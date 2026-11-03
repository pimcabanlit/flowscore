"""Scoring one borrower (spec S1-R6 to S1-R14).

Every feature comes from flowscore.features.cashflow (S1-R8): this module only cuts the history
to the past, calls the library, and turns the model's output into a percentile, a band and SHAP
contributions. The raw model score is never returned (S1-R9).
"""
import math

import numpy as np
import pandas as pd
from catboost import Pool

from flowscore.features.cashflow import (income_denominator, opening_balance, scale_free_features,
                                         window_features, window_slice)
from flowscore.schema import DATE, ordered

from backend.app.models.artifact import LoadedModel

WINDOW_MONTHS = 3        # D3
NOTICE = "Relative risk among 1990s Czech borrowers. Not validated on Philippine outcomes."   # S1-R14


class HistoryTooShort(ValueError):
    """The supplied history does not cover the whole observation window (S1-R6)."""


def window_start(as_of) -> pd.Timestamp:
    return pd.Timestamp(as_of) - pd.DateOffset(months=WINDOW_MONTHS)


def check_history(history_start, as_of) -> None:
    start = window_start(as_of)
    if pd.Timestamp(history_start) > start:
        raise HistoryTooShort(f"history_start {pd.Timestamp(history_start).date()} is later than "
                              f"{start.date()} (as_of minus {WINDOW_MONTHS} months): months without "
                              "transactions would look like months without income")


def compute_features(tx: pd.DataFrame, as_of) -> tuple:
    """(income_denominator, {feature: value}) from the library, using only transactions
    strictly before as_of (S1-R7). The cut happens before opening_balance as well, because that
    function would otherwise rebuild the opening from a later transaction when the history
    holds nothing before the window."""
    past = ordered(tx[tx[DATE] < pd.Timestamp(as_of)])
    window = window_slice(past, as_of, WINDOW_MONTHS)
    opening = opening_balance(past, window_start(as_of))
    income = income_denominator(window, as_of, WINDOW_MONTHS)
    feats = scale_free_features(window_features(window, as_of, opening, WINDOW_MONTHS), income)
    return income, feats


def _is_missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def range_check(features: dict, ranges: dict) -> tuple:
    """(missing, out_of_range, refused). Missing values are never out of range; scoring is
    refused when more than half of the non-missing features are out of range (S1-R13, D21)."""
    missing = [f for f, v in features.items() if _is_missing(v)]
    present = [f for f in features if f not in missing]
    out = [{"feature": f, "value": float(features[f]), "min": ranges[f]["min"], "max": ranges[f]["max"]}
           for f in present
           if not ranges[f]["min"] <= features[f] <= ranges[f]["max"]]
    return missing, out, len(out) > len(present) / 2


def percentile(score: float, reference_sorted: np.ndarray) -> float:
    """Share (0-100) of reference borrowers whose score is strictly lower (S1-R9)."""
    return 100.0 * np.searchsorted(reference_sorted, score, side="left") / len(reference_sorted)


def band(pct: float, cutoffs: dict) -> str:
    """lower below `lower_below`, higher above `higher_above`, middle in between (S1-R10)."""
    if pct < cutoffs["lower_below"]:
        return "lower"
    if pct > cutoffs["higher_above"]:
        return "higher"
    return "middle"


def shap_values(model: LoadedModel, X: pd.DataFrame) -> tuple:
    """(base_value, {feature: contribution}, raw_log_odds) from CatBoost's own SHAP values on the
    imputed and scaled features the model actually sees (S1-R11)."""
    prep, booster = model.pipeline[:-1], model.pipeline[-1]
    Xt = prep.transform(X)
    names = [n.split("__", 1)[-1] for n in prep.get_feature_names_out()]
    sv = booster.get_feature_importance(Pool(Xt), type="ShapValues")[0]
    raw = float(booster.predict(Xt, prediction_type="RawFormulaVal")[0])
    return float(sv[-1]), {n: float(v) for n, v in zip(names, sv[:-1])}, raw


def score(model: LoadedModel, tx: pd.DataFrame, as_of) -> dict:
    """The full assessment for one borrower. `tx` is a validated canonical table."""
    income, feats = compute_features(tx, as_of)
    missing, out_of_range, refused = range_check(feats, model.metadata["reference_ranges"])
    result = {
        "status": "refused" if refused else "scored",
        "model_version": model.model_version,
        "as_of": pd.Timestamp(as_of).date(),
        "income_denominator": None if _is_missing(income) else float(income),
        "features": {f: None if _is_missing(v) else float(v) for f, v in feats.items()},
        "missing": [{"feature": f, "imputed_value": model.imputed_values[f]} for f in missing],
        "out_of_range": out_of_range,
        "risk_percentile": None, "risk_band": None, "shap": None,
        "notice": NOTICE,
    }
    if refused:
        return result
    X = pd.DataFrame([[np.nan if _is_missing(feats[f]) else feats[f] for f in model.features]],
                     columns=model.features, dtype=float)
    p = float(model.pipeline.predict_proba(X)[0, 1])
    pct = percentile(p, model.reference_scores)
    base, contrib, _ = shap_values(model, X)
    result.update(risk_percentile=pct, risk_band=band(pct, model.metadata["band_cutoffs"]),
                  shap={"base_value": base, "contributions": contrib})
    return result
