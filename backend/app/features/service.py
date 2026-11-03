"""Feature snapshots (spec S3-R3, S3-R6, S3-R8, S3-R11).

A snapshot is computed by the slice 1 service (`compute_features`, which calls
features/cashflow.py) from the stored transactions strictly before as_of. Nothing here computes
a feature. When a snapshot with the same borrower, as_of, feature code version and transaction
fingerprint already exists, it is reused, so rescoring always starts from the same numbers.
"""
import datetime as dt
import hashlib
import math
from pathlib import Path

import flowscore.features.cashflow as cashflow
from flowscore.features.cashflow import SCALE_FREE_FEATURES
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.assessments.service import WINDOW_MONTHS, compute_features, window_start
from backend.app.features.models import FeatureSnapshot
from backend.app.transactions import repository as transactions
from backend.app.transactions.repository import WindowNotCovered

# The feature code version: the SHA-256 of cashflow.py itself (.gitattributes keeps *.py at LF,
# so it is the same on Windows). Any change to the feature code changes it (S3-R3).
FEATURES_VERSION = hashlib.sha256(Path(cashflow.__file__).read_bytes()).hexdigest()


def _null_if_missing(v):
    """NaN -> None (JSON null), never 0 (S3-R6)."""
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def in_feature_order(values: dict) -> dict:
    """A feature dict in SCALE_FREE_FEATURES order. JSONB does not keep key order, and the order
    decides the order of the missing and out-of-range lists (S3-R10)."""
    rank = {f: i for i, f in enumerate(SCALE_FREE_FEATURES)}
    return {k: values[k] for k in sorted(values, key=lambda k: (rank.get(k, len(rank)), k))}


async def _find(session: AsyncSession, borrower_id: str, as_of: dt.date, digest: str):
    return await session.scalar(select(FeatureSnapshot).where(
        FeatureSnapshot.borrower_id == borrower_id, FeatureSnapshot.as_of == as_of,
        FeatureSnapshot.features_version == FEATURES_VERSION, FeatureSnapshot.transactions_sha256 == digest))


async def snapshot_for(session: AsyncSession, borrower_id: str, as_of: dt.date) -> FeatureSnapshot:
    """The snapshot of `borrower_id` as of `as_of`: reused if one matches, else computed and stored.
    Raises WindowNotCovered when the stored batches do not cover the window (S3-R8)."""
    start = window_start(as_of).date()
    if not transactions.covers(await transactions.periods(session, borrower_id), start, as_of):
        raise WindowNotCovered(f"stored transactions do not cover {start} to {as_of} "
                               f"(as_of minus {WINDOW_MONTHS} months up to as_of): months without "
                               "transactions would look like months without income")
    past = await transactions.rows(session, borrower_id, end=as_of)         # strictly before as_of
    digest, count = transactions.fingerprint(past)
    found = await _find(session, borrower_id, as_of, digest)
    if found is not None:
        return found
    income, feats = await run_in_threadpool(compute_features, transactions.to_frame(past), as_of)
    snap = FeatureSnapshot(borrower_id=borrower_id, as_of=as_of, window_months=WINDOW_MONTHS,
                           income_denominator=_null_if_missing(income),
                           features={f: _null_if_missing(v) for f, v in feats.items()},
                           features_version=FEATURES_VERSION, transactions_sha256=digest,
                           transaction_count=count)
    session.add(snap)
    try:
        await session.commit()
    except IntegrityError:                  # the same snapshot was stored by a parallel request
        await session.rollback()
        found = await _find(session, borrower_id, as_of, digest)
        if found is None:
            raise
        return found
    return snap
