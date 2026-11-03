"""Request and response schemas for scoring (spec S1-R5, S1-R15). Unknown fields are rejected."""
import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MAX_TRANSACTIONS = 20_000     # a generous year of statements; bounds the work one request can ask for


class Transaction(BaseModel):
    """One row of the canonical schema (flowscore.schema.REQUIRED)."""
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(min_length=1, max_length=100)
    transaction_date: dt.date
    debit_amount: Optional[float] = Field(default=None, allow_inf_nan=False)
    credit_amount: Optional[float] = Field(default=None, allow_inf_nan=False)
    running_balance: float = Field(allow_inf_nan=False)
    transaction_category: str = Field(min_length=1, max_length=50)


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: dt.date
    history_start: dt.date = Field(description="First date the supplied transactions cover")
    transactions: list[Transaction] = Field(max_length=MAX_TRANSACTIONS)


class MissingFeature(BaseModel):
    feature: str
    imputed_value: float = Field(description="Training median the model used in its place (D21)")


class OutOfRange(BaseModel):
    feature: str
    value: float
    min: float
    max: float


class Shap(BaseModel):
    base_value: float = Field(description="Log-odds before any feature is known")
    contributions: dict[str, float] = Field(description="Log-odds contribution of each feature")


class ScoreResponse(BaseModel):
    status: Literal["scored", "refused"]
    model_version: str
    as_of: dt.date
    income_denominator: Optional[float]
    features: dict[str, Optional[float]]
    missing: list[MissingFeature]
    out_of_range: list[OutOfRange]
    risk_percentile: Optional[float] = Field(description="Share of Berka reference borrowers with a lower score")
    risk_band: Optional[Literal["lower", "middle", "higher"]] = Field(
        description='"lower", "middle" or "higher" relative risk among the Berka reference borrowers. '
                    'Always relative: never an absolute level such as "high risk" (D21, D22).')
    shap: Optional[Shap]
    notice: str


class Health(BaseModel):
    model_version: str
    features: list[str]


class AssessRequest(BaseModel):
    """POST /api/v1/borrowers/{id}/assessments (S3-R9)."""
    model_config = ConfigDict(extra="forbid")

    as_of: dt.date


class StoredAssessment(ScoreResponse):
    """A stored assessment: the slice 1 response plus where it came from (S3-R9)."""
    id: int
    borrower_id: str
    snapshot_id: int
    features_version: str = Field(description="SHA-256 of features/cashflow.py when the snapshot was computed")
    created_at: dt.datetime


class AssessmentSummary(BaseModel):
    id: int
    as_of: dt.date
    status: Literal["scored", "refused"]
    risk_band: Optional[Literal["lower", "middle", "higher"]]
    risk_percentile: Optional[float]
    model_version: str
    created_at: dt.datetime
