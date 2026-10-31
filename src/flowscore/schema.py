"""The canonical transaction schema (spec FR-02 B) that every feature function works on.

Any data source (Berka, a BPI statement, the app's upload) is converted into this shape first.
"""
import pandas as pd

ID, DATE, DEBIT, CREDIT, BALANCE, CATEGORY = (
    "transaction_id", "transaction_date", "debit_amount", "credit_amount", "running_balance", "transaction_category")
REQUIRED = [ID, DATE, DEBIT, CREDIT, BALANCE, CATEGORY]

# Category vocabulary. Unknown categories are allowed (they count as plain inflow/outflow).
INCOME = {"salary", "pension", "deposit", "transfer_in", "other_in"}
NON_INCOME_CREDITS = {"interest", "reimbursement"}   # money in that is not the borrower's earnings
DEBT = {"credit_card_payment", "loan_payment"}
FIXED = DEBT | {"rent"}
PENALTY = "penalty_interest"                           # bank charge for an overdraft
CATEGORIES = INCOME | NON_INCOME_CREDITS | FIXED | {
    PENALTY, "bills", "insurance", "fee", "tax", "card_purchase", "cash_withdrawal",
    "transfer_out", "phone_load", "household", "other_out"}

# Credits excluded from the research feature "avg_monthly_inflow". Kept identical to the
# Berka study (only bank interest), so research results do not move; reimbursements are
# handled separately by the obligation features.
EXCLUDED_FROM_INFLOW = {"interest"}


def validate(tx: pd.DataFrame) -> list:
    """Errors that make a transaction table unusable. Empty list = OK."""
    errors = [f"missing column: {c}" for c in REQUIRED if c not in tx.columns]
    if errors:
        return errors
    if not pd.api.types.is_datetime64_any_dtype(tx[DATE]):
        errors.append(f"{DATE} must be a datetime column")
    debit, credit = tx[DEBIT].fillna(0), tx[CREDIT].fillna(0)
    if (debit < 0).any() or (credit < 0).any():
        errors.append("negative debit or credit amounts")
    if ((debit > 0) & (credit > 0)).any():
        errors.append("rows with both a debit and a credit")
    if tx[ID].duplicated().any():
        errors.append("duplicate transaction ids")
    return errors


def ordered(tx: pd.DataFrame) -> pd.DataFrame:
    """Chronological order; ties broken by transaction id (the statement's own order)."""
    return tx.sort_values([DATE, ID], kind="stable")
