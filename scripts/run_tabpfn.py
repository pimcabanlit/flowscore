"""RQ2 add-on: TabPFN on the same folds as LR / RF / CatBoost.

Run:  python scripts/run_tabpfn.py            (10 repeats, matches run_research.py)
      python scripts/run_tabpfn.py --repeats 2 (quick check)
Needs: pip install tabpfn, Hugging Face terms accepted + `hf auth login`.
Writes results/rq2_tabpfn.csv
"""
import argparse, sys, time, warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import make_pipeline

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flowscore.experiment import CONFIGS, preprocessor, make_lr, make_catboost  # noqa: E402

warnings.filterwarnings("ignore")


def make_tabpfn(cols):
    from tabpfn import TabPFNClassifier
    return make_pipeline(preprocessor(cols), TabPFNClassifier(device="cpu", random_state=0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true", help="use logistic regression to test the plumbing")
    args = ap.parse_args()
    make = make_lr if args.dry_run else make_tabpfn
    name = "LR (dry run)" if args.dry_run else "TabPFN"

    df = pd.read_csv("results/features.csv")   # written by run_research.py
    y = df["bad"].to_numpy()
    rng = np.random.default_rng(0)
    B = [b for b in (rng.integers(0, len(y), len(y)) for _ in range(2000)) if 0 < y[b].sum() < len(b)]

    rows, n_fits, OOF = [], 5 * args.repeats * len(CONFIGS), {}
    t0, done = time.time(), 0
    for cname, cols in CONFIGS.items():
        cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=args.repeats, random_state=42)  # same seed as run_research.py
        P = np.zeros((args.repeats, len(df)))
        for i, (tr, te) in enumerate(cv.split(df, y)):
            m = make(cols).fit(df.iloc[tr][cols], y[tr])
            P[i // 5, te] = m.predict_proba(df.iloc[te][cols])[:, 1]
            done += 1
            if done == 1 or done % 10 == 0:
                el = time.time() - t0
                print(f"  fit {done}/{n_fits}  elapsed {el/60:.1f} min  est. left {el/done*(n_fits-done)/60:.1f} min", flush=True)
        OOF[cname] = P
        pm = P.mean(0)
        boot = [roc_auc_score(y[b], pm[b]) for b in B]
        rows.append(dict(model=name, config=cname,
                         AUROC=np.mean([roc_auc_score(y, r) for r in P]),
                         lo=np.percentile(boot, 2.5), hi=np.percentile(boot, 97.5),
                         PR_AUC=np.mean([average_precision_score(y, r) for r in P]),
                         Brier=np.mean([brier_score_loss(y, r) for r in P])))
        print(f"{name} | {cname}: AUROC {rows[-1]['AUROC']:.3f}", flush=True)

    out = pd.DataFrame(rows)
    print("\n", out.round(3).to_string(index=False))

    # Paired comparison against LR and CatBoost on the SAME folds and loans
    print("\n== Paired AUROC differences, 95% bootstrap CI")
    lines = []
    for cname in ["B: transactions only", "C: combined"]:
        cols = CONFIGS[cname]
        cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=args.repeats, random_state=42)
        refs = {"Logistic regression": make_lr, "CatBoost": make_catboost}
        for rname, rmake in refs.items():
            R = np.zeros((args.repeats, len(df)))
            for i, (tr, te) in enumerate(cv.split(df, y)):
                R[i // 5, te] = rmake(cols).fit(df.iloc[tr][cols], y[tr]).predict_proba(df.iloc[te][cols])[:, 1]
            a, b = OOF[cname].mean(0), R.mean(0)
            d = np.array([roc_auc_score(y[i], a[i]) - roc_auc_score(y[i], b[i]) for i in B])
            line = dict(config=cname, comparison=f"{name} - {rname}", diff=d.mean(),
                        lo=np.percentile(d, 2.5), hi=np.percentile(d, 97.5))
            lines.append(line)
            print(f"{cname:22s} {name} - {rname:20s} {d.mean():+.3f} [{line['lo']:+.3f}, {line['hi']:+.3f}]", flush=True)

    if not args.dry_run:
        out.to_csv("results/rq2_tabpfn.csv", index=False)
        pd.DataFrame(lines).to_csv("results/rq2_tabpfn_paired.csv", index=False)
        np.save("results/tabpfn_oof_combined.npy", OOF["C: combined"])


if __name__ == "__main__":
    main()
