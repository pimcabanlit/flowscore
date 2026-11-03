"""Slice 1 scoring API (docs/specs/01-scoring-api.md). Runs in CI without Berka data.

The model here is a tiny artifact built by the same `build_artifact` the training script uses,
fitted on made-up rows whose reference ranges are set exactly (row 0 = every minimum, row 1 =
every maximum). The borrowers are made-up round-number accounts, not modelled on anyone's
statements. Every expected feature value is worked out by hand in the comments.
"""
import json
import logging
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from flowscore.experiment import make_catboost, oof_predictions
from flowscore.features.cashflow import SCALE_FREE_FEATURES

from backend.app.assessments import service
from backend.app.core.app import create_app
from backend.app.core.settings import Settings
from backend.app.models.artifact import ArtifactError, build_artifact, load_artifact

ROOT = Path(__file__).resolve().parents[1]
URL = "/api/v1/assessments/score"
RANGES = {"inflow_cv": (0.0, 1.5), "outflow_inflow_ratio": (0.5, 1.5), "months_net_outflow": (0, 3),
          "min_balance_to_income": (-1.0, 3.0), "avg_balance_to_income": (0.0, 6.0)}
CUTOFFS = {"lower_below": 50, "higher_above": 80}


def synthetic_training(n=300, seed=0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({f: rng.uniform(lo, hi, n) for f, (lo, hi) in RANGES.items()})
    X["months_net_outflow"] = rng.integers(0, 4, n).astype(float)
    X.iloc[0] = [lo for lo, _ in RANGES.values()]
    X.iloc[1] = [hi for _, hi in RANGES.values()]
    for f in ["inflow_cv", "min_balance_to_income", "avg_balance_to_income"]:
        X.loc[rng.choice(np.arange(2, n), 20, replace=False), f] = np.nan
    risk = 3 * (X.outflow_inflow_ratio - 1) + 0.5 * X.months_net_outflow - 0.3 * X.avg_balance_to_income.fillna(2)
    y = (risk + rng.normal(0, 0.7, n) > 0.6).astype(int).to_numpy()
    return X[SCALE_FREE_FEATURES], y


@pytest.fixture(scope="module")
def artifact_dir(tmp_path_factory):
    X, y = synthetic_training()
    ref = oof_predictions(X, SCALE_FREE_FEATURES, y, make=make_catboost, n_repeats=1).mean(0)
    out = tmp_path_factory.mktemp("models") / "test-sf-v0"
    build_artifact(X, y, out_dir=out, model_version="test-sf-v0", reference_scores=ref, band_cutoffs=CUTOFFS,
                   metrics={"source": "synthetic test rows"}, training_data={"dataset": "synthetic"},
                   git_commit="test")
    return out


@pytest.fixture(scope="module")
def client(artifact_dir):
    with TestClient(create_app(Settings(model_dir=artifact_dir), models_root=artifact_dir.parent)) as c:
        yield c


def tx(i, date, debit, credit, balance, category):
    return {"transaction_id": str(i), "transaction_date": date, "debit_amount": debit,
            "credit_amount": credit, "running_balance": balance, "transaction_category": category}


AS_OF = "2026-04-01"            # window [2026-01-01, 2026-04-01): Jan, Feb, Mar 2026 = 31+28+31 = 90 days

# Account A: steady salary, everything in range.
ACCOUNT_A = [
    tx(1, "2025-12-15", None, 10_000, 10_000, "deposit"),        # before the window: opening = 10,000
    tx(2, "2026-01-05", None, 20_000, 30_000, "salary"),
    tx(3, "2026-01-20", 15_000, None, 15_000, "rent"),
    tx(4, "2026-02-05", None, 20_000, 35_000, "salary"),
    tx(5, "2026-02-20", 25_000, None, 10_000, "bills"),
    tx(6, "2026-03-05", None, 30_000, 40_000, "salary"),
    tx(7, "2026-03-06", None, 100, 40_100, "interest"),           # not income
    tx(8, "2026-03-20", 20_000, None, 20_100, "card_purchase"),
]
# Hand-worked:
#   inflow by month (interest excluded): Jan 20,000  Feb 20,000  Mar 30,000   -> sum 70,000, mean 70,000/3
#   inflow_cv = population std / mean: deviations -10,000/3, -10,000/3, +20,000/3
#             std = sqrt((1+1+4)/3) * 10,000/3 = sqrt(2) * 10,000/3;  cv = sqrt(2)*10,000 / 70,000 = sqrt(2)/7
#   outflow by month: Jan 15,000  Feb 25,000  Mar 20,000  -> outflow_inflow_ratio = 60,000 / 70,000 = 6/7
#   months_net_outflow: only Feb (25,000 > 20,000) -> 1
#   income_denominator = median(20,000, 20,000, 30,000) = 20,000
#   min balance = min(opening 10,000, 30,000, 15,000, 35,000, 10,000, 40,000, 40,100, 20,100) = 10,000
#     -> min_balance_to_income = 0.5
#   daily end-of-day balance over 90 days:
#     Jan 1-4 10,000 x4 | Jan 5-19 30,000 x15 | Jan 20-Feb 4 15,000 x16 | Feb 5-19 35,000 x15 |
#     Feb 20-Mar 4 10,000 x13 | Mar 5 40,000 x1 | Mar 6-19 40,100 x14 | Mar 20-31 20,100 x12
#     sum = 40,000 + 450,000 + 240,000 + 525,000 + 130,000 + 40,000 + 561,400 + 241,200 = 2,227,600
#     avg = 2,227,600 / 90;  avg_balance_to_income = 2,227,600 / 90 / 20,000 = 5,569 / 4,500
A_EXPECTED = {"inflow_cv": math.sqrt(2) / 7, "outflow_inflow_ratio": 6 / 7, "months_net_outflow": 1.0,
              "min_balance_to_income": 0.5, "avg_balance_to_income": 5569 / 4500}

# Account B: one salary in January only -> median month inflow 0 -> income unknown.
ACCOUNT_B = [
    tx(1, "2025-12-15", None, 5_000, 5_000, "deposit"),
    tx(2, "2026-01-10", None, 20_000, 25_000, "salary"),
    tx(3, "2026-02-10", 10_000, None, 15_000, "bills"),
    tx(4, "2026-03-10", 5_000, None, 10_000, "bills"),
]
# Hand-worked:
#   inflow by month: 20,000, 0, 0 -> median 0 -> income_denominator NaN (null)
#   inflow_cv: mean 20,000/3; deviations +40,000/3, -20,000/3, -20,000/3
#              std = sqrt((4+1+1)/3) * 10,000/3 = sqrt(2) * 20,000/3 -> cv = sqrt(2)
#   outflow: 0, 10,000, 5,000 -> ratio 15,000 / 20,000 = 0.75; months_net_outflow: Feb and Mar -> 2
#   both balance-to-income features need income -> missing (not 0)
B_EXPECTED = {"inflow_cv": math.sqrt(2), "outflow_inflow_ratio": 0.75, "months_net_outflow": 2.0,
              "min_balance_to_income": None, "avg_balance_to_income": None}

# Account C: a large balance that barely moves.
ACCOUNT_C = [
    tx(1, "2025-12-01", None, 1_000_000, 1_000_000, "deposit"),
    tx(2, "2026-01-15", None, 1_000, 1_001_000, "transfer_in"),
    tx(3, "2026-02-15", None, 1_000, 1_002_000, "transfer_in"),
    tx(4, "2026-03-15", None, 1_000, 1_003_000, "transfer_in"),
]
# Hand-worked:
#   inflow 1,000 every month -> inflow_cv 0 (in range); no outflow -> ratio 0 (below 0.5: OUT)
#   months_net_outflow 0 (in range); income 1,000
#   min balance 1,000,000 -> 1,000x income (above 3: OUT)
#   daily: Jan 1-14 1,000,000 x14 | Jan 15-Feb 14 1,001,000 x31 | Feb 15-Mar 14 1,002,000 x28 |
#          Mar 15-31 1,003,000 x17 -> sum 90,138,000; avg 1,001,533.33 -> 1,001.533x income (above 6: OUT)
#   3 of 5 non-missing features out of range > half -> refused
C_EXPECTED = {"inflow_cv": 0.0, "outflow_inflow_ratio": 0.0, "months_net_outflow": 0.0,
              "min_balance_to_income": 1000.0, "avg_balance_to_income": 90_138_000 / 90 / 1_000}


def body(rows, as_of=AS_OF, history_start="2025-12-01"):
    return {"as_of": as_of, "history_start": history_start, "transactions": rows}


def assert_features(got, expected):
    assert set(got) == set(expected)
    for f, v in expected.items():
        assert got[f] == (None if v is None else pytest.approx(v, rel=1e-12, abs=1e-12)), f


# ---------------------------------------------------------------------------------------------
# hand-worked values

def test_hand_worked_account_is_scored(client):        # S1-R19, S1-R15
    r = client.post(URL, json=body(ACCOUNT_A))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "scored"
    assert out["income_denominator"] == 20_000
    assert_features(out["features"], A_EXPECTED)
    assert out["missing"] == [] and out["out_of_range"] == []
    assert 0 <= out["risk_percentile"] <= 100
    assert out["risk_band"] in {"lower", "middle", "higher"}
    assert set(out["shap"]["contributions"]) == set(SCALE_FREE_FEATURES)
    assert set(out) == {"status", "model_version", "as_of", "income_denominator", "features", "missing",
                        "out_of_range", "risk_percentile", "risk_band", "shap", "notice"}
    assert out["model_version"] == "test-sf-v0" and out["as_of"] == AS_OF


def test_missing_income_is_null_not_zero(client):     # S1-R12, S1-R19
    out = client.post(URL, json=body(ACCOUNT_B)).json()
    assert out["status"] == "scored"
    assert out["income_denominator"] is None
    assert_features(out["features"], B_EXPECTED)
    X, _ = synthetic_training()
    assert out["missing"] == [
        {"feature": f, "imputed_value": pytest.approx(float(np.nanmedian(X[f])))}
        for f in ["min_balance_to_income", "avg_balance_to_income"]]
    assert out["out_of_range"] == []               # missing is never out of range


def test_far_out_of_range_is_refused(client):         # S1-R13, S1-R19
    out = client.post(URL, json=body(ACCOUNT_C)).json()
    assert out["status"] == "refused"
    assert_features(out["features"], C_EXPECTED)
    assert out["out_of_range"] == [
        {"feature": "outflow_inflow_ratio", "value": 0.0, "min": 0.5, "max": 1.5},
        {"feature": "min_balance_to_income", "value": 1000.0, "min": -1.0, "max": 3.0},
        {"feature": "avg_balance_to_income", "value": pytest.approx(C_EXPECTED["avg_balance_to_income"]),
         "min": 0.0, "max": 6.0}]
    assert out["risk_percentile"] is None and out["risk_band"] is None and out["shap"] is None


def test_range_rule_counts_only_present_features():   # S1-R13
    ranges = {f: {"min": 0.0, "max": 1.0} for f in "abcde"}
    two_of_five = {"a": 2.0, "b": -1.0, "c": 0.5, "d": 0.5, "e": 1.0}       # edges are in range
    missing, out, refused = service.range_check(two_of_five, ranges)
    assert missing == [] and [o["feature"] for o in out] == ["a", "b"] and not refused
    three_of_five = {**two_of_five, "c": 5.0}
    assert service.range_check(three_of_five, ranges)[2]
    # 2 missing, 2 of the 3 present out of range: 2 > 1.5 -> refused; missing not flagged
    missing, out, refused = service.range_check({"a": 2.0, "b": 9.0, "c": 0.5, "d": np.nan, "e": None}, ranges)
    assert missing == ["d", "e"] and [o["feature"] for o in out] == ["a", "b"] and refused


# ---------------------------------------------------------------------------------------------
# no future information

def test_transactions_on_or_after_as_of_change_nothing(client):    # S1-R7
    base = client.post(URL, json=body(ACCOUNT_A)).json()
    later = ACCOUNT_A + [tx(90, AS_OF, None, 500_000, 520_100, "salary"),
                         tx(91, "2026-05-01", 900_000, None, -379_900, "loan_payment")]
    assert client.post(URL, json=body(later)).json() == base


def test_future_transaction_never_sets_the_opening_balance():     # S1-R7
    # Only a transaction after as_of: the window is empty, and the opening balance must not be
    # rebuilt from that later row. Same output as no transactions at all.
    cols = ["transaction_id", "transaction_date", "debit_amount", "credit_amount", "running_balance",
            "transaction_category"]
    empty = pd.DataFrame(columns=cols).astype({"transaction_date": "datetime64[ns]", "debit_amount": float,
                                               "credit_amount": float, "running_balance": float})
    future = pd.DataFrame([["1", pd.Timestamp("2026-04-02"), np.nan, 50_000.0, 80_000.0, "salary"]], columns=cols)
    (inc_f, f_f), (inc_e, f_e) = service.compute_features(future, AS_OF), service.compute_features(empty, AS_OF)
    assert math.isnan(inc_f) and math.isnan(inc_e)
    assert pd.Series(f_f).equals(pd.Series(f_e))


# ---------------------------------------------------------------------------------------------
# validation

def test_short_history_is_refused(client):            # S1-R6
    r = client.post(URL, json=body(ACCOUNT_A[1:], history_start="2026-01-02"))   # window starts 2026-01-01
    assert r.status_code == 422
    assert "history_start 2026-01-02 is later than 2026-01-01" in r.json()["detail"][0]["msg"]
    assert client.post(URL, json=body(ACCOUNT_A[1:], history_start="2026-01-01")).status_code == 200


def test_every_validation_error_is_listed(client):    # S1-R5
    bad = [tx(1, "2026-01-05", None, 100, 100, "salary"),
           tx(1, "2026-01-06", -5, None, 95, "bills"),                 # duplicate id, negative amount
           tx(2, "2026-01-07", 10, 10, 95, "bills")]                   # both debit and credit
    r = client.post(URL, json=body(bad, history_start="2026-01-05"))   # and history too short
    assert r.status_code == 422
    msgs = [e["msg"] for e in r.json()["detail"]]
    assert msgs[:3] == ["negative debit or credit amounts", "rows with both a debit and a credit",
                        "duplicate transaction ids"]
    assert "history_start" in msgs[3] and len(msgs) == 4

    # Pydantic stage: a missing field and an unknown field are both reported
    row = tx(1, "2026-01-05", None, 100, 100, "salary")
    del row["running_balance"]
    row["payee"] = "x"
    r = client.post(URL, json=body([row]))
    assert r.status_code == 422
    kinds = sorted(e["type"] for e in r.json()["detail"])
    assert kinds == ["extra_forbidden", "missing"]


def test_transactions_before_history_start_are_rejected(client):  # S1-R5
    r = client.post(URL, json=body(ACCOUNT_A, history_start="2025-12-20"))
    assert r.status_code == 422
    assert r.json()["detail"][0]["msg"] == "transactions dated before history_start"


# ---------------------------------------------------------------------------------------------
# percentile, band, SHAP, notice

def test_percentile_is_share_of_strictly_lower_scores():   # S1-R9
    ref = np.array([0.1, 0.2, 0.2, 0.4, 0.9])
    assert service.percentile(0.05, ref) == 0.0
    assert service.percentile(0.2, ref) == 20.0     # one lower (0.1); ties are not lower
    assert service.percentile(0.3, ref) == 60.0     # 0.1, 0.2, 0.2
    assert service.percentile(0.95, ref) == 100.0


def test_band_cutoffs_come_from_the_artifact(artifact_dir):  # S1-R10
    meta = json.loads((artifact_dir / "metadata.json").read_text())
    assert meta["band_cutoffs"] == {"lower_below": 50.0, "higher_above": 80.0}
    c = meta["band_cutoffs"]
    assert [service.band(p, c) for p in (0, 49.9, 50, 80, 80.1, 100)] == [
        "lower", "lower", "middle", "middle", "higher", "higher"]
    assert service.band(60, {"lower_below": 70, "higher_above": 90}) == "lower"


def test_raw_score_is_never_returned(client):          # S1-R9
    text = client.post(URL, json=body(ACCOUNT_A)).text.lower()
    assert "probab" not in text and "pd" not in json.loads(text) and "score" not in json.loads(text)


def test_percentile_matches_reference_scores(client, artifact_dir):   # S1-R9
    model = load_artifact(artifact_dir)
    X = pd.DataFrame([A_EXPECTED])[SCALE_FREE_FEATURES]
    p = model.pipeline.predict_proba(X)[0, 1]
    expected = 100 * np.mean(np.asarray(model.metadata["reference_scores"]) < p)
    assert client.post(URL, json=body(ACCOUNT_A)).json()["risk_percentile"] == pytest.approx(expected)


def test_shap_adds_up_to_log_odds(artifact_dir):        # S1-R11
    model = load_artifact(artifact_dir)
    for feats in (A_EXPECTED, B_EXPECTED):
        X = pd.DataFrame([{f: np.nan if v is None else v for f, v in feats.items()}])[SCALE_FREE_FEATURES]
        base, contrib, raw = service.shap_values(model, X)
        assert list(contrib) == SCALE_FREE_FEATURES
        assert base + sum(contrib.values()) == pytest.approx(raw, abs=1e-6)
        p = model.pipeline.predict_proba(X)[0, 1]
        assert raw == pytest.approx(math.log(p / (1 - p)), abs=1e-6)       # raw output is log-odds


def test_notice_is_always_present(client):              # S1-R14
    for rows in (ACCOUNT_A, ACCOUNT_C):
        assert client.post(URL, json=body(rows)).json()["notice"] == (
            "Relative risk among 1990s Czech borrowers. Not validated on Philippine outcomes.")


def test_health(client):                                # S1-R15
    assert client.get("/api/v1/health").json() == {"model_version": "test-sf-v0", "features": SCALE_FREE_FEATURES}


# ---------------------------------------------------------------------------------------------
# artifact

def test_artifact_contents(artifact_dir):               # S1-R3
    assert (artifact_dir / "model.joblib").is_file()
    meta = json.loads((artifact_dir / "metadata.json").read_text())
    assert {"model_version", "created_at", "git_commit", "features", "training_data", "metrics",
            "reference_ranges", "reference_scores", "band_cutoffs", "training_predictions_sha256"} <= set(meta)
    assert meta["features"] == SCALE_FREE_FEATURES
    assert meta["reference_ranges"] == {f: {"min": float(lo), "max": float(hi)} for f, (lo, hi) in RANGES.items()}
    assert len(meta["reference_scores"]) == 300


def test_artifact_with_wrong_features_is_refused(artifact_dir, tmp_path):   # S1-R4
    bad = tmp_path / "bad"
    shutil.copytree(artifact_dir, bad)
    meta = json.loads((bad / "metadata.json").read_text())
    meta["features"] = list(reversed(meta["features"]))
    (bad / "metadata.json").write_text(json.dumps(meta))
    with pytest.raises(ArtifactError, match="refusing to load"):
        load_artifact(bad)
    with pytest.raises(ArtifactError):
        with TestClient(create_app(Settings(model_dir=bad), models_root=tmp_path)):
            pass
    with pytest.raises(ArtifactError, match="no model artifact"):
        load_artifact(tmp_path / "nowhere")


def test_model_is_held_in_memory(artifact_dir, tmp_path, monkeypatch):   # S1-R17
    copy = tmp_path / "copy"
    shutil.copytree(artifact_dir, copy)
    monkeypatch.setenv("FLOWSCORE_MODEL_DIR", str(copy))
    assert Settings().resolved_model_dir(models_root=tmp_path) == copy.resolve()
    monkeypatch.delenv("FLOWSCORE_MODEL_DIR")
    assert Settings().resolved_model_dir() == ROOT / "models" / "catboost-sf-v1"
    with TestClient(create_app(Settings(model_dir=copy), models_root=tmp_path)) as c:
        shutil.rmtree(copy)                                  # requests must not need the disk
        assert c.post(URL, json=body(ACCOUNT_A)).json()["status"] == "scored"


def test_logs_hold_no_transaction_data(client, caplog):    # S1-R18
    caplog.set_level(logging.DEBUG)
    client.post(URL, json=body(ACCOUNT_A))
    client.post(URL, json=body(ACCOUNT_A, history_start="2026-02-01"))
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "status=scored" in logged and "status=invalid" in logged
    for secret in ("20000", "20,000", "40100", "card_purchase", "salary", "2026-01-05", "0.857", "1.2375"):
        assert secret not in logged


# ---------------------------------------------------------------------------------------------
# structure

def test_backend_layout_and_one_feature_library():         # S1-R16, S1-R8
    app = ROOT / "backend" / "app"
    for f in ("assessments/router.py", "assessments/schemas.py", "assessments/service.py",
              "models/artifact.py", "core/settings.py", "core/app.py"):
        assert (app / f).is_file(), f
    src = {p: p.read_text(encoding="utf-8") for p in app.rglob("*.py")}
    library = ["window_features", "opening_balance", "income_denominator", "scale_free_features",
               "window_slice", "monthly_inflows"]
    for p, text in src.items():
        for name in library:
            assert f"def {name}" not in text, f"{p} re-implements {name}"
    service_src = src[app / "assessments" / "service.py"]
    assert "from flowscore.features.cashflow import" in service_src


# ---------------------------------------------------------------------------------------------
# the committed Berka artifact (D22)

def test_committed_artifact_matches_the_research(): # S1-R1
    model = load_artifact(ROOT / "models" / "catboost-sf-v1")
    meta = model.metadata
    assert meta["model_version"] == "catboost-sf-v1"
    assert meta["training_data"]["loans"] == 682 and meta["training_data"]["defaults"] == 76
    assert meta["training_data"]["window_months"] == 3
    d21 = pd.read_csv(ROOT / "results" / "d21_scale_free.csv").set_index("model").loc["CatBoost"]
    assert meta["metrics"]["cv_auroc"] == d21.auroc_scale_free
    assert meta["metrics"]["paired_diff_ci95"] == [d21.lo, d21.hi]
    assert len(meta["reference_scores"]) == 682
    assert meta["band_cutoffs"] == {"lower_below": 50.0, "higher_above": 80.0}
    with TestClient(create_app(Settings())) as c:              # default FLOWSCORE_MODEL_DIR
        assert c.get("/api/v1/health").json()["model_version"] == "catboost-sf-v1"
        out = c.post(URL, json=body(ACCOUNT_A)).json()
    assert out["status"] == "scored" and out["risk_band"] in {"lower", "middle", "higher"}
    assert_features(out["features"], A_EXPECTED)


def test_artifacts_load_only_from_models_folder(artifact_dir):   # S1-R17
    # joblib loading can execute code, so the artifact must sit in the repo's models/ folder (D22)
    with pytest.raises(ValueError, match="outside"):
        Settings(model_dir=artifact_dir).resolved_model_dir()
    with pytest.raises(ValueError, match="outside"):
        Settings(model_dir="models/../tests").resolved_model_dir()
    with pytest.raises(ValueError, match="outside"):
        with TestClient(create_app(Settings(model_dir=artifact_dir))):
            pass
    # ...and is chosen only at startup: no request schema can carry a path, and the request code
    # never calls the loader
    from backend.app.assessments.schemas import ScoreRequest
    assert set(ScoreRequest.model_fields) == {"as_of", "history_start", "transactions"}
    for p in (ROOT / "backend" / "app" / "assessments").glob("*.py"):
        assert "load_artifact" not in p.read_text(encoding="utf-8") and "joblib" not in p.read_text(encoding="utf-8")


def test_band_labels_stay_relative(client):              # S1-R10
    for rows in (ACCOUNT_A, ACCOUNT_B, ACCOUNT_C):
        out = client.post(URL, json=body(rows))
        assert out.json()["risk_band"] in {None, "lower", "middle", "higher"}
        text = out.text.lower()
        assert "high risk" not in text and "low risk" not in text and '"high"' not in text
