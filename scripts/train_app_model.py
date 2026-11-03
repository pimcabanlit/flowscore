"""Train the app model once and save it as a versioned artifact (spec S1-R1 to S1-R3, D21).

    $env:PYTHONPATH="src"; python scripts\\train_app_model.py      (needs data/raw/; a few minutes)

Writes models/catboost-sf-v1/ (model.joblib + metadata.json). Reuses the research code only:
build_transaction_features(..., scale_free=True), make_catboost and oof_predictions, on the same
682 loans, label (D2), window (D3), settings (D15) and folds as scripts/run_scale_free.py.

The percentile reference is the out-of-fold score of every loan, averaged over the 10 repeats
of the D21 folds (spec open question 3): in-sample scores are overfitted. As a check, the AUROC
of those out-of-fold scores must equal auroc_scale_free in results/d21_scale_free.csv.

Determinism (S1-R2): the final model is fitted twice and the two must predict identically;
metadata.json records a hash of the training-row predictions, so separate runs can be compared.
"""
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))            # for backend.app

from flowscore.data import load_berka                                          # noqa: E402
from flowscore.experiment import make_catboost, oof_predictions               # noqa: E402
from flowscore.features.cashflow import SCALE_FREE_FEATURES                    # noqa: E402
from flowscore.features.transactions import build_transaction_features        # noqa: E402

from backend.app.models.artifact import build_artifact, predictions_digest    # noqa: E402

warnings.filterwarnings("ignore")

MODEL_VERSION = "catboost-sf-v1"
WINDOW_MONTHS = 3                 # D3
N_REPEATS = 10                    # as scripts/run_scale_free.py
BAND_CUTOFFS = {"lower_below": 50, "higher_above": 80}   # spec open question 2 (recommendation)


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "scripts", "backend"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main():
    t = load_berka(str(ROOT / "data" / "raw") + "/")
    sf = build_transaction_features(t["loan"], t["trans"], months=WINDOW_MONTHS, scale_free=True)
    df = sf.merge(t["loan"][["loan_id", "bad"]], on="loan_id").sort_values("loan_id").reset_index(drop=True)
    X, y = df[SCALE_FREE_FEATURES], df.bad.to_numpy()
    print(f"loans {len(df)}, defaults {y.sum()}, income NaN {df.income.isna().sum()}")

    P = oof_predictions(df, SCALE_FREE_FEATURES, y, make=make_catboost, n_repeats=N_REPEATS)
    cv_auroc = float(np.mean([roc_auc_score(y, p) for p in P]))
    d21 = pd.read_csv(ROOT / "results" / "d21_scale_free.csv").set_index("model").loc["CatBoost"]
    if not np.isclose(cv_auroc, d21.auroc_scale_free, rtol=0, atol=1e-9):
        sys.exit(f"CV AUROC {cv_auroc:.6f} does not reproduce results/d21_scale_free.csv "
                 f"({d21.auroc_scale_free:.6f}); not writing an artifact")
    print(f"CV AUROC {cv_auroc:.4f} reproduces results/d21_scale_free.csv")

    out = ROOT / "models" / MODEL_VERSION
    meta = build_artifact(
        X, y, out_dir=out, model_version=MODEL_VERSION, reference_scores=P.mean(0),
        band_cutoffs=BAND_CUTOFFS, git_commit=git_commit(),
        training_data={
            "dataset": "Berka / PKDD'99 Czech bank (public)",
            "loans": int(len(df)), "defaults": int(y.sum()),
            "income_missing": int(df.income.isna().sum()),
            "window_months": WINDOW_MONTHS,
            "window": "transactions strictly before the loan date (D3)",
            "label": "default = loan status B or D (D2)",
        },
        metrics={
            "source": "results/d21_scale_free.csv (CatBoost)",
            "cv": "repeated stratified 5-fold, 10 repeats, seed 42 (D13, D21)",
            "cv_auroc": float(d21.auroc_scale_free),
            "cv_auroc_research_transactions": float(d21.auroc_transactions),
            "paired_diff_vs_research_transactions": float(d21["diff"]),
            "paired_diff_ci95": [float(d21.lo), float(d21.hi)],
        },
    )
    again = predictions_digest(make_catboost(SCALE_FREE_FEATURES).fit(X, y).predict_proba(X)[:, 1])
    if again != meta["training_predictions_sha256"]:
        sys.exit("two fits of the final model predict differently: training is not deterministic")
    print(f"deterministic: training predictions sha256 {again[:16]}...")
    print(f"wrote {out.relative_to(ROOT)} (git {meta['git_commit']})")


if __name__ == "__main__":
    main()
