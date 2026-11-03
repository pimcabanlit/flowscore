"""GET /api/v1/borrowers and GET /api/v1/borrowers/{id} (spec S3-R9)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.assessments import repository as assessments
from backend.app.borrowers import repository
from backend.app.borrowers.schemas import BorrowerOut
from backend.app.core.db import get_session

router = APIRouter(prefix="/borrowers", tags=["borrowers"])


def _out(b, start, end, latest) -> dict:
    summary = None
    if latest is not None:
        a, s = latest
        summary = {"id": a.id, "as_of": s.as_of, "status": a.status, "risk_band": a.risk_band,
                   "risk_percentile": a.risk_percentile, "model_version": a.model_version,
                   "created_at": a.created_at}
    return {"id": b.id, "display_name": b.display_name, "synthetic": b.synthetic, "created_at": b.created_at,
            "history_start": start, "history_end": end, "latest_assessment": summary}


@router.get("", response_model=list[BorrowerOut])
async def list_borrowers(session: AsyncSession = Depends(get_session)) -> list:
    latest = await assessments.latest_by_borrower(session)
    return [_out(b, start, end, latest.get(b.id)) for b, start, end in await repository.with_coverage(session)]


@router.get("/{borrower_id}", response_model=BorrowerOut)
async def get_borrower(borrower_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    found = await repository.with_coverage(session, borrower_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"no borrower {borrower_id}")
    b, start, end = found[0]
    latest = await assessments.latest_by_borrower(session)
    return _out(b, start, end, latest.get(b.id))
