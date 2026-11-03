"""Slice 3: the database (docs/specs/03-database.md).

Runs on SQLite (a temporary file per test) unless FLOWSCORE_TEST_DATABASE_URL names an empty
Postgres database, in which case the same tests run there (S3-R16). Each test starts from
`alembic downgrade base` + `alembic upgrade head`, so that database is wiped: its name must
contain "test".

Scoring uses the committed model (models/catboost-sf-v1/, D22), which CI has.
"""
import ast
import asyncio
import configparser
import datetime as dt
import hashlib
import importlib.util
import logging
import math
import os
import re
import shutil
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

import flowscore.features.cashflow as cashflow
from flowscore_demo.synthetic import read

from backend.app.assessments import repository as assessments_repo
from backend.app.assessments.service import compute_features
from backend.app.core.app import create_app
from backend.app.core.db import make_engine, make_sessionmaker
from backend.app.core.settings import Settings
from backend.app.core.tables import metadata
from backend.app.models.registry import RegistryMismatch
from backend.app.transactions import repository as tx_repo
from backend.app.transactions.repository import covers, fingerprint, money

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "synthetic"
TEST_URL = os.environ.get("FLOWSCORE_TEST_DATABASE_URL")
CREDENTIALS_IN_URL = re.compile(r"://[^/\s\"'@]+:[^/\s\"'@]+@")       # scheme://user:password@
TABLES = {"borrowers", "transaction_batches", "transactions", "feature_snapshots", "assessments", "model_registry"}


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


seed_script = load_script("seed_demo_database")
score_script = load_script("score_synthetic_borrowers")
DEMO_FILES = read(DEMO)
PREPARED = {p[0].borrower_id: p for p in seed_script.prepare(*DEMO_FILES)}


# ---------------------------------------------------------------------------------------------
# helpers

def migrate(url, target, monkeypatch):
    """alembic upgrade/downgrade, with the URL from FLOWSCORE_DATABASE_URL as in real use (S3-R4).
    The Config is built without alembic.ini so the test run's logging is left alone."""
    monkeypatch.setenv("FLOWSCORE_DATABASE_URL", url)
    cfg = Config()
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    (command.upgrade if target == "head" else command.downgrade)(cfg, target)
    monkeypatch.delenv("FLOWSCORE_DATABASE_URL")


@pytest.fixture
def db_url(tmp_path, monkeypatch):
    if TEST_URL:
        name = make_url(TEST_URL).database or ""
        assert "test" in name, f"FLOWSCORE_TEST_DATABASE_URL names '{name}': the tests wipe it, so its name must contain 'test'"
        url = TEST_URL
    else:
        url = f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    migrate(url, "base", monkeypatch)
    migrate(url, "head", monkeypatch)
    return url


def run(url, fn):
    """Run `await fn(sessionmaker)` on a fresh engine, in its own event loop."""
    async def go():
        engine = make_engine(url)
        try:
            return await fn(make_sessionmaker(engine))
        finally:
            await engine.dispose()
    return asyncio.run(go())


def sql(url, statement, **params):
    """Rows of a raw SQL statement (committed)."""
    async def fn(maker):
        async with maker() as s:
            res = await s.execute(text(statement), params)
            rows = res.all() if res.returns_rows else None
            await s.commit()
            return rows
    return run(url, fn)


def seed(url, ids=None):
    prepared = [PREPARED[i] for i in (ids or sorted(PREPARED))]
    return run(url, lambda maker: seed_script.seed(maker, prepared))


def add_account(url, borrower_id, start, end, rows):
    """A made-up borrower with canonical rows (id, 'YYYY-MM-DD', debit, credit, balance, category)."""
    tuples = [(i, dt.date.fromisoformat(d), money(de), money(cr), money(bal), cat) for i, d, de, cr, bal, cat in rows]
    b = SimpleNamespace(borrower_id=borrower_id, display_name=f"Test {borrower_id}")
    return run(url, lambda maker: seed_script.seed(maker, [(b, dt.date.fromisoformat(start),
                                                              dt.date.fromisoformat(end), tuples)]))


