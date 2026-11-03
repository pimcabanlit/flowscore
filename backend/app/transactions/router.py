"""GET /api/v1/borrowers/{id}/transactions (spec S3-R9): the stored canonical rows, start
inclusive and end exclusive, in statement order. Logs nothing about the rows (S3-R14)."""
import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.borrowers.models import Borrower
from backend.app.core.db import get_session
from backend.app.transactions import repository
from backend.app.transactions.schemas import TransactionOut

router = APIRouter(prefix="/borrowers/{borrower_id}/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
async def list_transactions(borrower_id: str, start: Optional[dt.date] = None, end: Optional[dt.date] = None,
                            session: AsyncSession = Depends(get_session)) -> list:
    if await session.get(Borrower, borrower_id) is None:
        raise HTTPException(status_code=404, detail=f"no borrower {borrower_id}")
    num = lambda d: None if d is None else float(d)
    return [{"transaction_id": tid, "transaction_date": date, "debit_amount": num(de), "credit_amount": num(cr),
             "running_balance": float(bal), "transaction_category": cat}
            for tid, date, de, cr, bal, cat in await repository.rows(session, borrower_id, start, end)]
