"""Storing and reading assessments (spec S3-R2, S3-R3).

Append-only: there is an `add` and there are reads, and nothing else. The migration's triggers
refuse UPDATE and DELETE as well, so even code that bypasses this module cannot edit history.
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.assessments.models import Assessment
from backend.app.assessments.service import window_start
from backend.app.features.models import FeatureSnapshot
from backend.app.features.service import in_feature_order


async def add(session: AsyncSession, snapshot: FeatureSnapshot, result: dict) -> Assessment:
    """Store the output of service.score_features for `snapshot` as a new row."""
    row = Assessment(snapshot_id=snapshot.id, model_version=result["model_version"], status=result["status"],
                     risk_percentile=result["risk_percentile"], risk_band=result["risk_band"],
                     shap=result["shap"], missing=result["missing"], out_of_range=result["out_of_range"],
                     notice=result["notice"])
    session.add(row)
    await session.commit()
    return row


async def get(session: AsyncSession, assessment_id: int) -> Optional[tuple]:
    """(assessment, snapshot), or None."""
    res = await session.execute(select(Assessment, FeatureSnapshot)
                                .join(FeatureSnapshot, Assessment.snapshot_id == FeatureSnapshot.id)
                                .where(Assessment.id == assessment_id))
    return res.first()


async def for_borrower(session: AsyncSession, borrower_id: str) -> list:
    """[(assessment, snapshot)] of one borrower, newest first."""
    res = await session.execute(select(Assessment, FeatureSnapshot)
                                .join(FeatureSnapshot, Assessment.snapshot_id == FeatureSnapshot.id)
                                .where(FeatureSnapshot.borrower_id == borrower_id)
                                .order_by(Assessment.id.desc()))
    return [tuple(r) for r in res.all()]


async def latest_by_borrower(session: AsyncSession) -> dict:
    """borrower_id -> (assessment, snapshot) of the newest assessment of each borrower."""
    newest = (select(func.max(Assessment.id).label("id"))
              .join(FeatureSnapshot, Assessment.snapshot_id == FeatureSnapshot.id)
              .group_by(FeatureSnapshot.borrower_id).subquery())
    res = await session.execute(select(Assessment, FeatureSnapshot)
                                .join(FeatureSnapshot, Assessment.snapshot_id == FeatureSnapshot.id)
                                .where(Assessment.id.in_(select(newest.c.id))))
    return {s.borrower_id: (a, s) for a, s in res.all()}


def to_response(a: Assessment, s: FeatureSnapshot) -> dict:
    """The stored assessment in the slice 1 response shape (S1-R15), plus its ids (S3-R9)."""
    shap = None
    if a.shap is not None:
        shap = {"base_value": a.shap["base_value"], "contributions": in_feature_order(a.shap["contributions"])}
    return {
        "id": a.id, "borrower_id": s.borrower_id, "snapshot_id": s.id, "features_version": s.features_version,
        "created_at": a.created_at,
        "window_start": window_start(s.as_of, s.window_months).date(),
        "status": a.status, "model_version": a.model_version, "as_of": s.as_of,
        "income_denominator": s.income_denominator, "features": in_feature_order(s.features),
        "missing": a.missing, "out_of_range": a.out_of_range,
        "risk_percentile": a.risk_percentile, "risk_band": a.risk_band, "shap": shap, "notice": a.notice,
    }