def client(url, **kw):
    return TestClient(create_app(Settings(database_url=url, **kw)))


def assess(c, borrower_id, as_of):
    return c.post(f"/api/v1/borrowers/{borrower_id}/assessments", json={"as_of": as_of})


STORED_ONLY = {"id", "borrower_id", "snapshot_id", "features_version", "created_at"}


def output(a: dict) -> dict:
    """A stored assessment without the fields only a stored one has."""
    return {k: v for k, v in a.items() if k not in STORED_ONLY}


# Made-up accounts with round numbers (the same as Accounts A and B in test_scoring_api.py).
# as_of 2026-04-01: window [2026-01-01, 2026-04-01).
ACCOUNT_A = [
    ("1", "2025-12-15", None, 10_000, 10_000, "deposit"),
    ("2", "2026-01-05", None, 20_000, 30_000, "salary"),
    ("3", "2026-01-20", 15_000, None, 15_000, "rent"),
    ("4", "2026-02-05", None, 20_000, 35_000, "salary"),
    ("5", "2026-02-20", 25_000, None, 10_000, "bills"),
    ("6", "2026-03-05", None, 30_000, 40_000, "salary"),
    ("7", "2026-03-06", None, 100, 40_100, "interest"),
    ("8", "2026-03-20", 20_000, None, 20_100, "card_purchase"),
]
# Hand-worked in test_scoring_api.py: income 20,000; cv sqrt(2)/7; ratio 6/7; 1 net-outflow month;
# min balance 10,000 -> 0.5; average daily balance 2,227,600 / 90 -> 5,569 / 4,500.
A_EXPECTED = {"inflow_cv": math.sqrt(2) / 7, "outflow_inflow_ratio": 6 / 7, "months_net_outflow": 1.0,
              "min_balance_to_income": 0.5, "avg_balance_to_income": 5569 / 4500}
ACCOUNT_B = [
    ("1", "2025-12-15", None, 5_000, 5_000, "deposit"),
    ("2", "2026-01-10", None, 20_000, 25_000, "salary"),
    ("3", "2026-02-10", 10_000, None, 15_000, "bills"),
    ("4", "2026-03-10", 5_000, None, 10_000, "bills"),
]
# Hand-worked: monthly inflow 20,000, 0, 0 -> median 0 -> income unknown, so both balance-to-income
# features are unknown too (NULL, not 0); cv sqrt(2); ratio 15,000 / 20,000 = 0.75; 2 net-outflow months.
B_EXPECTED = {"inflow_cv": math.sqrt(2), "outflow_inflow_ratio": 0.75, "months_net_outflow": 2.0,
              "min_balance_to_income": None, "avg_balance_to_income": None}


def assert_features(got, expected):
    assert set(got) == set(expected)
    for f, v in expected.items():
        assert got[f] == (None if v is None else pytest.approx(v, rel=1e-12, abs=1e-12)), f


# ---------------------------------------------------------------------------------------------
# hand-worked helpers

def test_window_coverage_is_hand_worked():                  # S3-R8
    d = dt.date
    jan_feb, feb_mar = (d(2026, 1, 1), d(2026, 2, 1)), (d(2026, 2, 1), d(2026, 3, 1))
    assert covers([jan_feb, feb_mar], d(2026, 1, 1), d(2026, 3, 1))           # adjacent periods join
    assert covers([feb_mar, jan_feb], d(2026, 1, 15), d(2026, 2, 15))         # order does not matter
    assert not covers([jan_feb, (d(2026, 2, 2), d(2026, 3, 1))], d(2026, 1, 1), d(2026, 3, 1))  # 1-day gap
    assert not covers([jan_feb], d(2025, 12, 31), d(2026, 2, 1))              # starts a day too early
    assert not covers([jan_feb], d(2026, 1, 1), d(2026, 2, 2))                # ends a day too late
    assert covers([jan_feb], d(2026, 1, 1), d(2026, 2, 1))                    # end is exclusive
    assert not covers([], d(2026, 1, 1), d(2026, 2, 1))


