"""Reading and writing transactions (spec S3-R1, S3-R6, S3-R8).

Rows go in as canonical values with Decimal amounts and come out as a canonical DataFrame for
the feature library: an absent amount stays NaN, never 0 (S3-R6).
"""
import datetime as dt
import hashlib
from collections.abc import Iterable
from decimal import Decimal
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flowscore.schema import BALANCE, CATEGORY, CREDIT, DATE, DEBIT, ID, REQUIRED

from backend.app.transactions.models import Transaction, TransactionBatch

CENT = Decimal("0.01")


class WindowNotCovered(ValueError):
    """The stored batches do not cover the whole observation window (S3-R8)."""


def money(value) -> Optional[Decimal]:
    """A canonical amount as Decimal with 2 places, or None when absent. Refuses a value with
    more than 2 decimal places instead of rounding it silently (NUMERIC(14, 2) would)."""
    if value is None or value == "" or (isinstance(value, float) and np.isnan(value)):
        return None
    d = Decimal(str(value))
    if d != d.quantize(CENT):
        raise ValueError(f"amount {value} has more than 2 decimal places")
    return d.quantize(CENT)


def covers(periods: Iterable[tuple], start: dt.date, end: dt.date) -> bool:
    """True when the union of half-open periods [period_start, period_end) contains [start, end).
    Adjacent periods join (one ends on the day the next starts); a gap of a day breaks coverage."""
    reach = start
    for p_start, p_end in sorted(periods):
        if p_start > reach:
            break
        reach = max(reach, p_end)
        if reach >= end:
            return True
    return reach >= end


def fingerprint(rows: Iterable[tuple]) -> tuple:
    """(sha256, count) of canonical rows (id, date, debit, credit, balance, category), taken in
    statement order (date, then transaction id, as schema.ordered) with amounts written to 2
    places, so the same stored rows give the same digest on any engine (S3-R3)."""
    fmt = lambda d: "" if d is None else f"{Decimal(d):.2f}"
    h, n = hashlib.sha256(), 0
    for tid, date, debit, credit, balance, cat in sorted(rows, key=lambda r: (r[1], r[0])):
        h.update(f"{tid}|{date.isoformat()}|{fmt(debit)}|{fmt(credit)}|{fmt(balance)}|{cat}\n".encode())
        n += 1
    return h.hexdigest(), n


def as_tuple(t: Transaction) -> tuple:
    return (t.transaction_id, t.transaction_date, t.debit_amount, t.credit_amount, t.running_balance,
            t.transaction_category)


def to_frame(rows: Iterable[tuple]) -> pd.DataFrame:
    """Canonical DataFrame (flowscore.schema.REQUIRED) from canonical tuples. Decimal -> float;
    None -> NaN (never 0)."""
    num = lambda d: np.nan if d is None else float(d)
    df = pd.DataFrame([(tid, date, num(de), num(cr), float(bal), cat)
                       for tid, date, de, cr, bal, cat in rows], columns=REQUIRED)
    df[DATE] = pd.to_datetime(df[DATE])
    for c in (DEBIT, CREDIT, BALANCE):
        df[c] = df[c].astype(float)
    df[ID] = df[ID].astype(str)
    df[CATEGORY] = df[CATEGORY].astype(str)
    return df


async def add_batch(session: AsyncSession, borrower_id: str, source: str, period_start: dt.date,
                    period_end: dt.date, rows: Iterable[tuple]) -> TransactionBatch:
    """Store one batch and its rows (canonical tuples with Decimal or None amounts). The caller
    commits."""
    batch = TransactionBatch(borrower_id=borrower_id, source=source, period_start=period_start,
                             period_end=period_end)
    session.add(batch)
    await session.flush()
    session.add_all(Transaction(borrower_id=borrower_id, batch_id=batch.id, transaction_id=tid,
                                transaction_date=date, debit_amount=de, credit_amount=cr,
                                running_balance=bal, transaction_category=cat)
                    for tid, date, de, cr, bal, cat in rows)
    return batch


async def periods(session: AsyncSession, borrower_id: str) -> list:
    """[(period_start, period_end)] of every batch of the borrower."""
    res = await session.execute(select(TransactionBatch.period_start, TransactionBatch.period_end)
                                .where(TransactionBatch.borrower_id == borrower_id))
    return [tuple(r) for r in res.all()]


async def rows(session: AsyncSession, borrower_id: str, start: Optional[dt.date] = None,
               end: Optional[dt.date] = None) -> list:
    """The borrower's rows as canonical tuples, start inclusive and end exclusive, in statement
    order (date, then transaction id)."""
    q = select(Transaction).where(Transaction.borrower_id == borrower_id)
    if start is not None:
        q = q.where(Transaction.transaction_date >= start)
    if end is not None:
        q = q.where(Transaction.transaction_date < end)
    # Sorted here, not in SQL: a database collation may order ids differently from Python.
    return sorted((as_tuple(t) for t in (await session.scalars(q)).all()), key=lambda r: (r[1], r[0]))
