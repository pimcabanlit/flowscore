"""Transaction batches and transactions (spec S3-R1, S3-R6, S3-R8).

One row per transaction, in the canonical schema (flowscore.schema), plus the borrower and the
batch it was loaded in. A batch records the period a statement (or a synthetic history) covers,
so an assessment can check that its whole window is covered (S3-R8). Amounts are NUMERIC(14, 2);
an absent debit or credit is NULL, never 0 (S3-R6).
"""
import datetime as dt
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.db import Base, UTCDateTime, utcnow

MONEY = Numeric(14, 2)


class TransactionBatch(Base):
    __tablename__ = "transaction_batches"
    __table_args__ = (CheckConstraint("period_start < period_end", name="period_not_empty"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    borrower_id: Mapped[str] = mapped_column(ForeignKey("borrowers.id"), index=True)
    source: Mapped[str] = mapped_column(String(50))
    period_start: Mapped[dt.date] = mapped_column(Date)          # first day covered
    period_end: Mapped[dt.date] = mapped_column(Date)            # first day NOT covered
    loaded_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("borrower_id", "transaction_id"),
        Index("ix_transactions_borrower_id_transaction_date", "borrower_id", "transaction_date"),
        CheckConstraint("debit_amount IS NULL OR debit_amount >= 0", name="debit_not_negative"),
        CheckConstraint("credit_amount IS NULL OR credit_amount >= 0", name="credit_not_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    borrower_id: Mapped[str] = mapped_column(ForeignKey("borrowers.id"))
    batch_id: Mapped[int] = mapped_column(ForeignKey("transaction_batches.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(String(100))
    transaction_date: Mapped[dt.date] = mapped_column(Date)
    debit_amount: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    credit_amount: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    running_balance: Mapped[Decimal] = mapped_column(MONEY)
    transaction_category: Mapped[str] = mapped_column(String(50))
