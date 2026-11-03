"""Slice 2 synthetic demo borrowers (docs/specs/02-synthetic-borrowers.md). Runs in CI.

Demo data only (D1). The hand-worked accounts below use round made-up numbers, not anyone's
statements. Dates were checked against a calendar: 2025-11-15 is a Saturday, 2025-11-30 a Sunday
(and Bonifacio Day), 2025-12-31 a Wednesday (special non-working day) and 2025-12-30 a Tuesday
(Rizal Day), 2026-08-31 the last Monday of August (National Heroes Day).
"""
import datetime as dt
import inspect
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from flowscore import synthetic
from flowscore.schema import CATEGORIES, validate
from flowscore.synthetic import (AS_OF, HISTORY_START, PERSONAS, Profile, generate, paydays, read,
                                 simulate, to_canonical, transfer_fee, write)

from backend.app.core.app import create_app

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "synthetic"
D = dt.date


def rows_of(profile, start, end):
    """(date, debit, credit, balance, category) for each generated row."""
    rows = simulate(profile, np.random.default_rng(0), "SYN-T", start, end)
    return [tuple(r[2:]) for r in rows]


# ---------------------------------------------------------------------------------------------
# patterns

def test_paydays_move_back_from_weekends_and_holidays():  # S2-R1
    assert paydays(2025, 10) == [D(2025, 10, 15), D(2025, 10, 31)]      # Wed, Fri: unchanged
    assert paydays(2025, 11) == [D(2025, 11, 14), D(2025, 11, 28)]      # Sat -> Fri; Sun + holiday, Sat -> Fri
    assert paydays(2025, 12) == [D(2025, 12, 15), D(2025, 12, 29)]      # 31st and 30th holidays -> Mon 29th
    assert paydays(2026, 2) == [D(2026, 2, 13), D(2026, 2, 27)]         # Sun -> Fri; Sat 28th -> Fri
    assert paydays(2026, 8) == [D(2026, 8, 14), D(2026, 8, 28)]         # Sat -> Fri; Heroes Day Mon -> Fri


def test_transfer_fees_follow_the_dated_schedule():  # S2-R1
    assert transfer_fee("instapay", D(2026, 6, 30)) == 2_500             # PHP 25.00, in centavos
    assert transfer_fee("pesonet", D(2026, 6, 30)) == 5_000              # PHP 50.00
    assert transfer_fee("instapay", D(2026, 7, 1)) == 0                  # waived from July 2026
    assert transfer_fee("pesonet", D(2026, 7, 1)) == 0
    assert transfer_fee(None, D(2025, 11, 5)) == 0                       # bills payment: no fee


STEADY = Profile("steady_salaried", opening_balance=10_000, semi_monthly_pay=10_000, thirteenth_month=20_000,
                 rent=6_000, electricity=2_000, card_payment=3_000, interest=False)


def test_hand_worked_steady_account():  # S2-R11
    # Nov 2025: rent on the 5th by InstaPay (+25 fee), pay on Fri 14th and Fri 28th, electricity on
    # the 20th, card on the 23rd.  Dec 2025: the 13th month (20,000) comes with the 15th's pay; the
    # last payday moves from Wed 31st past Tue 30th to Mon 29th.
    assert rows_of(STEADY, D(2025, 11, 1), D(2026, 1, 1)) == [
        ("2025-11-05", "6000.00", "", "4000.00", "rent"),               # 10,000 - 6,000
        ("2025-11-05", "25.00", "", "3975.00", "fee"),
        ("2025-11-14", "", "10000.00", "13975.00", "salary"),
        ("2025-11-20", "2000.00", "", "11975.00", "bills"),
        ("2025-11-23", "3000.00", "", "8975.00", "credit_card_payment"),
        ("2025-11-28", "", "10000.00", "18975.00", "salary"),           # Nov: in 20,000, out 11,025
        ("2025-12-05", "6000.00", "", "12975.00", "rent"),
        ("2025-12-05", "25.00", "", "12950.00", "fee"),
        ("2025-12-15", "", "10000.00", "22950.00", "salary"),
        ("2025-12-15", "", "20000.00", "42950.00", "salary"),           # 13th month
        ("2025-12-20", "2000.00", "", "40950.00", "bills"),
        ("2025-12-23", "3000.00", "", "37950.00", "credit_card_payment"),
        ("2025-12-29", "", "10000.00", "47950.00", "salary"),           # Dec: in 40,000, out 11,025
    ]
    # Jul 2026: transfers are free, so rent has no fee row and the month's outflow is 11,000.
    jul = rows_of(STEADY, D(2026, 7, 1), D(2026, 8, 1))
    assert [r[4] for r in jul].count("fee") == 0
    assert sum(float(r[1] or 0) for r in jul) == 11_000 and sum(float(r[2] or 0) for r in jul) == 20_000
    assert jul[-1] == ("2026-07-31", "", "10000.00", "19000.00", "salary")   # 10,000 + 20,000 - 11,000


