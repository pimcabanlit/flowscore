"""Slice 4: what the frontend reads from the API, and the guards on what it may say
(docs/specs/04-frontend.md).

The frontend itself is TypeScript, which this CI job does not run; its checks are in the PR
(`npm run check`, the browser check). Everything that decides what a number means on screen lives
in the backend and is tested here.
"""
import datetime as dt
import re
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flowscore.features.cashflow import SCALE_FREE_FEATURES

from backend.app.assessments.service import NOTICE
from backend.app.core.app import create_app
from backend.app.core.settings import Settings
from backend.app.features.glossary import GLOSSARY
from backend.app.transactions.repository import money
from backend.app.transactions.summary import daily_balance, monthly

from test_database import DEMO_FILES, assess, client, db_url, load_script, run, seed  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "frontend" / "src"
D = dt.date.fromisoformat


def rows(*raw):
    """Canonical tuples from (id, 'YYYY-MM-DD', debit, credit, balance, category) with string amounts."""
    return [(i, D(d), money(de), money(cr), money(bal), cat) for i, d, de, cr, bal, cat in raw]


# ---------------------------------------------------------------------------------------------
# the monthly summary, hand-worked (S4-R6)

# History covers 2026-01-15 to 2026-04-01 (exclusive): January only in part, February and March
# in full. March has no transactions at all.
HISTORY = [(D("2026-01-15"), D("2026-04-01"))]
ROWS = rows(
    ("1", "2026-01-20", None, "1000.10", "1000.10", "deposit"),
    ("2", "2026-02-05", None, "20000.00", "21000.10", "salary"),
    ("3", "2026-02-20", "15000.20", None, "5999.90", "rent"),
    ("4", "2026-02-28", None, "0.10", "6000.00", "interest"),
    ("5", "2026-02-28", None, "0.20", "6000.20", "interest"),
)


def test_monthly_summary_is_hand_worked():                      # S4-R6
    jan, feb, mar = monthly(ROWS, HISTORY)
    # January is covered only from the 15th: no figures, never zeros, but its row still counts.
    assert jan == {"month": "2026-01", "start": D("2026-01-01"), "end": D("2026-02-01"), "covered": False,
                   "money_in": None, "money_out": None, "net": None, "closing_balance": None,
                   "transaction_count": 1}
    # February: in 20,000.00 + 0.10 + 0.20 = 20,000.30 (interest included, exact in Decimal);
    # out 15,000.20; net 5,000.10; closing = balance after the last row, 6,000.20.
    assert feb == {"month": "2026-02", "start": D("2026-02-01"), "end": D("2026-03-01"), "covered": True,
                   "money_in": 20000.30, "money_out": 15000.20, "net": 5000.10, "closing_balance": 6000.20,
                   "transaction_count": 4}
    # March: covered and empty, so a true 0 in and out, and the balance carried from February.
    assert mar == {"month": "2026-03", "start": D("2026-03-01"), "end": D("2026-04-01"), "covered": True,
                   "money_in": 0.0, "money_out": 0.0, "net": 0.0, "closing_balance": 6000.20,
                   "transaction_count": 0}


def test_a_gap_of_one_day_uncovers_the_month():                 # S4-R6
    periods = [(D("2026-01-01"), D("2026-02-10")), (D("2026-02-11"), D("2026-03-01"))]
    r = rows(("1", "2026-01-05", None, "100.00", "100.00", "deposit"),
             ("2", "2026-02-15", "40.00", None, "60.00", "bills"))
    jan, feb = monthly(r, periods)
    assert (jan["covered"], jan["money_in"], jan["closing_balance"]) == (True, 100.0, 100.0)
    assert (feb["covered"], feb["money_out"], feb["closing_balance"]) == (False, None, None)
    assert monthly(r, []) == []


def test_daily_balance_is_the_last_row_of_each_day():           # S4-R6
    assert daily_balance(ROWS) == [
        {"date": D("2026-01-20"), "balance": 1000.10}, {"date": D("2026-02-05"), "balance": 21000.10},
        {"date": D("2026-02-20"), "balance": 5999.90}, {"date": D("2026-02-28"), "balance": 6000.20}]


