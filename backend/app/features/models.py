"""The feature_snapshots table (spec S3-R1, S3-R3, S3-R6).

A snapshot is the input of an assessment: the features of one borrower as of one date, with
what is needed to tell later whether they would come out the same (the feature code version
and a fingerprint of the transactions used). Feature values are a JSON object; a feature that
cannot be computed is JSON null, never 0. Snapshots are never updated or deleted (S3-R2).
"""
import datetime as dt
from typing import Optional

from sqlalchemy import Date, Double, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.db import Base, JSONType, UTCDateTime, utcnow


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"
    __table_args__ = (UniqueConstraint("borrower_id", "as_of", "features_version", "transactions_sha256"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    borrower_id: Mapped[str] = mapped_column(ForeignKey("borrowers.id"), index=True)
    as_of: Mapped[dt.date] = mapped_column(Date)
    window_months: Mapped[int] = mapped_column(Integer)
    income_denominator: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    features: Mapped[dict] = mapped_column(JSONType)                  # name -> float or null
    features_version: Mapped[str] = mapped_column(String(64))         # sha256 of cashflow.py
    transactions_sha256: Mapped[str] = mapped_column(String(64))
    transaction_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