def test_amounts_keep_two_places_and_missing_stays_none():   # S3-R6
    assert money("192.48") == Decimal("192.48")
    assert money(25) == Decimal("25.00")
    assert money("") is None and money(None) is None and money(float("nan")) is None
    with pytest.raises(ValueError, match="more than 2 decimal places"):
        money("1.005")


def test_fingerprint_is_hand_worked():                       # S3-R3, S3-R6
    d = dt.date
    rows = [("2", d(2026, 1, 5), None, Decimal("20000"), Decimal("30000.5"), "salary"),
            ("1", d(2026, 1, 5), Decimal("15.25"), None, Decimal("10000"), "fee")]
    expected = hashlib.sha256(b"1|2026-01-05|15.25||10000.00|fee\n"
                              b"2|2026-01-05||20000.00|30000.50|salary\n").hexdigest()
    assert fingerprint(rows) == (expected, 2)
    assert fingerprint(list(reversed(rows))) == (expected, 2)                 # statement order, not input order
    zero = [(*rows[0][:3], Decimal("0"), *rows[0][4:]), rows[1]]
    assert fingerprint(zero)[0] != expected                                   # a 0 credit is not a missing one


# ---------------------------------------------------------------------------------------------
# schema and migrations

def test_migration_matches_the_models(db_url):               # S3-R1
    async def fn(maker):
        async with maker() as s:
            conn = await s.connection()
            return await conn.run_sync(lambda c: (set(inspect(c).get_table_names()),
                                                  compare_metadata(MigrationContext.configure(c), metadata)))
    tables, diff = run(db_url, fn)
    assert tables - {"alembic_version"} == TABLES
    assert diff == []


def test_only_synthetic_borrowers_are_accepted(db_url):      # S3-R1
    with pytest.raises(DBAPIError):
        sql(db_url, "INSERT INTO borrowers (id, display_name, synthetic, created_at) "
                    "VALUES ('REAL-1', 'x', false, CURRENT_TIMESTAMP)")
    sql(db_url, "INSERT INTO borrowers (id, display_name, synthetic, created_at) "
                "VALUES ('SYN-X', 'x', true, CURRENT_TIMESTAMP)")


def test_upgrade_downgrade_upgrade(db_url, monkeypatch):     # S3-R5
    seed(db_url, ["SYN-001"])
    with client(db_url) as c:
        assert assess(c, "SYN-001", "2026-10-01").status_code == 201
    migrate(db_url, "base", monkeypatch)                      # with data, including append-only rows
    tables = run(db_url, lambda maker: _tables(maker))
    assert tables & TABLES == set()
    migrate(db_url, "head", monkeypatch)
    assert run(db_url, lambda maker: _tables(maker)) >= TABLES
    assert sql(db_url, "SELECT COUNT(*) FROM borrowers")[0][0] == 0


async def _tables(maker):
    async with maker() as s:
        conn = await s.connection()
        return await conn.run_sync(lambda c: set(inspect(c).get_table_names()))


# ---------------------------------------------------------------------------------------------
# assessments

def test_assessments_and_snapshots_cannot_be_edited(db_url):  # S3-R2
    seed(db_url, ["SYN-001"])
    with client(db_url) as c:
        first = assess(c, "SYN-001", "2026-10-01").json()
    for statement in ("UPDATE assessments SET risk_band = 'higher'", "DELETE FROM assessments",
                      "UPDATE feature_snapshots SET income_denominator = 0", "DELETE FROM feature_snapshots"):
        with pytest.raises(DBAPIError, match="append-only"):
            sql(db_url, statement)
    with client(db_url) as c:
        assert c.get(f"/api/v1/assessments/{first['id']}").json() == first
    public = {n for n in dir(assessments_repo) if not n.startswith("_")}
    assert not {n for n in public if n.startswith(("update", "delete", "edit", "remove", "set"))}


