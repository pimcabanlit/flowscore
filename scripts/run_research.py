"""Reproduce all research results (RQ1, RQ2, RQ3/4, RQ5) on Berka. Run: PYTHONPATH=src python scripts/run_research.py"""
import pickle, warnings
import numpy as np, pandas as pd, shap
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, log_loss
from flowscore.experiment import CONFIGS, MODELS, UNVERIFIED_TIMING, oof_predictions, calibrated, make_lr, make_catboost
warnings.filterwarnings("ignore")

from flowscore.data import load_berka
from flowscore.features.application import build_application_features
from flowscore.features.transactions import build_transaction_features

# ---- Build features from the raw CSVs ----
t = load_berka("data/raw/")
app = build_application_features(t["loan"], t["account"], t["disp"], t["card"], t["district"])
tx = build_transaction_features(t["loan"], t["trans"], months=3)
df = app.merge(tx, on="loan_id").merge(t["loan"][["loan_id", "bad"]], on="loan_id")
df.to_csv("results/features.csv", index=False)
y = df.bad.to_numpy(); R = 10
rng = np.random.default_rng(0)
B = [b for b in (rng.integers(0, len(y), len(y)) for _ in range(2000)) if 0 < y[b].sum() < len(b)]

def summary(p):
    pm = p.mean(0); boot = [roc_auc_score(y[b], pm[b]) for b in B]
    return dict(AUROC=np.mean([roc_auc_score(y, r) for r in p]), lo=np.percentile(boot, 2.5), hi=np.percentile(boot, 97.5),
                PR_AUC=np.mean([average_precision_score(y, r) for r in p]), Brier=np.mean([brier_score_loss(y, r) for r in p]))

def paired(pa, pb):
    a, b = pa.mean(0), pb.mean(0); d = np.array([roc_auc_score(y[i], a[i]) - roc_auc_score(y[i], b[i]) for i in B])
    return f"{d.mean():+.3f} [{np.percentile(d, 2.5):+.3f}, {np.percentile(d, 97.5):+.3f}]"

# ---- RQ1 + RQ2 ----
P = {(m, c): oof_predictions(df, cols, y, make=mk, n_repeats=R) for m, mk in MODELS.items() for c, cols in CONFIGS.items()}
res = pd.DataFrame([dict(model=m, config=c, **summary(p)) for (m, c), p in P.items()])
res.to_csv("results/rq1_rq2.csv", index=False)
print("== RQ1/RQ2: AUROC by model and feature set\n", res.round(3).to_string(index=False))
print("\n== Paired differences (AUROC, 95% CI)")
for m in MODELS:
    print(f"{m:20s} B−A {paired(P[(m,'B: transactions only')], P[(m,'A: application only')])}   C−B {paired(P[(m,'C: combined')], P[(m,'B: transactions only')])}")
for m in ["Random forest", "CatBoost"]:
    print(f"{m} − LR (combined): {paired(P[(m,'C: combined')], P[('Logistic regression','C: combined')])}")

# Sensitivity: add back the unverified-timing feature
print("\n== Sensitivity: + is_joint_account")
for c in ["A: application only", "C: combined"]:
    s = summary(oof_predictions(df, CONFIGS[c] + UNVERIFIED_TIMING, y, n_repeats=R))
    print(f"LR {c}: {s['AUROC']:.3f}  (main: {res.query('model==\"Logistic regression\" and config==@c').AUROC.iloc[0]:.3f})")

# ---- RQ5 calibration ----
def calib(p):
    p = np.clip(p, 1e-4, 1 - 1e-4); lp = np.log(p / (1 - p)).reshape(-1, 1)
    slope = LogisticRegression(C=1e6).fit(lp, y).coef_[0, 0]
    t = pd.DataFrame({"q": pd.qcut(p, 5, labels=False), "p": p, "y": y}).groupby("q").agg(pred=("p", "mean"), obs=("y", "mean"), n=("y", "size"))
    return dict(mean_PD=p.mean(), Brier=brier_score_loss(y, p), log_loss=log_loss(y, p), slope=slope,
                ECE=(abs(t.pred - t.obs) * t.n).sum() / len(y)), t
cal_rows, bins = [], {}
cols = CONFIGS["C: combined"]
for m, mk in [("Logistic regression", make_lr), ("CatBoost", make_catboost)]:
    raw = P[(m, "C: combined")][0]
    plt = oof_predictions(df, cols, y, make=calibrated(mk), n_repeats=1)[0]
    for tag, p in [("raw", raw), ("Platt", plt)]:
        r, t = calib(p); cal_rows.append(dict(model=m, version=tag, **r)); bins[(m, tag)] = t
cal = pd.DataFrame(cal_rows); cal.to_csv("results/rq5_calibration.csv", index=False)
print(f"\n== RQ5 calibration (combined; actual default rate {y.mean():.3f})\n", cal.round(3).to_string(index=False))
for k, t in bins.items(): print(k, "quintiles pred→obs:", " | ".join(f"{a:.3f}→{b:.3f}" for a, b in zip(t.pred, t.obs)))

# ---- RQ3/RQ4 SHAP ----
imp = {}
for m, mk in [("LR", make_lr), ("CatBoost", make_catboost)]:
    pipe = mk(cols).fit(df[cols], y); pre, clf = pipe[0], pipe[-1]
    X = pre.transform(df[cols]); names = [n.split("__", 1)[1] for n in pre.get_feature_names_out()]
    names = ["statement_frequency" if n.startswith("statement_frequency") else n for n in names]
    sv = (shap.LinearExplainer(clf, X) if m == "LR" else shap.TreeExplainer(clf)).shap_values(X)
    sv = sv if sv.ndim == 2 else sv[:, :, 1]
    imp[m] = pd.Series(np.abs(sv).mean(0), index=names).groupby(level=0).sum()
    if m == "LR": lr = dict(sv=sv, names=names)
imp = pd.DataFrame(imp); imp["source"] = ["transaction" if c in CONFIGS["B: transactions only"] else "application" for c in imp.index]
imp["LR_rank"] = imp.LR.rank(ascending=False).astype(int); imp["CB_rank"] = imp.CatBoost.rank(ascending=False).astype(int)
imp = imp.sort_values("CatBoost", ascending=False); imp.to_csv("results/rq3_shap_importance.csv")
print("\n== RQ3 SHAP importance (mean |SHAP|, log-odds)\n", imp.round(3).to_string())
print("Spearman rank agreement LR vs CatBoost:", round(spearmanr(imp.LR, imp.CatBoost)[0], 2))
for m in ["LR", "CatBoost"]:
    s = imp.groupby("source")[m].sum(); print(f"{m}: share of |SHAP| from transaction features = {s['transaction']/s.sum():.0%}")
i = int(np.argmax(lr["sv"].sum(1) * (y == 1)))
e = pd.Series(lr["sv"][i], index=lr["names"]).groupby(level=0).sum().sort_values(key=abs, ascending=False).head(5)
print(f"\nExample: loan {df.loan_id[i]} (defaulted), top LR contributions:")
for k, v in e.items(): print(f"  {k:28s} {v:+.2f}  value={df[k].iloc[i]}")
