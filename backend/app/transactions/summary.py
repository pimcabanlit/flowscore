"""The monthly cash-flow summary behind the borrower cash-flow view (spec S4-R6).

This is a display summary, not a model feature: the model's features come only from
features/cashflow.py (hard rule 4), and nothing here feeds them. It exists so the frontend draws
the cash-flow view from figures the API computed and pytest checked, and computes nothing itself
(S4-R2).

Rules, hand-worked in tests/test_frontend_api.py:
- Months are calendar months, from the month of the first covered day to the month of the last.
- A month gets money in, money out and net only when the stored batches cover all of it
  (`covers`, D24). A month covered only in part, or not at all, has None for all three: part of a
  month would look like a month with less income. Missing is not zero (hard rule 6).
- Money in is every credit and money out every debit, interest included. The model's income
  figure (income_denominator) excludes interest; the view says so.
- The closing balance is the running balance after the month's last transaction, or the last
  one before it when the month had none. None when the month is not fully covered, or when no
  transaction is known up to its end.
- Sums are Decimal, so 0.10 + 0.20 is 0.30, not 0.30000000000000004.
"""
import datetime as dt
from collections.abc import Iterable
from decimal import Decimal
from typing import Optional

from backend.app.transactions.repository import covers


def _month_start(d: dt.date) -> dt.date:
    return d.replace(day=1)


def _next_month(d: dt.date) -> dt.date:
    return (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def _num(d: Optional[Decimal]) -> Optional[float]:
    return None if d is None else float(d)


def monthly(rows: Iterable[tuple], periods: Iterable[tuple]) -> list:
    """[{month, start, end, covered, money_in, money_out, net, closing_balance, transaction_count}]
    from canonical tuples (id, date, debit, credit, balance, category) in statement order and the
    borrower's batch periods [(period_start, period_end)], end exclusive."""
    rows, periods = list(rows), list(periods)
    if not periods:
        return []
    first = _month_start(min(p[0] for p in periods))
    last_day = max(p[1] for p in periods) - dt.timedelta(days=1)
    out, i, balance = [], 0, None
    m = first
    while m <= last_day:
        end = _next_month(m)
        money_in, money_out, count = Decimal("0"), Decimal("0"), 0
        while i < len(rows) and rows[i][1] < end:
            _, date, debit, credit, bal, _ = rows[i]
            if date >= m:
                money_in += credit or Decimal("0")       # a credit row has no debit, and the reverse
                money_out += debit or Decimal("0")
                count += 1
            balance = Decimal(bal)
            i += 1
        full = covers(periods, m, end)
        out.append({
            "month": m.strftime("%Y-%m"), "start": m, "end": end, "covered": full,
            "money_in": _num(money_in) if full else None,
            "money_out": _num(money_out) if full else None,
            "net": _num(money_in - money_out) if full else None,
            "closing_balance": _num(balance) if full else None,
            "transaction_count": count,
        })
        m = end
    return out


def daily_balance(rows: Iterable[tuple]) -> list:
    """[{date, balance}]: the running balance after the last transaction of each day that has
    one, in date order. Days without a transaction are not listed (the balance did not change)."""
    last = {}
    for _, date, _, _, bal, _ in rows:          # statement order: the day's last row wins
        last[date] = bal
    return [{"date": d, "balance": float(b)} for d, b in sorted(last.items())]