def test_rescoring_a_snapshot_gives_the_same_output(db_url):  # S3-R3
    seed(db_url, ["SYN-007"])
    with client(db_url) as c:
        a1 = assess(c, "SYN-007", "2026-10-01").json()
        a2 = assess(c, "SYN-007", "2026-10-01").json()
    assert a1["id"] != a2["id"]                                  # a new row, never an update
    assert a1["snapshot_id"] == a2["snapshot_id"]                # the same stored input
    assert output(a1) == output(a2)
    assert a1["features_version"] == hashlib.sha256(Path(cashflow.__file__).read_bytes()).hexdigest()
    rows = DEMO_FILES[1]
    before = rows[(rows.borrower_id == "SYN-007") & (rows.transaction_date < "2026-10-01")]
    snap = sql(db_url, "SELECT transaction_count, transactions_sha256, borrower_id FROM feature_snapshots")
    assert snap[0][0] == len(before) and snap[0][2] == "SYN-007"


def test_changed_transactions_give_a_new_snapshot(db_url):    # S3-R3
    add_account(db_url, "TEST-A", "2025-12-01", "2026-04-01", ACCOUNT_A)
    with client(db_url) as c:
        a1 = assess(c, "TEST-A", "2026-04-01").json()
        run(db_url, lambda maker: _add_row(maker, "TEST-A"))
        a2 = assess(c, "TEST-A", "2026-04-01").json()
    assert a2["snapshot_id"] != a1["snapshot_id"]
    snaps = sql(db_url, "SELECT transaction_count FROM feature_snapshots ORDER BY id")
    assert [r[0] for r in snaps] == [8, 9]


async def _add_row(maker, borrower_id):
    async with maker() as s:
        await tx_repo.add_batch(s, borrower_id, "test", dt.date(2026, 3, 1), dt.date(2026, 4, 1),
                                [("9", dt.date(2026, 3, 25), Decimal("100.00"), None, Decimal("20000.00"), "fee")])
        await s.commit()


def test_missing_values_are_null_not_zero(db_url):            # S3-R6
    add_account(db_url, "TEST-B", "2025-12-01", "2026-04-01", ACCOUNT_B)
    with client(db_url) as c:
        a = assess(c, "TEST-B", "2026-04-01").json()
    assert a["income_denominator"] is None
    assert_features(a["features"], B_EXPECTED)
    assert {m["feature"] for m in a["missing"]} == {"min_balance_to_income", "avg_balance_to_income"}
    income, = sql(db_url, "SELECT income_denominator FROM feature_snapshots")[0]
    assert income is None                                        # NULL in the table, not 0
    debits = sql(db_url, "SELECT transaction_id, debit_amount FROM transactions WHERE credit_amount IS NOT NULL "
                         "ORDER BY transaction_id")
    assert [(i, v) for i, v in debits] == [("1", None), ("2", None)]
    frame = tx_repo.to_frame([("1", dt.date(2026, 1, 1), None, Decimal("5.00"), Decimal("5.00"), "deposit")])
    assert np.isnan(frame.debit_amount.iloc[0])


def test_stored_features_are_the_hand_worked_values(db_url):  # S3-R10, S3-R11
    add_account(db_url, "TEST-A", "2025-12-01", "2026-04-01", ACCOUNT_A)
    with client(db_url) as c:
        a = assess(c, "TEST-A", "2026-04-01").json()
    assert a["income_denominator"] == 20_000
    assert_features(a["features"], A_EXPECTED)


