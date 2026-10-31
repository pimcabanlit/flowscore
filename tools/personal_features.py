"""Run the FlowScore transaction features on your own parsed statements. LOCAL USE ONLY.

    python tools/personal_features.py personal/transactions.csv

Computes, for each month-end in your history, the same 9 features used on Berka (3-month window
before that date), plus Philippine-specific extras the BPI categories make possible.
Prints a table and writes personal/features_by_month.csv. Nothing leaves your machine.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flowscore.features.transactions import loan_features  # noqa: E402

DEBT = {"credit_card_payment", "loan_payment"}


def to_berka_shape(tx: pd.DataFrame) -> pd.DataFrame:
    """Adapter: FlowScore schema -> the columns loan_features() expects."""
    credit = tx["credit_amount"].fillna(0) > 0
    return pd.DataFrame({
        "trans_id": np.arange(len(tx)),
        "trans_date": tx["transaction_date"],
        "type": np.where(credit, "PRIJEM", "VYDAJ"),
        "amount": np.where(credit, tx["credit_amount"].fillna(0), tx["debit_amount"].fillna(0)),
        "balance": tx["running_balance"],
        # bank interest is not income (same rule as Berka); no penalty-interest code in BPI data
        "k_symbol": np.where(tx["transaction_category"] == "interest", "UROK", ""),
    })


def opening_balance(tx: pd.DataFrame, start) -> float:
    before = tx[tx["transaction_date"] < start]
    if len(before):
        return float(before["running_balance"].iloc[-1])
    first = tx.iloc[0]                       # undo the first transaction
    return float(first["running_balance"] - (first["credit_amount"] or 0) + (first["debit_amount"] or 0))


def ph_extras(w: pd.DataFrame, months: int) -> dict:
    """Features Berka could not provide, from the BPI categories."""
    inflow = w["credit_amount"].fillna(0)
    outflow = w["debit_amount"].fillna(0)
    salary = inflow[w["transaction_category"] == "salary"].sum()
    debt = outflow[w["transaction_category"].isin(DEBT)].sum()
    fees = outflow[w["transaction_category"] == "fee"].sum()
    return {
        "salary_share_of_inflow": salary / inflow.sum() if inflow.sum() else np.nan,
        "debt_service_ratio": debt / salary if salary else np.nan,        # card/loan payments / salary
        "fees_per_month": fees / months,
        "card_purchases_per_month": (w["transaction_category"] == "card_purchase").sum() / months,
        "salary_credits": int((w["transaction_category"] == "salary").sum()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--months", type=int, default=3)
    ap.add_argument("--out", default="personal/features_by_month.csv")
    args = ap.parse_args()

    tx = pd.read_csv(args.csv, parse_dates=["transaction_date"])
    tx = tx.sort_values(["transaction_date", "transaction_id"]).reset_index(drop=True)
    first, last = tx["transaction_date"].min(), tx["transaction_date"].max()

    # one "as of" date per month: the 1st of each month with a full window behind it
    asof = pd.date_range(first.normalize() + pd.DateOffset(months=args.months), last + pd.Timedelta(days=1), freq="MS")
    if len(asof) == 0:
        sys.exit(f"Need at least {args.months} months of history; have {first.date()} to {last.date()}.")

    berka = to_berka_shape(tx)
    rows = []
    for d in asof:
        start = d - pd.DateOffset(months=args.months)
        mask = (tx["transaction_date"] >= start) & (tx["transaction_date"] < d)
        f = loan_features(berka[mask.values], d, opening_balance(tx, start), args.months)
        rows.append({"as_of": d.date(), **f, **ph_extras(tx[mask], args.months)})
    out = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    pd.set_option("display.width", 200)
    show = out.set_index("as_of").T
    print(f"Features over a {args.months}-month window, as of the 1st of each month "
          f"({first.date()} to {last.date()} history):\n")
    print(show.round(2).to_string())
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
