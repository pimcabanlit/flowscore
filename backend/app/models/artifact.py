"""The app model artifact (spec S1-R3, S1-R4): one folder per version, `models/<model_version>/`.

    model.joblib    the fitted pipeline: imputer, scaler and CatBoost (experiment.make_catboost)
    metadata.json   version, provenance, feature list, metrics, reference ranges,
                    reference scores for the percentile and the band cut-offs

`build_artifact` is used by scripts/train_app_model.py (real Berka model) and by the tests
(a tiny model on synthetic rows). `load_artifact` refuses an artifact whose feature list does
not match the code, so features can never be scored in the wrong order.
"""
import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from flowscore.experiment import make_catboost
from flowscore.features.cashflow import SCALE_FREE_FEATURES

MODEL_FILE = "model.joblib"
METADATA_FILE = "metadata.json"


class ArtifactError(RuntimeError):
    """The artifact is missing, incomplete or does not match the code."""


def reference_ranges(X: pd.DataFrame) -> dict:
    """Min and max of each feature over the training rows, ignoring NaN (D21)."""
    return {c: {"min": float(np.nanmin(X[c])), "max": float(np.nanmax(X[c]))} for c in X.columns}


def predictions_digest(p: np.ndarray) -> str:
    """Fingerprint of the training-row predictions, so two training runs can be compared."""
    return hashlib.sha256(np.round(np.asarray(p, dtype=float), 12).tobytes()).hexdigest()


def build_artifact(X: pd.DataFrame, y: np.ndarray, *, out_dir, model_version: str,
                   reference_scores: np.ndarray, band_cutoffs: dict, metrics: dict,
                   training_data: dict, git_commit: str) -> dict:
    """Fit the app pipeline on all rows of X (columns = SCALE_FREE_FEATURES) and save it.

    reference_scores: one model score per training row, used for the percentile (S1-R9);
    out-of-fold scores for the real model (spec open question 3). Returns the metadata."""
    if list(X.columns) != SCALE_FREE_FEATURES:
        raise ArtifactError(f"training columns {list(X.columns)} != SCALE_FREE_FEATURES")
    if len(reference_scores) != len(X):
        raise ArtifactError("need one reference score per training row")
    lower, higher = band_cutoffs["lower_below"], band_cutoffs["higher_above"]
    if not 0 <= lower <= higher <= 100:
        raise ArtifactError(f"band cut-offs must satisfy 0 <= lower <= higher <= 100: {band_cutoffs}")

    pipe = make_catboost(SCALE_FREE_FEATURES).fit(X, y)
    meta = {
        "model_version": model_version,
        "created_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "git_commit": git_commit,
        "features": list(SCALE_FREE_FEATURES),
        "training_data": training_data,
        "metrics": metrics,
        "reference_ranges": reference_ranges(X),
        "reference_scores": [float(s) for s in reference_scores],
        "band_cutoffs": {"lower_below": float(lower), "higher_above": float(higher)},
        "training_predictions_sha256": predictions_digest(pipe.predict_proba(X)[:, 1]),
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, out / MODEL_FILE)
    (out / METADATA_FILE).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


@dataclass(frozen=True)
class LoadedModel:
    """An artifact held in memory (S1-R17). Built once at startup; requests never touch disk."""
    pipeline: object
    metadata: dict
    features: list
    reference_scores: np.ndarray          # sorted, for the percentile
    imputed_values: dict                  # feature -> training median the imputer fills in

    @property
    def model_version(self) -> str:
        return self.metadata["model_version"]


def _imputed_values(pipeline) -> dict:
    """The value the pipeline's imputer puts in for each feature (the training median)."""
    ct = pipeline[0]
    out = {}
    for name, steps, cols in ct.transformers_:
        if name in ("money", "num") and len(cols):
            out.update(dict(zip(cols, (float(v) for v in steps[0].statistics_))))
    return out


def load_artifact(path) -> LoadedModel:
    """Read an artifact folder and check it against the code (S1-R4)."""
    path = Path(path)
    if not (path / MODEL_FILE).is_file() or not (path / METADATA_FILE).is_file():
        raise ArtifactError(f"no model artifact at {path} (expected {MODEL_FILE} and {METADATA_FILE}); "
                            "run scripts/train_app_model.py or set FLOWSCORE_MODEL_DIR")
    meta = json.loads((path / METADATA_FILE).read_text(encoding="utf-8"))
    pipe = joblib.load(path / MODEL_FILE)
    if meta.get("features") != SCALE_FREE_FEATURES:
        raise ArtifactError(f"artifact features {meta.get('features')} != SCALE_FREE_FEATURES "
                            f"{SCALE_FREE_FEATURES}; refusing to load")
    fitted = list(getattr(pipe, "feature_names_in_", []))
    if fitted != SCALE_FREE_FEATURES:
        raise ArtifactError(f"model was fitted on {fitted} != SCALE_FREE_FEATURES; refusing to load")
    missing = {"reference_ranges", "reference_scores", "band_cutoffs", "model_version"} - set(meta)
    if missing:
        raise ArtifactError(f"metadata.json lacks {sorted(missing)}")
    return LoadedModel(pipeline=pipe, metadata=meta, features=list(SCALE_FREE_FEATURES),
                       reference_scores=np.sort(np.asarray(meta["reference_scores"], dtype=float)),
                       imputed_values=_imputed_values(pipe))