def test_window_must_be_covered(db_url):                       # S3-R8
    seed(db_url, ["SYN-002"])                                     # covers 2025-10-01 to 2026-10-01
    with client(db_url) as c:
        assert assess(c, "SYN-002", "2026-01-01").status_code == 201    # window 2025-10-01..2026-01-01
        r = assess(c, "SYN-002", "2025-12-31")                           # window starts 2025-09-30
        assert r.status_code == 422 and "do not cover 2025-09-30" in r.json()["detail"][0]["msg"]
        assert assess(c, "SYN-002", "2026-10-01").status_code == 201    # end is exclusive
        assert assess(c, "SYN-002", "2026-10-02").status_code == 422    # a day beyond the history
        rows = DEMO_FILES[1]
        a = assess(c, "SYN-002", "2026-07-01").json()
    snap = sql(db_url, "SELECT transaction_count FROM feature_snapshots WHERE id = :i", i=a["snapshot_id"])
    mine = rows[rows.borrower_id == "SYN-002"]
    assert snap[0][0] == (mine.transaction_date < "2026-07-01").sum()   # strictly before as_of


# ---------------------------------------------------------------------------------------------
# model registry

def test_model_is_registered_once(db_url):                     # S3-R7
    for _ in range(2):
        with client(db_url) as c:
            c.get("/api/v1/health")
    rows = sql(db_url, "SELECT model_version, model_sha256, metadata_sha256, git_commit FROM model_registry")
    joblib_sha = hashlib.sha256((ROOT / "models" / "catboost-sf-v1" / "model.joblib").read_bytes()).hexdigest()
    assert len(rows) == 1 and rows[0][0] == "catboost-sf-v1" and rows[0][1] == joblib_sha
    names = run(db_url, lambda maker: _columns(maker, "model_registry"))
    assert not {n for n in names if "path" in n or "dir" in n}       # never a path to load from (D22)


async def _columns(maker, table):
    async with maker() as s:
        conn = await s.connection()
        return await conn.run_sync(lambda c: [col["name"] for col in inspect(c).get_columns(table)])


def test_changed_artifact_under_the_same_version_is_refused(db_url, tmp_path):   # S3-R7
    with client(db_url) as c:
        c.get("/api/v1/health")
    copy = tmp_path / "models" / "catboost-sf-v1"
    shutil.copytree(ROOT / "models" / "catboost-sf-v1", copy)
    meta = (copy / "metadata.json").read_text(encoding="utf-8").replace('"git_commit": "', '"git_commit": "x')
    (copy / "metadata.json").write_text(meta, encoding="utf-8")
    app = create_app(Settings(database_url=db_url, model_dir=copy), models_root=tmp_path / "models")
    with pytest.raises(RegistryMismatch):
        with TestClient(app):
            pass


# ---------------------------------------------------------------------------------------------
# endpoints

def test_endpoints(db_url):                                    # S3-R9
    seed(db_url, ["SYN-001", "SYN-013"])
    with client(db_url) as c:
        listed = c.get("/api/v1/borrowers").json()
        assert [b["id"] for b in listed] == ["SYN-001", "SYN-013"]
        assert listed[0]["latest_assessment"] is None and listed[0]["synthetic"] is True
        assert (listed[0]["history_start"], listed[0]["history_end"]) == ("2025-10-01", "2026-10-01")
        older = assess(c, "SYN-013", "2026-07-01")
        newer = assess(c, "SYN-013", "2026-10-01")
        assert older.status_code == newer.status_code == 201
        one = c.get("/api/v1/borrowers/SYN-013").json()
        assert one["latest_assessment"]["id"] == newer.json()["id"]
        assert one["latest_assessment"]["as_of"] == "2026-10-01"
        history = c.get("/api/v1/borrowers/SYN-013/assessments").json()
        assert [h["id"] for h in history] == [newer.json()["id"], older.json()["id"]]     # newest first
        assert c.get(f"/api/v1/assessments/{older.json()['id']}").json() == older.json()
        txs = c.get("/api/v1/borrowers/SYN-013/transactions", params={"start": "2026-09-01", "end": "2026-10-01"}).json()
        rows = DEMO_FILES[1]
        want = rows[(rows.borrower_id == "SYN-013") & (rows.transaction_date >= "2026-09-01")
                    & (rows.transaction_date < "2026-10-01")]
        assert [t["transaction_id"] for t in txs] == list(want.transaction_id)    # statement order
        assert c.get("/api/v1/borrowers/NOPE").status_code == 404
        assert c.get("/api/v1/borrowers/NOPE/transactions").status_code == 404
        assert assess(c, "NOPE", "2026-10-01").status_code == 404
        assert c.get("/api/v1/assessments/999999").status_code == 404
        assert c.post("/api/v1/borrowers/SYN-001/assessments", json={"as_of": "2026-10-01", "x": 1}).status_code == 422


