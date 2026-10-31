"""Transaction features from the pre-loan observation window.

Berka codes:  type PRIJEM = credit;  VYDAJ / VYBER = debit.
              k_symbol UROK = bank interest credited (NOT treated as income)
              k_symbol SANKC. UROK = penalty interest for a negative balance.
All features use only transactions in [loan_date - months, loan_date).
"""
import numpy as np
import pandas as pd

FEATURES = ["avg_monthly_inflow", "inflow_cv", "avg_daily_balance", "min_balance",
            "days_negative_balance", "penalty_interest_count", "months_net_outflow",
            "outflow_inflow_ratio", "tx_count"]


def _signed(tx: pd.DataFrame) -> pd.DataFrame:
    tx = tx.copy()
    k = tx["k_symbol"].fillna("").str.strip()
    tx["is_credit"] = tx["type"].eq("PRIJEM")
    tx["is_interest"] = k.eq("UROK")
    tx["is_penalty"] = k.eq("SANKC. UROK")
    tx["inflow"] = np.where(tx["is_credit"] & ~tx["is_interest"], tx["amount"], 0.0)
    tx["outflow"] = np.where(~tx["is_credit"], tx["amount"], 0.0)
    return tx


def loan_features(tx: pd.DataFrame, loan_date: pd.Timestamp, opening_balance: float, months: int = 3) -> dict:
    """Features for ONE loan. tx = that loan's window transactions (may be empty).

    opening_balance = account balance just before the window starts.
    """
    tx = _signed(tx).sort_values(["trans_date", "trans_id"]) if len(tx) else _signed(tx)
    start = loan_date - pd.DateOffset(months=months)

    # Month buckets counted back from the loan date: 0 = most recent month
    edges = [loan_date - pd.DateOffset(months=k) for k in range(months + 1)]
    inflow_m, outflow_m = [], []
    for k in range(months):
        m = (tx["trans_date"] >= edges[k + 1]) & (tx["trans_date"] < edges[k]) if len(tx) else []
        inflow_m.append(float(tx.loc[m, "inflow"].sum()) if len(tx) else 0.0)
        outflow_m.append(float(tx.loc[m, "outflow"].sum()) if len(tx) else 0.0)
    inflow_m, outflow_m = np.array(inflow_m), np.array(outflow_m)

    # Daily end-of-day balance, carried forward from the opening balance
    days = pd.date_range(start, loan_date - pd.Timedelta(days=1), freq="D")
    eod = tx.groupby("trans_date")["balance"].last() if len(tx) else pd.Series(dtype=float)
    daily = eod.reindex(days).ffill().fillna(opening_balance)
    all_balances = np.concatenate([[opening_balance], tx["balance"].to_numpy() if len(tx) else []])

    mean_in = inflow_m.mean()
    return {
        "avg_monthly_inflow": mean_in,
        "inflow_cv": inflow_m.std() / mean_in if mean_in > 0 else np.nan,   # undefined, not zero
        "avg_daily_balance": daily.mean(),
        "min_balance": all_balances.min(),                                  # includes intraday lows
        "days_negative_balance": int((daily < 0).sum()),
        "penalty_interest_count": int(tx["is_penalty"].sum()) if len(tx) else 0,
        "months_net_outflow": int((outflow_m > inflow_m).sum()),
        "outflow_inflow_ratio": outflow_m.sum() / inflow_m.sum() if inflow_m.sum() > 0 else np.nan,
        "tx_count": len(tx),
    }


def build_transaction_features(loans: pd.DataFrame, trans: pd.DataFrame, months: int = 3) -> pd.DataFrame:
    """One row per loan. loans: loan_id, account_id, loan_date. trans: full table with trans_date."""
    t = trans.merge(loans[["loan_id", "account_id", "loan_date"]], on="account_id")
    t["start"] = t["loan_date"] - pd.DateOffset(months=months)
    before = t[t["trans_date"] < t["start"]].sort_values(["trans_date", "trans_id"])
    opening = before.groupby("loan_id")["balance"].last()
    window = t[(t["trans_date"] >= t["start"]) & (t["trans_date"] < t["loan_date"])]
    groups = dict(tuple(window.groupby("loan_id")))
    rows = []
    for r in loans.itertuples():
        tx = groups.get(r.loan_id, window.iloc[0:0])
        rows.append({"loan_id": r.loan_id, **loan_features(tx, r.loan_date, opening.get(r.loan_id, 0.0), months)})
    return pd.DataFrame(rows).sort_values("loan_id").reset_index(drop=True)
