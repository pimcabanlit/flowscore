"""Canonical-schema feature tests. Every expected value is worked out by hand in the comments."""
import numpy as np
import pandas as pd
import pytest

from flowscore.adapters.berka import category, to_canonical
from flowscore.features.cashflow import (SCALE_FREE_FEATURES, features_as_of, income_denominator, monthly_inflows,
                                         monthly_salary, obligation_features, opening_balance, salary_baseline,
                                         scale_free_features, window_features, window_slice)
from flowscore.schema import validate

T = pd.Timestamp


def canon(rows):
    """rows: (id, date, debit, credit, balance, category)"""
    df = pd.DataFrame(rows, columns=["transaction_id", "transaction_date", "debit_amount", "credit_amount",
                                     "running_balance", "transaction_category"])
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


# ---------- 1. research features: same hand example as test_transactions.py, canonical columns
def test_window_features_hand_example():
    t = canon([
        (1, "1996-01-05", None, 1000, 1500, "transfer_in"),
        (2, "1996-01-20", 300, None, 1200, "bills"),
        (3, "1996-02-10", None, 1000, 2200, "transfer_in"),
        (4, "1996-02-28", None, 10, 2210, "interest"),            # not income
        (5, "1996-03-05", 2500, None, -290, "cash_withdrawal"),
        (6, "1996-03-06", 20, None, -310, "penalty_interest"),
        (7, "1996-03-15", None, 1600, 1290, "transfer_in"),
    ])
    f = window_features(t, T("1996-04-01"), opening=500)
    assert f["avg_monthly_inflow"] == pytest.approx(3600 / 3)
    assert f["inflow_cv"] == pytest.approx(np.std([1000, 1000, 1600]) / 1200)
    assert f["min_balance"] == -310 and f["days_negative_balance"] == 10
    assert f["penalty_interest_count"] == 1 and f["months_net_outflow"] == 1
    assert f["outflow_inflow_ratio"] == pytest.approx(2820 / 3600) and f["tx_count"] == 7
    exp = (500*4 + 1500*15 + 1200*21 + 2200*18 + 2210*6 - 290 - 310*9 + 1290*17) / 91
    assert f["avg_daily_balance"] == pytest.approx(exp)


def test_window_slice_never_uses_as_of_day_or_later():
    t = canon([(1, "2026-01-01", 1, None, 0, "x"), (2, "2026-03-31", 1, None, 0, "x"),
               (3, "2026-04-01", 1, None, 0, "x"), (4, "2026-05-01", 1, None, 0, "x")])
    assert list(window_slice(t, "2026-04-01", 3)["transaction_id"]) == [1, 2]


def test_opening_balance():
    t = canon([(1, "2026-01-10", None, 200, 1200, "salary"), (2, "2026-02-10", 50, None, 1150, "fee")])
    assert opening_balance(t, "2026-02-01") == 1200            # last balance before the start
    assert opening_balance(t, "2026-01-01") == 1000            # nothing before: undo first (1200 - 200)


# ---------- 2. obligations
def test_obligation_features_hand_example():
    w = canon([
        (1, "2026-01-15", None, 1000, 0, "salary"), (2, "2026-01-30", None, 1000, 0, "salary"),
        (3, "2026-01-16", 600, None, 0, "credit_card_payment"), (4, "2026-02-01", 200, None, 0, "loan_payment"),
        (5, "2026-02-05", 500, None, 0, "rent"), (6, "2026-02-20", None, 300, 0, "reimbursement"),
        (7, "2026-02-21", 30, None, 0, "fee"), (8, "2026-02-22", 99, None, 0, "card_purchase"),
    ])
    f = obligation_features(w, months=3)
    assert f["salary_share_of_inflow"] == pytest.approx(2000 / 2300)
    assert f["debt_service_ratio"] == pytest.approx(800 / 2000)           # card 600 + loan 200
    assert f["fixed_obligation_ratio"] == pytest.approx(1300 / 2000)      # + rent 500
    assert f["net_debt_service_ratio"] == pytest.approx(500 / 2000)       # 800 - 300 reimbursed
    assert f["reimbursements_per_month"] == pytest.approx(100)
    assert f["fees_per_month"] == pytest.approx(10)
    assert f["card_purchases_per_month"] == pytest.approx(1 / 3) and f["salary_credits"] == 2


