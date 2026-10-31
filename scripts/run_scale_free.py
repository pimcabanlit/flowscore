"""D21: AUROC cost of the scale-free app feature set vs the research transaction set, on Berka.

Same folds as run_research.py (RepeatedStratifiedKFold, 5 x 10, seed 42) and the same 2000
bootstrap resamples (seed 0), so the difference is paired loan by loan.
Run: PYTHONPATH=src python scripts/run_scale_free.py   (~2 min; needs data/raw/)
Writes results/d21_scale_free.csv. Does not touch any other results file.
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from flowscore.data import load_berka
from flowscore.experiment import TX, make_catboost, make_lr, oof_predictions
from flowscore.features.cashflow import SCALE_FREE_FEATURES
from flowscore.features.transactions import build_transaction_features

warnings.filterwarnings("ignore")

t = load_berka("data/raw/")
tx = build_transaction_features(t["loan"], t["trans"], months=3)
sf = build_transaction_features(t["loan"], t["trans"], months=3, scale_free=True)
sf = sf.drop(columns=[c for c in SCALE_FREE_FEATURES if c in tx.columns])   # identical columns, keep one copy
df = tx.merge(sf, on="loan_id").merge(t["loan"][["loan_id", "bad"]], on="loan_id").sort_values("loan_id")
df = df.reset_index(drop=True)
y = df.bad.to_numpy(); R = 10
rng = np.random.default_rng(0)
B = [b for b in (rng.integers(0, len(y), len(y)) for _ in range(2000)) if 0 < y[b].sum() < len(b)]

print(f"loans {len(df)}, defaults {y.sum()}, income NaN {df.income.isna().sum()}")
rows = []
for name, mk in {"CatBoost": make_catboost, "Logistic regression": make_lr}.items():
    P_tx = oof_predictions(df, TX, y, make=mk, n_repeats=R)
    P_sf = oof_predictions(df, SCALE_FREE_FEATURES, y, make=mk, n_repeats=R)
    auc = lambda P: np.mean([roc_auc_score(y, p) for p in P])     # as in results/rq1_rq2.csv
    p_tx, p_sf = P_tx.mean(0), P_sf.mean(0)                     # paired test as in run_research.paired
    d = np.array([roc_auc_score(y[b], p_sf[b]) - roc_auc_score(y[b], p_tx[b]) for b in B])
    rows.append(dict(model=name, auroc_transactions=auc(P_tx), auroc_scale_free=auc(P_sf), diff=d.mean(),
                     lo=np.percentile(d, 2.5), hi=np.percentile(d, 97.5)))
    r = rows[-1]
    print(f"{name:20s} TX {r['auroc_transactions']:.3f}  scale-free {r['auroc_scale_free']:.3f}  "
          f"diff {r['diff']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]", flush=True)
pd.DataFrame(rows).to_csv("results/d21_scale_free.csv", index=False)
