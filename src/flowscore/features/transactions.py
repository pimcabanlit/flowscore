"""Berka entry points for the transaction features, kept for the research scripts.

The feature logic lives in flowscore.features.cashflow (canonical schema). These functions only
translate Berka rows with flowscore.adapters.berka and call it, so research results are unchanged.
"""
import pandas as pd

from flowscore.adapters.berka import to_canonical
from flowscore.features.cashflow import WINDOW_FEATURES, opening_balance, window_features, window_slice
from flowscore.schema import ordered

FEATURES = WINDOW_FEATURES


def loan_features(tx: pd.DataFrame, loan_date: pd.Timestamp, opening_balance: float, months: int = 3) -> dict:
    """Features for ONE loan from its Berka-coded window transactions (may be empty)."""
    return window_features(to_canonical(tx), loan_date, opening_balance, months)


def build_transaction_features(loans: pd.DataFrame, trans: pd.DataFrame, months: int = 3) -> pd.DataFrame:
    """One row per loan. loans: loan_id, account_id, loan_date. trans: full Berka table with trans_date."""
    canon = to_canonical(trans[trans["account_id"].isin(loans["account_id"])])
    by_account = {a: ordered(g) for a, g in canon.groupby("account_id")}
    empty = canon.iloc[0:0]
    rows = []
    for r in loans.itertuples():
        hist = by_account.get(r.account_id, empty)
        start = r.loan_date - pd.DateOffset(months=months)
        f = window_features(window_slice(hist, r.loan_date, months), r.loan_date,
                            opening_balance(hist, start) if len(hist[hist["transaction_date"] < start]) else 0.0,
                            months)
        rows.append({"loan_id": r.loan_id, **f})
    return pd.DataFrame(rows).sort_values("loan_id").reset_index(drop=True)
