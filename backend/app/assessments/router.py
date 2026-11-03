"""POST /api/v1/assessments/score (spec S1-R15), and stored assessments (spec S3-R9):
POST and GET /api/v1/borrowers/{id}/assessments, GET /api/v1/assessments/{id}.

Logs only ids, the model version, status and timing (S1-R18, S3-R14): never the request body,
transactions or features.
"""
import logging
import time

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from flowscore.schema import CREDIT, DATE, DEBIT, REQUIRED, validate

from backend.app.assessments import repository, service
from backend.app.assessments.schemas import AssessRequest, ScoreRequest, ScoreResponse, StoredAssessment
from backend.app.borrowers.models import Borrower
from backend.app.core.db import get_session
from backend.app.features.service import in_feature_order, snapshot_for
from backend.app.transactions.repository import WindowNotCovered

log = logging.getLogger("flowscore.api")
router = APIRouter(prefix="/assessments", tags=["assessments"])
borrower_router = APIRouter(prefix="/borrowers/{borrower_id}/assessments", tags=["assessments"])


def to_frame(req: ScoreRequest) -> pd.DataFrame:
    rows = [t.model_dump() for t in req.transactions]
    df = pd.DataFrame(rows, columns=REQUIRED)
    df[DATE] = pd.to_datetime(df[DATE])
    for c in (DEBIT, CREDIT):           # absent amount = NaN, never 0 (hard rule 6)
        df[c] = pd.to_numeric(df[c]).astype(float)
    return df


def _error(msg: str) -> dict:
    return {"loc": ["body"], "msg": msg, "type": "value_error"}


@router.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest, request: Request) -> dict:
    t0 = time.perf_counter()
    model = request.app.state.model
    df = to_frame(req)
    errors = [_error(e) for e in validate(df)]                        # S1-R5: all errors, not the first
    try:
        service.check_history(req.history_start, req.as_of)          # S1-R6
    except service.HistoryTooShort as e:
        errors.append(_error(str(e)))
    if len(df) and df[DATE].min() < pd.Timestamp(req.history_start):
        errors.append(_error("transactions dated before history_start"))
    if errors:
        log.info("score model=%s status=invalid errors=%d ms=%.0f", model.model_version, len(errors),
                 1000 * (time.perf_counter() - t0))
        raise HTTPException(status_code=422, detail=errors)
    result = service.score(model, df, req.as_of)
    log.info("score model=%s status=%s ms=%.0f", model.model_version, result["status"],
             1000 * (time.perf_counter() - t0))
    return result


# ---------------------------------------------------------------------------------------------
# stored assessments (slice 3)

async def _borrower_or_404(session: AsyncSession, borrower_id: str) -> Borrower:
    b = await session.get(Borrower, borrower_id)
    if b is None:
        raise HTTPException(status_code=404, detail=f"no borrower {borrower_id}")
    return b


@borrower_router.post("", response_model=StoredAssessment, status_code=201)
async def assess(borrower_id: str, req: AssessRequest, request: Request,
                 session: AsyncSession = Depends(get_session)) -> dict:
    """Score a stored borrower as of a date and keep the result (S3-R3, S3-R8). The features are
    always read back from the stored snapshot, so a rescore starts from the same numbers."""
    t0 = time.perf_counter()
    model = request.app.state.model
    await _borrower_or_404(session, borrower_id)
    try:
        snap = await snapshot_for(session, borrower_id, req.as_of)
    except WindowNotCovered as e:
        log.info("assess borrower=%s status=invalid ms=%.0f", borrower_id, 1000 * (time.perf_counter() - t0))
        raise HTTPException(status_code=422, detail=[_error(str(e))])
    result = await run_in_threadpool(service.score_features, model, snap.income_denominator,
                                     in_feature_order(snap.features), snap.as_of)
    row = await repository.add(session, snap, result)
    log.info("assess borrower=%s assessment=%d snapshot=%d model=%s status=%s ms=%.0f", borrower_id, row.id,
             snap.id, model.model_version, row.status, 1000 * (time.perf_counter() - t0))
    return repository.to_response(row, snap)


@borrower_router.get("", response_model=list[StoredAssessment])
async def list_for_borrower(borrower_id: str, session: AsyncSession = Depends(get_session)) -> list:
    await _borrower_or_404(session, borrower_id)
    return [repository.to_response(a, s) for a, s in await repository.for_borrower(session, borrower_id)]


@router.get("/{assessment_id}", response_model=StoredAssessment)
async def get_assessment(assessment_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    found = await repository.get(session, assessment_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"no assessment {assessment_id}")
    return repository.to_response(*found)