def test_without_a_database_slice_1_still_works():              # S3-R9
    with TestClient(create_app(Settings(database_url=None))) as c:
        assert c.get("/api/v1/borrowers").status_code == 503
        assert c.get("/api/v1/health").status_code == 200


def test_same_output_as_slice_1_for_every_demo_borrower(db_url):   # S3-R10
    seed(db_url)
    borrowers, tx = DEMO_FILES
    with client(db_url) as c:
        for b in borrowers.itertuples(index=False):
            stored = assess(c, b.borrower_id, b.as_of)
            assert stored.status_code == 201, b.borrower_id
            fetched = c.get(f"/api/v1/assessments/{stored.json()['id']}").json()
            direct = c.post("/api/v1/assessments/score", json=score_script.request_body(b, tx)).json()
            assert output(fetched) == direct, b.borrower_id


# ---------------------------------------------------------------------------------------------
# seed script

def test_seed_runs_twice_without_changes(db_url):              # S3-R12
    first = seed(db_url, ["SYN-001", "SYN-002"])
    assert first == {"loaded": ["SYN-001", "SYN-002"], "unchanged": [], "differing": []}
    assert seed(db_url, ["SYN-001", "SYN-002"]) == {"loaded": [], "unchanged": ["SYN-001", "SYN-002"],
                                                    "differing": []}
    n = len(DEMO_FILES[1][DEMO_FILES[1].borrower_id.isin(["SYN-001", "SYN-002"])])
    assert sql(db_url, "SELECT COUNT(*) FROM transactions")[0][0] == n
    assert sql(db_url, "SELECT COUNT(*) FROM transaction_batches")[0][0] == 2


def test_seed_reports_a_borrower_that_differs(db_url):         # S3-R12
    seed(db_url, ["SYN-001"])
    b, start, end, tuples = PREPARED["SYN-001"]
    changed = [(*tuples[0][:2], tuples[0][2], tuples[0][3], tuples[0][4] + 1, tuples[0][5]), *tuples[1:]]
    report = run(db_url, lambda maker: seed_script.seed(maker, [(b, start, end, changed)]))
    assert report == {"loaded": [], "unchanged": [], "differing": ["SYN-001"]}
    stored = run(db_url, lambda maker: _rows(maker, "SYN-001"))
    assert fingerprint(stored) == fingerprint(tuples)              # not overwritten


async def _rows(maker, borrower_id):
    async with maker() as s:
        return await tx_repo.rows(s, borrower_id)


def test_seed_refuses_bad_files():                             # S3-R12
    borrowers, tx = (f.copy() for f in DEMO_FILES)
    borrowers.loc[0, "synthetic"] = "false"
    with pytest.raises(seed_script.SeedError, match="SYN-001: not marked synthetic"):
        seed_script.prepare(borrowers, tx)
    borrowers, tx = (f.copy() for f in DEMO_FILES)
    tx.loc[tx.index[5], "debit_amount"] = "12.345"
    with pytest.raises(seed_script.SeedError, match="more than 2 decimal places"):
        seed_script.prepare(borrowers, tx)
    borrowers, tx = (f.copy() for f in DEMO_FILES)
    tx.loc[tx.index[5], "debit_amount"] = "-5.00"
    with pytest.raises(seed_script.SeedError, match="negative"):
        seed_script.prepare(borrowers, tx)


