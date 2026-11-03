"""Transaction responses (spec S3-R9) and the monthly cash-flow summary (spec S4-R6)."""
import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field

from backend.app.assessments.schemas import Transaction as TransactionOut   # the canonical row (S1-R5)


class MonthOut(BaseModel):
    month: str = Field(description="YYYY-MM")
    start: dt.date
    end: dt.date = Field(description="First day of the next month (exclusive)")
    covered: bool = Field(description="True when the stored batches cover the whole month")
    money_in: Optional[float] = Field(description="Sum of credits, interest included; null unless covered")
    money_out: Optional[float] = Field(description="Sum of debits; null unless covered")
    net: Optional[float] = Field(description="money_in - money_out; null unless covered")
    closing_balance: Optional[float] = Field(description="Running balance at the end of the month; null unless covered")
    transaction_count: int


class DailyBalance(BaseModel):
    date: dt.date
    balance: float = Field(description="Running balance after the day's last transaction")


class AssessmentWindow(BaseModel):
    assessment_id: int
    as_of: dt.date
    start: dt.date = Field(description="First day of the observation window (inclusive)")
    end: dt.date = Field(description="as_of: the window ends the day before (exclusive)")


class CashflowOut(BaseModel):
    borrower_id: str
    months: list[MonthOut]
    daily_balance: list[DailyBalance]
    window: Optional[AssessmentWindow] = Field(description="Window of the latest assessment; null if none")


__all__ = ["TransactionOut", "MonthOut", "DailyBalance", "AssessmentWindow", "CashflowOut"]
