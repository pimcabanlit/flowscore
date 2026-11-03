"""The assessments table (spec S3-R1, S3-R2, S3-R3).

An assessment is never updated or deleted: a new score is a new row (S3-R2; a trigger in the
migration enforces it). It points to the snapshot it scored and the model version that scored it.
"""
import datetime as dt
from typing import Optional

from sqlalchemy import CheckConstraint, Double, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.db import Base, JSONType, UTCDateTime, utcnow


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(
            "(status = 'scored' AND risk_percentile IS NOT NULL AND risk_band IS NOT NULL) OR "
            "(status = 'refused' AND risk_percentile IS NULL AND risk_band IS NULL)",
            name="status_matches_outputs"),
        CheckConstraint("risk_band IS NULL OR risk_band IN ('lower', 'middle', 'higher')",
                        name="band_is_relative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("feature_snapshots.id"), index=True)
    model_version: Mapped[str] = mapped_column(ForeignKey("model_registry.model_version"))
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(10))
    risk_percentile: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    risk_band: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    shap: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    missing: Mapped[list] = mapped_column(JSONType)
    out_of_range: Mapped[list] = mapped_column(JSONType)
    notice: Mapped[str] = mapped_column(Text)