def test_obligations_without_salary_are_unknown_not_zero():
    f = obligation_features(canon([(1, "2026-01-16", 600, None, 0, "credit_card_payment")]))
    assert np.isnan(f["debt_service_ratio"]) and np.isnan(f["net_debt_service_ratio"])


def test_net_debt_never_negative():
    w = canon([(1, "2026-01-15", None, 1000, 0, "salary"), (2, "2026-01-16", 100, None, 0, "credit_card_payment"),
               (3, "2026-01-20", None, 500, 0, "reimbursement")])
    assert obligation_features(w)["net_debt_service_ratio"] == 0


# ---------- 3. salary baseline
def history():
    # history 2025-10-15 .. 2026-05-10: full months Nov..Apr. Feb has one payday, Mar has none.
    rows, i = [], 0
    for m, n in [("2025-10", 2), ("2025-11", 2), ("2025-12", 2), ("2026-01", 2), ("2026-02", 1), ("2026-03", 0),
                 ("2026-04", 2), ("2026-05", 1)]:
        for d in ["15", "28"][:n]:
            i += 1; rows.append((i, f"{m}-{d}", None, 1000, 0, "salary"))
    rows.insert(0, (0, "2025-10-15", 1, None, 0, "fee")); rows.append((99, "2026-05-10", 1, None, 0, "fee"))
    return canon(rows)


def test_monthly_salary_full_months_only_and_zero_months_kept():
    m = monthly_salary(history())
    assert [str(p) for p in m.index] == ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]
    assert list(m) == [2000, 2000, 2000, 1000, 0, 2000]     # Oct and May are partial: left out


def test_salary_baseline_is_median_of_past_months_only():
    m = monthly_salary(history())
    empty = canon([])
    assert np.isnan(salary_baseline(m, empty, "2026-01-15")["salary_baseline_monthly"])   # only Nov, Dec: < 3
    b = salary_baseline(m, empty, "2026-03-01")              # Nov..Feb = 2000,2000,2000,1000 -> median 2000
    assert b["salary_baseline_monthly"] == 2000 and b["salary_baseline_months_used"] == 4
    b = salary_baseline(m, empty, "2026-04-15")              # Mar (ends Mar 31) counts, Apr (ends Apr 30) not yet
    assert b["salary_baseline_months_used"] == 5 and b["salary_baseline_monthly"] == 2000
    w = canon([(1, "2026-02-01", 900, None, 0, "credit_card_payment"), (2, "2026-02-02", None, 300, 0, "reimbursement")])
    b = salary_baseline(m, w, "2026-03-01", months=3)        # debt 300/month, reimb 100/month
    assert b["debt_service_ratio_baseline"] == pytest.approx(300 / 2000)
    assert b["net_debt_service_ratio_baseline"] == pytest.approx(200 / 2000)


def test_salary_baseline_needs_three_months():
    m = monthly_salary(history())
    assert salary_baseline(m, canon([]), "2026-01-31")["salary_baseline_months_used"] == 2


def test_features_as_of_combines_all_groups():
    f = features_as_of(history(), "2026-04-01")
    assert {"min_balance", "debt_service_ratio", "salary_baseline_monthly"} <= set(f)


# ---------- schema + Berka adapter
def test_validate_catches_bad_tables():
    assert validate(pd.DataFrame({"x": [1]}))[0].startswith("missing column")
    bad = canon([(1, "2026-01-01", 5, 5, 0, "x"), (1, "2026-01-02", -1, None, 0, "x")])
    errs = " | ".join(validate(bad))
    assert "both a debit and a credit" in errs and "negative" in errs and "duplicate" in errs


def test_berka_categories():
    assert category(True, "UROK", "") == "interest"
    assert category(False, "SANKC. UROK", "VYBER") == "penalty_interest"
    assert category(False, "UVER", "PREVOD NA UCET") == "loan_payment"
    assert category(True, "", "VKLAD") == "deposit"
    assert category(False, "", "VYBER KARTOU") == "card_purchase"
    assert category(False, "", "") == "other_out"


