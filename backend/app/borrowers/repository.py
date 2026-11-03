"""Reading borrowers (spec S3-R9). Borrowers are created only by the synthetic seed script
(S3-R12); there is no endpoint that creates one."""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.borrowers.models import Borrower
from backend.app.transactions.models import TransactionBatch


async def with_coverage(session: AsyncSession, borrower_id: Optional[str] = None) -> list:
    """[(borrower, first day covered, first day not covered)], ordered by id; every borrower, or
    only `borrower_id`. The two dates are None for a borrower with no batch."""
    cov = (select(TransactionBatch.borrower_id, func.min(TransactionBatch.period_start).label("start"),
                  func.max(TransactionBatch.period_end).label("end"))
           .group_by(TransactionBatch.borrower_id).subquery())
    q = select(Borrower, cov.c.start, cov.c.end).outerjoin(cov, cov.c.borrower_id == Borrower.id)
    if borrower_id is not None:
        q = q.where(Borrower.id == borrower_id)
    res = await session.execute(q.order_by(Borrower.id))
    return [tuple(r) for r in res.all()]