def test_cashflow_endpoint(db_url):                             # S4-R2, S4-R6
    seed(db_url, ["SYN-001"])
    tx = DEMO_FILES[1]
    mine = tx[tx.borrower_id == "SYN-001"]
    with client(db_url) as c:
        before = c.get("/api/v1/borrowers/SYN-001/cashflow").json()
        assert before["window"] is None
        months = before["months"]
        assert [m["month"] for m in months][:2] == ["2025-10", "2025-11"] and len(months) == 12
        assert all(m["covered"] for m in months)
        # September 2026 from the demo file, summed independently in Decimal.
        sep = mine[mine.transaction_date.str.startswith("2026-09")]
        dec = lambda col: sum((Decimal(v) for v in sep[col] if v != ""), Decimal("0"))
        got = months[-1]
        assert got["month"] == "2026-09"
        assert got["money_in"] == float(dec("credit_amount")) and got["money_out"] == float(dec("debit_amount"))
        assert got["closing_balance"] == float(mine.running_balance.iloc[-1])
        assert got["transaction_count"] == len(sep)
        assert before["daily_balance"][-1]["balance"] == float(mine.running_balance.iloc[-1])
        assert len(before["daily_balance"]) == mine.transaction_date.nunique()

        made = assess(c, "SYN-001", "2026-10-01").json()
        assert made["window_start"] == "2026-07-01"                 # S4-R3: the page names the window
        after = c.get("/api/v1/borrowers/SYN-001/cashflow").json()
        assert after["window"] == {"assessment_id": made["id"], "as_of": "2026-10-01",
                                   "start": "2026-07-01", "end": "2026-10-01"}
        assert c.get("/api/v1/borrowers/NOPE/cashflow").status_code == 404


# ---------------------------------------------------------------------------------------------
# plain-language labels (S4-R7)

def test_every_model_feature_has_one_plain_label():             # S4-R7
    assert list(GLOSSARY) == SCALE_FREE_FEATURES
    labels = [g["label"] for g in GLOSSARY.values()]
    assert len(set(labels)) == len(labels)
    with TestClient(create_app(Settings(database_url=None))) as c:      # no database needed
        got = c.get("/api/v1/features/glossary").json()
    assert [g["feature"] for g in got] == SCALE_FREE_FEATURES
    assert all(g["window_months"] == 3 and g["label"] and g["description"] for g in got)


# ---------------------------------------------------------------------------------------------
# what the frontend may say (S4-R3, S4-R8)

def _frontend_text() -> dict:
    files = [p for p in FRONTEND_SRC.rglob("*") if p.suffix in {".ts", ".tsx", ".css"}]
    assert files, "frontend/src is missing"
    return {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8") for p in files}


FORBIDDEN = [
    (re.compile(r"\b(high|low|medium|moderate)[ -]risk\b", re.I), 'an absolute risk label (D22: say "higher relative risk")'),
    (re.compile(r"probability of default|default probability|chance of default", re.I), "a probability of default (D21)"),
    (re.compile(r"\bPD\b"), "a PD (D21)"),
    (re.compile(r"predict_proba|probability", re.I), "a probability (D21)"),
]


def test_frontend_never_shows_a_probability_or_an_absolute_label():   # S4-R8
    errors = [f"{name}: {why}" for name, text in _frontend_text().items()
              for pattern, why in FORBIDDEN if pattern.search(text)]
    assert not errors, "\n".join(errors)


def test_notice_comes_from_the_api_and_is_never_a_tooltip():    # S4-R3
    texts = _frontend_text()
    joined = "\n".join(texts.values())
    assert NOTICE not in joined, "the D21 notice is rendered from the API's `notice` field, not copied"
    notice = texts["frontend/src/components/notice.tsx"]
    assert "notice" in notice and not re.search(r"tooltip|title=|popover|hover", notice, re.I)


# ---------------------------------------------------------------------------------------------
# demo assessments (S4-R9)

assess_script = load_script("assess_demo_borrowers")


def test_assess_demo_borrowers_runs_twice_without_duplicates(db_url):   # S4-R9
    seed(db_url, ["SYN-001", "SYN-025"])
    first = assess_script.assess_all(Settings(database_url=db_url))
    assert first == {"assessed": ["SYN-001", "SYN-025"], "skipped": []}
    second = assess_script.assess_all(Settings(database_url=db_url))
    assert second == {"assessed": [], "skipped": ["SYN-001", "SYN-025"]}
    with client(db_url) as c:
        listed = c.get("/api/v1/borrowers").json()
    assert [(b["id"], b["latest_assessment"]["as_of"]) for b in listed] == [
        ("SYN-001", "2026-10-01"), ("SYN-025", "2026-10-01")]