def test_savings_account_never_goes_negative():  # S2-R5
    # Opening 1,000. Rent 5,000 on the 5th cannot be covered: skipped with its fee. Each payday is
    # swept the next day down to 300, in whole hundreds: 11,000 - 10,700 and 10,300 - 10,000.
    p = Profile("near_zero", opening_balance=1_000, semi_monthly_pay=10_000, rent=5_000,
                sweep_after_payday=True, sweep_keep=300, interest=False)
    assert rows_of(p, D(2025, 11, 1), D(2025, 12, 1)) == [
        ("2025-11-14", "", "10000.00", "11000.00", "salary"),
        ("2025-11-15", "10700.00", "", "300.00", "cash_withdrawal"),
        ("2025-11-28", "", "10000.00", "10300.00", "salary"),
        ("2025-11-29", "10000.00", "", "300.00", "cash_withdrawal"),
    ]


def test_a_load_is_declined_not_charged_in_part():  # S2-R5
    # Opening 10.00 and two loads a month: the smallest load is 50, so both are declined. A load
    # is never cut to the 10.00 the account holds (review of #11: 70 partial loads like 9.18).
    p = Profile("near_zero", opening_balance=10, phone_loads=2, interest=False)
    assert rows_of(p, D(2025, 11, 1), D(2025, 12, 1)) == []


def test_no_row_on_or_after_the_end_date():  # S2-R8
    # History ending mid-month: the month-end interest (30 Nov) falls after the end and is not
    # written (review of #11: it used to be, dated after as_of).
    p = Profile("steady_salaried", opening_balance=100_000)
    assert rows_of(p, D(2025, 11, 1), D(2025, 11, 15)) == []
    assert rows_of(p, D(2025, 11, 1), D(2025, 12, 1)) == [("2025-11-30", "", "4.16", "100004.16", "interest")]
    # 100,000.00 x 0.0625% / 12 = 5.2083; less 20% tax = 4.1667 -> 4.16 (whole centavos, truncated)


def test_interest_is_net_of_final_tax():  # S2-R1
    # 1,200,000.00 at 0.0625% a year: a month is 62.50, less 20% tax = 50.00.
    p = Profile("steady_salaried", opening_balance=1_200_000)
    assert rows_of(p, D(2025, 11, 1), D(2025, 12, 1)) == [("2025-11-30", "", "50.00", "1200050.00", "interest")]


# ---------------------------------------------------------------------------------------------
# the borrower set

@pytest.fixture(scope="module")
def committed():
    return read(DEMO)


def test_borrower_set_covers_every_persona(committed):  # S2-R2, S2-R3
    borrowers, tx = committed
    assert len(borrowers) == 30
    assert borrowers.persona.value_counts().to_dict() == {p: 6 for p in PERSONAS}
    assert set(borrowers.history_start) == {HISTORY_START.isoformat()}
    assert set(borrowers.as_of) == {AS_OF.isoformat()}
    for persona, cats in [("steady_salaried", {"salary", "rent", "fee", "bills", "credit_card_payment",
                                               "phone_load", "cash_withdrawal", "interest"}),
                          ("card_debt", {"salary", "credit_card_payment", "loan_payment", "fee"}),
                          ("irregular_freelancer", {"transfer_in", "bills", "cash_withdrawal"}),
                          ("remittance_dependent", {"transfer_in", "cash_withdrawal", "phone_load"}),
                          ("near_zero", {"salary", "cash_withdrawal"})]:
        ids = borrowers.borrower_id[borrowers.persona == persona]
        for bid in ids:
            assert cats <= set(tx.transaction_category[tx.borrower_id == bid]), (persona, bid)
    # the people differ inside a persona: no two borrowers share a first salary or first transfer in
    first_credit = tx[tx.credit_amount != ""].groupby("borrower_id").credit_amount.first()
    assert first_credit.nunique() == len(borrowers)


