"""POST /api/v1/assessments/score (spec S1-R15).

Logs only the model version, status and timing (S1-R18): never the request body or features.
"""
import logging
import time

import pandas as pd
from fastapi import APIRouter, HTTPException, Request

from flowscore.schema import CREDIT, DATE, DEBIT, REQUIRED, validate

from backend.app.assessments import service
from backend.app.assessments.schemas import ScoreRequest, ScoreResponse

log = logging.getLogger("flowscore.api")
router = APIRouter(prefix="/assessments", tags=["assessments"])


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