def test_berka_to_canonical_splits_sides():
    b = pd.DataFrame({"trans_id": [1, 2], "account_id": [7, 7], "trans_date": pd.to_datetime(["1995-01-01"] * 2),
                      "type": ["PRIJEM", "VYBER"], "amount": [100.0, 40.0], "balance": [100.0, 60.0],
                      "k_symbol": ["UROK", None], "operation": [None, "VYBER"]})
    c = to_canonical(b)
    assert list(c["credit_amount"].fillna(0)) == [100, 0] and list(c["debit_amount"].fillna(0)) == [0, 40]
    assert list(c["transaction_category"]) == ["interest", "cash_withdrawal"] and validate(c) == []


# ---------- 4. scale-free features and the income denominator (D21)
HAND = [
    (1, "1996-01-05", None, 1000, 1500, "transfer_in"),
    (2, "1996-01-20", 300, None, 1200, "bills"),
    (3, "1996-02-10", None, 1000, 2200, "transfer_in"),
    (4, "1996-02-28", None, 10, 2210, "interest"),
    (5, "1996-03-05", 2500, None, -290, "cash_withdrawal"),
    (6, "1996-03-06", 20, None, -310, "penalty_interest"),
    (7, "1996-03-15", None, 1600, 1290, "transfer_in"),
]


def test_income_denominator_hand_example():
    t = canon(HAND)
    # buckets back from 1 Apr: Mar = 1600, Feb = 1000 (the 10 of interest is excluded), Jan = 1000
    assert list(monthly_inflows(t, T("1996-04-01"))) == [1600, 1000, 1000]
    assert income_denominator(t, T("1996-04-01")) == 1000                    # median(1600, 1000, 1000)
    assert income_denominator(t, T("1996-04-01"), months=2) == 1300          # median(1600, 1000) = (1600+1000)/2


def test_income_denominator_counts_salary_and_transfers_alike():
    # the definition must not depend on a salary label (Berka has none)
    a = canon([(1, "2026-01-15", None, 500, 500, "salary"), (2, "2026-02-15", None, 500, 1000, "salary"),
               (3, "2026-03-15", None, 500, 1500, "salary")])
    b = a.assign(transaction_category="transfer_in")
    assert income_denominator(a, T("2026-04-01")) == income_denominator(b, T("2026-04-01")) == 500


def test_income_denominator_is_nan_not_zero():
    assert np.isnan(income_denominator(canon([]), T("2026-04-01")))           # no transactions
    only_interest = canon([(1, "2026-03-31", None, 5, 5, "interest")])
    assert np.isnan(income_denominator(only_interest, T("2026-04-01")))      # interest is not income
    one_month = canon([(1, "2026-03-10", None, 900, 900, "salary")])         # buckets 900, 0, 0 -> median 0
    assert np.isnan(income_denominator(one_month, T("2026-04-01")))


def test_scale_free_features_hand_example():
    t = canon(HAND)
    f = window_features(t, T("1996-04-01"), opening=500)
    s = scale_free_features(f, income_denominator(t, T("1996-04-01")))
    assert list(s) == SCALE_FREE_FEATURES
    assert s["min_balance_to_income"] == pytest.approx(-310 / 1000)
    exp_avg = (500*4 + 1500*15 + 1200*21 + 2200*18 + 2210*6 - 290 - 310*9 + 1290*17) / 91
    assert s["avg_balance_to_income"] == pytest.approx(exp_avg / 1000)
    assert s["inflow_cv"] == f["inflow_cv"] and s["months_net_outflow"] == 1
    assert s["outflow_inflow_ratio"] == pytest.approx(2820 / 3600)


def test_scale_free_features_do_not_change_with_currency():
    t = canon(HAND)
    money = ["debit_amount", "credit_amount", "running_balance"]
    t50 = t.assign(**{c: t[c] * 50 for c in money})                         # same account, another currency
    s1 = scale_free_features(window_features(t, T("1996-04-01"), 500), income_denominator(t, T("1996-04-01")))
    s50 = scale_free_features(window_features(t50, T("1996-04-01"), 500 * 50), income_denominator(t50, T("1996-04-01")))
    assert s1 == pytest.approx(s50, nan_ok=True)


def test_scale_free_features_missing_income_gives_nan_ratios():
    s = scale_free_features({"inflow_cv": np.nan, "outflow_inflow_ratio": np.nan, "months_net_outflow": 3,
                             "min_balance": -50.0, "avg_daily_balance": 20.0}, np.nan)
    assert np.isnan(s["min_balance_to_income"]) and np.isnan(s["avg_balance_to_income"])
