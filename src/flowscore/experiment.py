"""RQ1: application-only vs transaction-only vs combined, logistic regression.

Evaluation: repeated stratified 5-fold CV. Every preprocessing step lives inside the
pipeline, so it is fitted on training folds only.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

APP = ["loan_amount", "loan_duration_months", "monthly_payment", "account_age_days",
       "statement_frequency", "has_card_before_loan", "district_population",
       "district_urban_ratio", "district_avg_salary", "district_unemployment_96",
       "district_entrepreneurs_per_1000"]
TX = ["avg_monthly_inflow", "inflow_cv", "avg_daily_balance", "min_balance", "days_negative_balance",
      "penalty_interest_count", "months_net_outflow", "outflow_inflow_ratio", "tx_count"]
MONEY = {"loan_amount", "monthly_payment", "district_population", "district_avg_salary",
         "avg_monthly_inflow"}   # strictly positive amounts only; balances can go negative
CATEGORICAL = {"statement_frequency"}
# Excluded from main results: disp table has no dates, so we cannot verify the second
# account holder was added before the loan (145 joint accounts, 0 defaults). Sensitivity check only.
UNVERIFIED_TIMING = ["is_joint_account"]

CONFIGS = {"A: application only": APP, "B: transactions only": TX, "C: combined": APP + TX}

log1p = FunctionTransformer(np.log1p, feature_names_out="one-to-one")


def preprocessor(cols):
    cat = [c for c in cols if c in CATEGORICAL]
    money = [c for c in cols if c in MONEY]
    other = [c for c in cols if c not in CATEGORICAL | MONEY]
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat),
        ("money", make_pipeline(SimpleImputer(strategy="median"), log1p, StandardScaler()), money),
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), other),
    ])
    return pre


def make_lr(cols, C=1.0):
    return make_pipeline(preprocessor(cols), LogisticRegression(C=C, max_iter=2000))


def make_rf(cols):
    from sklearn.ensemble import RandomForestClassifier
    return make_pipeline(preprocessor(cols), RandomForestClassifier(
        n_estimators=500, min_samples_leaf=5, n_jobs=-1, random_state=0))


def make_catboost(cols):
    from catboost import CatBoostClassifier
    return make_pipeline(preprocessor(cols), CatBoostClassifier(
        iterations=500, depth=4, learning_rate=0.03, verbose=0, random_seed=0, thread_count=-1, allow_writing_files=False))


MODELS = {"Logistic regression": make_lr, "Random forest": make_rf, "CatBoost": make_catboost}


def oof_predictions(df, cols, y, make=make_lr, n_splits=5, n_repeats=20, seed=42):
    """Out-of-fold PD for every loan, once per repeat. Shape: (n_repeats, n_loans)."""
    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    P = np.zeros((n_repeats, len(df)))
    for i, (tr, te) in enumerate(cv.split(df, y)):
        m = make(cols).fit(df.iloc[tr][cols], y[tr])
        P[i // n_splits, te] = m.predict_proba(df.iloc[te][cols])[:, 1]
    return P


def bootstrap_ci(y, p, metric, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].min() == y[idx].max():
            continue
        vals.append(metric(y[idx], p[idx]))
    return np.percentile(vals, [2.5, 97.5])


def calibrated(make):
    """Platt scaling fitted on inner folds of the training data only."""
    from sklearn.calibration import CalibratedClassifierCV
    return lambda cols: CalibratedClassifierCV(make(cols), method="sigmoid", cv=3)