# ---------------------------------------------------------------------------------------------
# secrets, logging and structure

def test_database_url_comes_only_from_the_environment(monkeypatch):   # S3-R4
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(ROOT / "alembic.ini", encoding="utf-8")
    assert not any(ini.has_option(section, "sqlalchemy.url") for section in ini.sections())
    secret = "postgresql+asyncpg://flowscore:s3cr3t-pw@db.example.invalid/flowscore"
    monkeypatch.setenv("FLOWSCORE_DATABASE_URL", secret)
    settings = Settings()
    assert settings.database_url.get_secret_value() == secret
    assert "s3cr3t-pw" not in repr(settings) and "s3cr3t-pw" not in str(settings.model_dump())
    for p in [*(ROOT / "backend").rglob("*.py"), *(ROOT / "alembic").rglob("*.py"), ROOT / "alembic.ini",
              *(ROOT / "scripts").glob("*.py")]:
        src = p.read_text(encoding="utf-8")
        assert not CREDENTIALS_IN_URL.search(src), p


def test_unreachable_database_error_hides_the_url(tmp_path):   # S3-R4
    url = f"sqlite+aiosqlite:///{(tmp_path / 'no-such-dir' / 'x.db').as_posix()}"
    with pytest.raises(RuntimeError) as err:
        with TestClient(create_app(Settings(database_url=url))):
            pass
    assert "no-such-dir" not in str(err.value) and "alembic upgrade head" in str(err.value)


def test_logs_hold_no_transaction_data(db_url, caplog):        # S3-R14
    add_account(db_url, "TEST-A", "2025-12-01", "2026-04-01", ACCOUNT_A)
    caplog.set_level(logging.DEBUG)
    with client(db_url) as c:
        a = assess(c, "TEST-A", "2026-04-01").json()
        assess(c, "TEST-A", "2027-01-01")
        c.get("/api/v1/borrowers/TEST-A/transactions")
    logged = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("flowscore"))
    assert f"assessment={a['id']}" in logged and "status=invalid" in logged
    for secret in ("20000", "20,000", "40100", "card_purchase", "salary", "2026-01-05", "0.857", "1.2375",
                   "aiosqlite", "test.db"):
        assert secret not in logged


def _imports(path: Path) -> set:
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def test_demo_code_stays_out():                          # S3-R13
    for p in (ROOT / "backend").rglob("*.py"):
        assert not {m for m in _imports(p) if m.split(".")[0] == "flowscore_demo"}, p
    for p in (ROOT / "src" / "flowscore").rglob("*.py"):
        assert not {m for m in _imports(p) if m.split(".")[0] in ("backend", "flowscore_demo")}, p


def test_layout_by_domain():                                   # S3-R15, S3-R11
    app = ROOT / "backend" / "app"
    for f in ("borrowers/models.py", "borrowers/repository.py", "borrowers/router.py",
              "transactions/models.py", "transactions/repository.py", "transactions/router.py",
              "features/models.py", "features/service.py", "assessments/models.py",
              "assessments/repository.py", "models/registry.py", "core/db.py"):
        assert (app / f).is_file(), f
    assert (ROOT / "alembic" / "env.py").is_file() and (ROOT / "alembic.ini").is_file()
    features = (app / "features" / "service.py").read_text(encoding="utf-8")
    assert "compute_features" in features
    assert "backend.app.assessments.service" in _imports(app / "features" / "service.py")


def test_engine_under_test(db_url):                            # S3-R16
    """SQLite unless FLOWSCORE_TEST_DATABASE_URL names a Postgres database."""
    assert make_url(db_url).get_backend_name() == ("postgresql" if TEST_URL else "sqlite")
