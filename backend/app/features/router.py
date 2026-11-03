"""GET /api/v1/features/glossary (spec S4-R7): plain-language labels for the model's features.
Needs no database; the frontend reads it to label the SHAP bars and feature values."""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.features import glossary

router = APIRouter(prefix="/features", tags=["features"])


class GlossaryEntry(BaseModel):
    feature: str
    label: str
    description: str
    unit: Literal["coefficient", "ratio", "months", "months_of_income"]
    window_months: int


@router.get("/glossary", response_model=list[GlossaryEntry])
def get_glossary() -> list:
    return glossary.entries()
