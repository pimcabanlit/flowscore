"""Plain-language names for the model's features (spec S4-R7).

What a number means on screen is decided here, in the backend, where pytest and the High/Medium
review read it, and not in the frontend. Every feature in SCALE_FREE_FEATURES has exactly one
entry (tests/test_frontend_api.py). The wording follows the definitions in features/cashflow.py
and D21; the window is the WINDOW_MONTHS months before as_of (D3).

`unit` tells the frontend how to write the raw value next to its label:
- "coefficient": a plain number (standard deviation / mean)
- "ratio": a multiple, e.g. 0.86x
- "months": a whole count out of WINDOW_MONTHS
- "months_of_income": a multiple of one month's income
"""
from flowscore.features.cashflow import SCALE_FREE_FEATURES

from backend.app.assessments.service import WINDOW_MONTHS

_N = WINDOW_MONTHS
_INCOME = "monthly income (the median monthly money in over the window, excluding bank interest)"

GLOSSARY = {
    "inflow_cv": {
        "label": "Income variability",
        "description": f"How much monthly money in (excluding bank interest) varies over the {_N} months: "
                       "standard deviation divided by the average. 0 means the same amount every month.",
        "unit": "coefficient",
    },
    "outflow_inflow_ratio": {
        "label": "Spending relative to income",
        "description": f"Money out divided by money in (excluding bank interest) over the {_N} months. "
                       "Above 1 means more went out than came in.",
        "unit": "ratio",
    },
    "months_net_outflow": {
        "label": "Months spending more than came in",
        "description": f"How many of the {_N} months had more money out than money in.",
        "unit": "months",
    },
    "min_balance_to_income": {
        "label": "Lowest balance relative to income",
        "description": f"The lowest balance in the window, at any point in a day, divided by {_INCOME}.",
        "unit": "months_of_income",
    },
    "avg_balance_to_income": {
        "label": "Average balance relative to income",
        "description": f"The average end-of-day balance over the window divided by {_INCOME}.",
        "unit": "months_of_income",
    },
}


def entries() -> list:
    """The glossary in SCALE_FREE_FEATURES order."""
    return [{"feature": f, "window_months": _N, **GLOSSARY[f]} for f in SCALE_FREE_FEATURES]
