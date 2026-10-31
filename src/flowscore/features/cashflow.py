"""Cash-flow features on the canonical transaction schema (flowscore.schema).

Three groups, all computed only from transactions in [as_of - months, as_of):

1. window_features      the 9 research features used in the Berka study
2. obligation_features  debt, rent, reimbursement and fee features (Philippine statements)
3. salary_baseline      a steadier income level: median monthly salary over prior full months

`features_as_of` runs all three for one account at one date.
"""
import numpy as np
import pandas as pd

from flowscore.schema import (BALANCE, CATEGORY, CREDIT, DATE, DEBIT, DEBT, EXCLUDED_FROM_INFLOW, PENALTY,
                              ordered)

WINDOW_FEATURES = ["avg_monthly_inflow", "inflow_cv", "avg_daily_balance", "min_balance",
                   "days_negative_balance", "penalty_interest_count", "months_net_outflow",
                   "outflow_inflow_ratio", "tx_count"]


# ---------------------------------------------------------------------------------------------
# helpers

def _amounts(tx: pd.DataFrame):
    return tx[CREDIT].fillna(0.0).astype(float), tx[DEBIT].fillna(0.0).astype(float)


def window_slice(tx: pd.DataFrame, as_of, months: int = 3) -> pd.DataFrame:
    """Transactions in [as_of - months, as_of). Nothing on or after as_of is ever used."""
    start = pd.Timestamp(as_of) - pd.DateOffset(months=months)
    return tx[(tx[DATE] >= start) & (tx[DATE] < pd.Timestamp(as_of))]


def opening_balance(tx: pd.DataFrame, start) -> float:
    """Balance just before `start`: the last running balance before it, else the first
    transaction's balance with that transaction undone. 0.0 if there are no transactions."""
    tx = ordered(tx)
    before = tx[tx[DATE] < pd.Timestamp(start)]
    if len(before):
        return float(before[BALANCE].iloc[-1])
    if not len(tx):
        return 0.0
    first = tx.iloc[0]
    credit = 0.0 if pd.isna(first[CREDIT]) else float(first[CREDIT])
    debit = 0.0 if pd.isna(first[DEBIT]) else float(first[DEBIT])
    return float(first[BALANCE]) - credit + debit


# ---------------------------------------------------------------------------------------------
# 1. research features

def window_features(window: pd.DataFrame, as_of, opening: float, months: int = 3) -> dict:
    """The 9 research features for ONE account. `window` = its transactions already cut to
    [as_of - months, as_of) (may be empty); `opening` = balance just before the window."""
    as_of = pd.Timestamp(as_of)
    tx = ordered(window) if len(window) else window
    credit, debit = _amounts(tx)
    inflow = credit.where(~tx[CATEGORY].isin(EXCLUDED_FROM_INFLOW), 0.0) if len(tx) else credit
    start = as_of - pd.DateOffset(months=months)

    # month buckets counted back from as_of: bucket 0 = the month just before it
    edges = [as_of - pd.DateOffset(months=k) for k in range(months + 1)]
    inflow_m = np.array([inflow[(tx[DATE] >= edges[k + 1]) & (tx[DATE] < edges[k])].sum() if len(tx) else 0.0
                         for k in range(months)], dtype=float)
    outflow_m = np.array([debit[(tx[DATE] >= edges[k + 1]) & (tx[DATE] < edges[k])].sum() if len(tx) else 0.0
                          for k in range(months)], dtype=float)

    # end-of-day balance carried forward over every day of the window
    days = pd.date_range(start, as_of - pd.Timedelta(days=1), freq="D")
    eod = tx.groupby(DATE)[BALANCE].last() if len(tx) else pd.Series(dtype=float)
    daily = eod.reindex(days).ffill().fillna(opening)
    balances = np.concatenate([[opening], tx[BALANCE].to_numpy(dtype=float) if len(tx) else []])

    mean_in = inflow_m.mean()
    return {
        "avg_monthly_inflow": mean_in,
        "inflow_cv": inflow_m.std() / mean_in if mean_in > 0 else np.nan,      # unknown, not zero
        "avg_daily_balance": daily.mean(),
        "min_balance": np.nanmin(balances),                                     # includes intraday lows
        "days_negative_balance": int((daily < 0).sum()),
        "penalty_interest_count": int((tx[CATEGORY] == PENALTY).sum()) if len(tx) else 0,
        "months_net_outflow": int((outflow_m > inflow_m).sum()),
        "outflow_inflow_ratio": outflow_m.sum() / inflow_m.sum() if inflow_m.sum() > 0 else np.nan,
        "tx_count": len(tx),
    }


