"""Run the FlowScore features on your own parsed statements. LOCAL USE ONLY.

    python tools/personal_features.py personal/transactions.csv

For the 1st of each month in your history: the 9 research features (3-month window before that
date), the obligation features (debt, rent, reimbursements, fees) and the 12-month salary
baseline. All come from flowscore.features.cashflow, the same code the app will use.
Prints a table and writes personal/features_by_month.csv. Nothing leaves your machine.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flowscore.features.cashflow import features_as_of, monthly_salary  # noqa: E402
from flowscore.schema import DATE, ordered, validate  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--months", type=int, default=3)
    ap.add_argument("--out", default="personal/features_by_month.csv")
    args = ap.parse_args()

    tx = ordered(pd.read_csv(args.csv, parse_dates=[DATE])).reset_index(drop=True)
    errors = validate(tx)
    if errors:
        sys.exit("Transactions file problems: " + "; ".join(errors))
    first, last = tx[DATE].min(), tx[DATE].max()

    # one "as of" date per month: the 1st of each month with a full window behind it
    asof = pd.date_range(first.normalize() + pd.DateOffset(months=args.months), last + pd.Timedelta(days=1), freq="MS")
    if len(asof) == 0:
        sys.exit(f"Need at least {args.months} months of history; have {first.date()} to {last.date()}.")

    monthly = monthly_salary(tx)
    out = pd.DataFrame([{"as_of": d.date(), **features_as_of(tx, d, args.months, monthly)} for d in asof])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    pd.set_option("display.width", 200)
    print(f"Features over a {args.months}-month window, as of the 1st of each month "
          f"({first.date()} to {last.date()} history):\n")
    print(out.set_index("as_of").T.round(2).to_string())
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
