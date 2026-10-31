"""Application features: what a lender knows at application time, without the transaction history.

Excluded on purpose: sex and birth date (spec FR-01), and anything dated on/after the loan date.
"""
import numpy as np
import pandas as pd

DISTRICT_COLS = {
    "A4": "district_population",
    "A10": "district_urban_ratio",
    "A11": "district_avg_salary",
    "A13": "district_unemployment_96",
    "A14": "district_entrepreneurs_per_1000",
}
FREQ = {"POPLATEK MESICNE": "monthly", "POPLATEK TYDNE": "weekly", "POPLATEK PO OBRATU": "after_transaction"}


def build_application_features(loans, accounts, disp, cards, districts) -> pd.DataFrame:
    """One row per loan. Dates must already be parsed: loan_date, account_date, card_issued."""
    df = loans[["loan_id", "account_id", "loan_date", "amount", "duration", "payments"]].rename(
        columns={"amount": "loan_amount", "duration": "loan_duration_months", "payments": "monthly_payment"})

    acc = accounts[["account_id", "district_id", "frequency", "account_date"]]
    df = df.merge(acc, on="account_id", how="left")
    df["account_age_days"] = (df["loan_date"] - df["account_date"]).dt.days
    df["statement_frequency"] = df["frequency"].map(FREQ)

    # Joint account: more than one person attached to the account
    n_people = disp.groupby("account_id").size().rename("n_account_holders")
    df = df.merge(n_people, on="account_id", how="left")
    df["is_joint_account"] = (df["n_account_holders"] > 1).astype(int)

    # Card held BEFORE the loan date only (a card issued later is future information)
    c = cards.merge(disp[["disp_id", "account_id"]], on="disp_id").merge(df[["account_id", "loan_date"]], on="account_id")
    c = c[c["card_issued"] < c["loan_date"]]
    df["has_card_before_loan"] = df["account_id"].isin(c["account_id"]).astype(int)

    d = districts.rename(columns={"A1": "district_id", **DISTRICT_COLS})[["district_id", *DISTRICT_COLS.values()]]
    d = d.replace("?", np.nan).astype(float).astype({"district_id": int})
    df = df.merge(d, on="district_id", how="left")

    cols = ["loan_id", "loan_amount", "loan_duration_months", "monthly_payment", "account_age_days",
            "statement_frequency", "is_joint_account", "has_card_before_loan", *DISTRICT_COLS.values()]
    return df[cols].sort_values("loan_id").reset_index(drop=True)
