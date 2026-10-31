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
    rent = outflow[w["transaction_category"] == "rent"].sum()
    reimb = inflow[w["transaction_category"] == "reimbursement"].sum()
    return {
        "salary_share_of_inflow": salary / inflow.sum() if inflow.sum() else np.nan,
        "debt_service_ratio": debt / salary if salary else np.nan,        # card/loan payments / salary
        "fixed_obligation_ratio": (debt + rent) / salary if salary else np.nan,  # debt + rent / salary
        # same as debt_service_ratio, minus money others sent back for things on your card (tag senders
        # as 'reimbursement' in personal/category_rules.csv). Conservative view = debt_service_ratio.
        "net_debt_service_ratio": max(debt - reimb, 0.0) / salary if salary else np.nan,
        "reimbursements_per_month": reimb / months,
        "fees_per_month": fees / months,
        "card_purchases_per_month": (w["transaction_category"] == "card_purchase").sum() / months,
        "salary_credits": int((w["transaction_category"] == "salary").sum()),
    }


def monthly_salary(tx: pd.DataFrame) -> pd.Series:
    """Salary per calendar month, only for months fully covered by the statements (zero-pay months stay 0)."""
    first, last = tx["transaction_date"].min(), tx["transaction_date"].max()
    months = pd.period_range(first, last, freq="M")
    covered = [m for m in months if m.start_time >= first.normalize() and m.end_time.normalize() <= last.normalize()]
    sal = tx[tx["transaction_category"] == "salary"]
    totals = sal.groupby(sal["transaction_date"].dt.to_period("M"))["credit_amount"].sum()
    return pd.Series({m: float(totals.get(m, 0.0)) for m in covered})


def baseline_features(monthly: pd.Series, as_of, w: pd.DataFrame, window_months: int,
                      lookback=12, min_months=3) -> dict:
    """Steadier income: median monthly salary over up to 12 full months BEFORE as_of.

    A median ignores one bonus month or one short month, so ratios built on it don't jump
    because of where the window happens to fall. Missing (NaN) until 3 full months exist.
    """
    past = monthly[[m for m in monthly.index if m.end_time < pd.Timestamp(as_of)]].tail(lookback)
    base = float(past.median()) if len(past) >= min_months else np.nan
    debt_m = w["debit_amount"].fillna(0)[w["transaction_category"].isin(DEBT)].sum() / window_months
    reimb_m = w["credit_amount"].fillna(0)[w["transaction_category"] == "reimbursement"].sum() / window_months
    ok = base == base and base > 0
    return {
        "salary_baseline_monthly": base,
        "salary_baseline_months_used": len(past),
        "debt_service_ratio_baseline": debt_m / base if ok else np.nan,
        "net_debt_service_ratio_baseline": max(debt_m - reimb_m, 0.0) / base if ok else np.nan,
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
    monthly = monthly_salary(tx)
    rows = []
    for d in asof:
        start = d - pd.DateOffset(months=args.months)
        mask = (tx["transaction_date"] >= start) & (tx["transaction_date"] < d)
        f = loan_features(berka[mask.values], d, opening_balance(tx, start), args.months)
        rows.append({"as_of": d.date(), **f, **ph_extras(tx[mask], args.months),
                     **baseline_features(monthly, d, tx[mask], args.months)})
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
