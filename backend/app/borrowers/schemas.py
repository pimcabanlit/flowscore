"""Borrower responses (spec S3-R9)."""
import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field

from backend.app.assessments.schemas import AssessmentSummary


class BorrowerOut(BaseModel):
    id: str
    display_name: str
    synthetic: bool
    created_at: dt.datetime
    history_start: Optional[dt.date] = Field(description="First day the stored batches cover")
    history_end: Optional[dt.date] = Field(description="First day after the stored batches (exclusive)")
    latest_assessment: Optional[AssessmentSummary]
