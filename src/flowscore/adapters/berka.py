"""Berka/PKDD'99 transactions -> the canonical schema (flowscore.schema).

Berka codes:  type     PRIJEM = credit;  VYDAJ / VYBER = debit
              k_symbol UROK = bank interest, SANKC. UROK = overdraft penalty, UVER = loan payment,
                       SIPO = household bills, POJISTNE = insurance, DUCHOD = pension,
                       SLUZBY = statement/service fee
"""
import numpy as np
import pandas as pd

from flowscore.schema import BALANCE, CATEGORY, CREDIT, DATE, DEBIT, ID

_CREDIT_CATS = {"UROK": "interest", "DUCHOD": "pension"}
_DEBIT_CATS = {"UVER": "loan_payment", "SIPO": "bills", "POJISTNE": "insurance", "SLUZBY": "fee"}
_OPERATION_CREDIT = {"VKLAD": "deposit", "PREVOD Z UCTU": "transfer_in"}
_OPERATION_DEBIT = {"VYBER": "cash_withdrawal", "VYBER KARTOU": "card_purchase", "PREVOD NA UCET": "transfer_out"}


def category(is_credit: bool, k_symbol: str, operation: str) -> str:
    k, op = (k_symbol or "").strip(), (operation or "").strip()
    if k == "SANKC. UROK":
        return "penalty_interest"                       # either side: the charge itself is the signal
    if is_credit:
        return _CREDIT_CATS.get(k) or _OPERATION_CREDIT.get(op, "other_in")
    return _DEBIT_CATS.get(k) or _OPERATION_DEBIT.get(op, "other_out")


def to_canonical(trans: pd.DataFrame) -> pd.DataFrame:
    """Needs columns trans_id, account_id, trans_date, type, amount, balance, k_symbol (operation optional).
    Keeps account_id so the result can be grouped per borrower."""
    is_credit = trans["type"].eq("PRIJEM").to_numpy()
    amount = trans["amount"].astype(float).to_numpy()
    k = trans["k_symbol"].fillna("").astype(str) if "k_symbol" in trans else pd.Series("", index=trans.index)
    op = trans["operation"].fillna("").astype(str) if "operation" in trans else pd.Series("", index=trans.index)
    out = pd.DataFrame({
        ID: trans["trans_id"].to_numpy(),
        DATE: trans["trans_date"].to_numpy(),
        DEBIT: np.where(is_credit, np.nan, amount),
        CREDIT: np.where(is_credit, amount, np.nan),
        BALANCE: trans["balance"].astype(float).to_numpy(),
        CATEGORY: [category(c, ks, o) for c, ks, o in zip(is_credit, k, op)],
    }, index=trans.index)
    if "account_id" in trans:
        out.insert(0, "account_id", trans["account_id"].to_numpy())
    return out