def test_same_seed_same_bytes(tmp_path):  # S2-R4
    a = write(tmp_path / "a", seed=7)
    b = write(tmp_path / "b", seed=7)
    c = write(tmp_path / "c", seed=8)
    assert all(x.read_bytes() == y.read_bytes() for x, y in zip(a, b))
    assert a[1].read_bytes() != c[1].read_bytes()
    assert b"\r\n" not in a[1].read_bytes()


def test_committed_files_match_the_generator(tmp_path):  # S2-R4
    for path in write(tmp_path):
        assert path.read_bytes() == (DEMO / path.name).read_bytes(), \
            f"demo/synthetic/{path.name} is stale: run scripts/generate_synthetic_borrowers.py"


def test_borrowers_are_clearly_fictional(committed):  # S2-R6
    borrowers, tx = committed
    assert list(borrowers.columns) == synthetic.BORROWER_COLUMNS
    assert list(tx.columns) == synthetic.COLUMNS          # no description or payee column at all
    assert set(borrowers.synthetic) == {"true"}
    assert list(borrowers.borrower_id) == [f"SYN-{n:03d}" for n in range(1, 31)]
    assert list(borrowers.display_name) == [f"Demo Borrower {n:02d}" for n in range(1, 31)]
    src = inspect.getsource(synthetic)
    assert "personal/" not in src.replace("Nothing is read from personal/", "")
    assert "open(" not in src and "read_csv(out / f" in src   # reads only its own output


def test_every_account_is_valid(committed):  # S2-R7, S2-R8
    borrowers, tx = committed
    assert set(tx.transaction_category) <= CATEGORIES
    for b in borrowers.itertuples():
        rows = tx[tx.borrower_id == b.borrower_id]
        df = to_canonical(rows)
        assert validate(df) == [], b.borrower_id
        assert df.transaction_date.min() >= np.datetime64(b.history_start)
        assert df.transaction_date.max() < np.datetime64(b.as_of)
        assert (df.debit_amount.isna() ^ df.credit_amount.isna()).all()        # one side, the other empty
        assert not ((rows.debit_amount == "0.00") | (rows.credit_amount == "0.00")).any()
        # running balance: each row = previous + credit - debit, to the centavo, never negative
        cents = lambda s: s.replace("", "0").str.replace(".", "", regex=False).astype(int)
        bal, dr, cr = cents(rows.running_balance), cents(rows.debit_amount), cents(rows.credit_amount)
        assert (bal.diff().iloc[1:] == (cr - dr).iloc[1:]).all(), b.borrower_id
        assert (bal >= 0).all()
        # loads come in their denominations only; never charged in part
        loads = rows.debit_amount[rows.transaction_category == "phone_load"].astype(float)
        assert loads.isin(synthetic.LOAD_DENOMINATIONS).all(), b.borrower_id
        # chronological in id order, so ties on a day keep the statement's order
        assert list(rows.transaction_id) == sorted(rows.transaction_id)
        assert rows.transaction_date.is_monotonic_increasing


# ---------------------------------------------------------------------------------------------
# scoring through the API, with the committed model

@pytest.fixture(scope="module")
def scored():
    import importlib.util
    spec = importlib.util.spec_from_file_location("score_synthetic", ROOT / "scripts" / "score_synthetic_borrowers.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with TestClient(create_app()) as client:
        return mod, mod.score_all(client, DEMO)


def test_every_borrower_is_scored(scored):  # S2-R9
    _, results = scored
    assert len(results) == 30
    # Every persona currently scores. If one is ever refused for being out of range, this list is
    # where it shows: change the expectation and report it in the PR (a finding about D21).
    assert {b.borrower_id: s["status"] for b, s in results} == {b.borrower_id: "scored" for b, _ in results}
    for b, s in results:
        assert s["risk_band"] in {"lower", "middle", "higher"}
        assert s["notice"]


def test_score_table_names_the_top_driver(scored):  # S2-R10
    mod, results = scored
    assert mod.top_driver({"contributions": {"a": 0.5, "b": -1.25, "c": 1.0}}) == "b (-1.25)"
    assert mod.top_driver(None) == ""
    _, s = results[0]
    assert set(s["shap"]["contributions"]) == set(s["features"])
