"""Observation window: keep only transactions strictly before each loan date."""
import pandas as pd


def parse_berka_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str).str[:6], format="%y%m%d")


def observation_window(loans: pd.DataFrame, trans: pd.DataFrame, months: int = 3) -> pd.DataFrame:
    """Return transactions in [loan_date - months, loan_date) for each loan.

    loans needs: loan_id, account_id, loan_date
    trans needs: account_id, trans_date
    Transactions ON the loan date are excluded, so nothing from the
    loan's own life can leak into features.
    """
    m = trans.merge(loans[["loan_id", "account_id", "loan_date"]], on="account_id", how="inner")
    start = m["loan_date"] - pd.DateOffset(months=months)
    keep = (m["trans_date"] >= start) & (m["trans_date"] < m["loan_date"])
    out = m.loc[keep].copy()
    out["window_start"] = start[keep]
    return out.reset_index(drop=True)
