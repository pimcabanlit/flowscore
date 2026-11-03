"""The borrowers table (spec S3-R1)."""
import datetime as dt

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.db import Base, UTCDateTime, utcnow


class Borrower(Base):
    __tablename__ = "borrowers"
    # Synthetic borrowers only in this slice (out of scope: real data). The slice that admits
    # real borrowers drops this constraint in its own migration, with a decision entry.
    __table_args__ = (CheckConstraint("synthetic", name="synthetic_only"),)

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    synthetic: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
