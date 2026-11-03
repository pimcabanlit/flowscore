"""GET /api/v1/borrowers/{id}/transactions (spec S3-R9): the stored canonical rows, start
inclusive and end exclusive, in statement order. GET /api/v1/borrowers/{id}/cashflow (spec S4-R6):
the monthly summary the cash-flow view draws. Logs nothing about the rows (S3-R14)."""
import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.assessments import repository as assessments
from backend.app.assessments.service import window_start
from backend.app.borrowers.models import Borrower
from backend.app.core.db import get_session
from backend.app.transactions import repository, summary
from backend.app.transactions.schemas import CashflowOut, TransactionOut

router = APIRouter(prefix="/borrowers/{borrower_id}", tags=["transactions"])


async def _borrower_or_404(session: AsyncSession, borrower_id: str) -> None:
    if await session.get(Borrower, borrower_id) is None:
        raise HTTPException(status_code=404, detail=f"no borrower {borrower_id}")


@router.get("/transactions", response_model=list[TransactionOut])
async def list_transactions(borrower_id: str, start: Optional[dt.date] = None, end: Optional[dt.date] = None,
                            session: AsyncSession = Depends(get_session)) -> list:
    await _borrower_or_404(session, borrower_id)
    num = lambda d: None if d is None else float(d)
    return [{"transaction_id": tid, "transaction_date": date, "debit_amount": num(de), "credit_amount": num(cr),
             "running_balance": float(bal), "transaction_category": cat}
            for tid, date, de, cr, bal, cat in await repository.rows(session, borrower_id, start, end)]


@router.get("/cashflow", response_model=CashflowOut)
async def cashflow(borrower_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Monthly money in and out, closing balances, end-of-day balances, and the window of the
    latest assessment, so the frontend computes nothing (S4-R2, S4-R6)."""
    await _borrower_or_404(session, borrower_id)
    rows = await repository.rows(session, borrower_id)
    periods = await repository.periods(session, borrower_id)
    window = None
    history = await assessments.for_borrower(session, borrower_id)       # newest first
    if history:
        a, s = history[0]
        window = {"assessment_id": a.id, "as_of": s.as_of,
                  "start": window_start(s.as_of, s.window_months).date(), "end": s.as_of}
    return {"borrower_id": borrower_id, "months": summary.monthly(rows, periods),
            "daily_balance": summary.daily_balance(rows), "window": window}