# ---------------------------------------------------------------------------------------------
# 2. obligations

def obligation_features(window: pd.DataFrame, months: int = 3) -> dict:
    """Debt, rent, reimbursement and fee features for ONE account's window.

    debt_service_ratio      (credit card + loan payments) / salary      conservative lender view
    fixed_obligation_ratio  (debt payments + rent) / salary
    net_debt_service_ratio  (debt payments - reimbursements) / salary   'real burden' view
    """
    credit, debit = _amounts(window)
    cat = window[CATEGORY]
    salary = credit[cat == "salary"].sum()
    debt = debit[cat.isin(DEBT)].sum()
    rent = debit[cat == "rent"].sum()
    reimb = credit[cat == "reimbursement"].sum()
    fees = debit[cat == "fee"].sum()
    ratio = lambda num: num / salary if salary else np.nan
    return {
        "salary_share_of_inflow": salary / credit.sum() if credit.sum() else np.nan,
        "debt_service_ratio": ratio(debt),
        "fixed_obligation_ratio": ratio(debt + rent),
        "net_debt_service_ratio": ratio(max(debt - reimb, 0.0)),
        "reimbursements_per_month": reimb / months,
        "fees_per_month": fees / months,
        "card_purchases_per_month": int((cat == "card_purchase").sum()) / months,
        "salary_credits": int((cat == "salary").sum()),
    }


# ---------------------------------------------------------------------------------------------
# 3. salary baseline

def monthly_salary(tx: pd.DataFrame) -> pd.Series:
    """Salary per calendar month, for months FULLY covered by the history. Zero-pay months stay 0."""
    if not len(tx):
        return pd.Series(dtype=float)
    first, last = tx[DATE].min(), tx[DATE].max()
    covered = [m for m in pd.period_range(first, last, freq="M")
               if m.start_time >= first.normalize() and m.end_time.normalize() <= last.normalize()]
    sal = tx[tx[CATEGORY] == "salary"]
    totals = sal.groupby(sal[DATE].dt.to_period("M"))[CREDIT].sum()
    return pd.Series({m: float(totals.get(m, 0.0)) for m in covered}, dtype=float)


def salary_baseline(monthly: pd.Series, window: pd.DataFrame, as_of, months: int = 3,
                    lookback: int = 12, min_months: int = 3) -> dict:
    """Median monthly salary over up to `lookback` full months that END BEFORE as_of, and the
    debt ratios rebuilt on it. NaN until `min_months` full months exist."""
    past = monthly[[m for m in monthly.index if m.end_time < pd.Timestamp(as_of)]].tail(lookback)
    base = float(past.median()) if len(past) >= min_months else np.nan
    credit, debit = _amounts(window)
    cat = window[CATEGORY]
    debt_m = debit[cat.isin(DEBT)].sum() / months
    reimb_m = credit[cat == "reimbursement"].sum() / months
    ok = base == base and base > 0
    return {
        "salary_baseline_monthly": base,
        "salary_baseline_months_used": len(past),
        "debt_service_ratio_baseline": debt_m / base if ok else np.nan,
        "net_debt_service_ratio_baseline": max(debt_m - reimb_m, 0.0) / base if ok else np.nan,
    }


# ---------------------------------------------------------------------------------------------
# everything for one account at one date

def features_as_of(tx: pd.DataFrame, as_of, months: int = 3, monthly: pd.Series = None) -> dict:
    """All feature groups for ONE account's full history `tx`, as of `as_of`."""
    tx = ordered(tx)
    start = pd.Timestamp(as_of) - pd.DateOffset(months=months)
    w = window_slice(tx, as_of, months)
    monthly = monthly_salary(tx) if monthly is None else monthly
    return {**window_features(w, as_of, opening_balance(tx, start), months),
            **obligation_features(w, months),
            **salary_baseline(monthly, w, as_of, months)}
