"""Golden test: the Berka features must equal the committed results/features.csv exactly.

Guards the research results against any change to the feature code. Skipped when the raw
Berka CSVs are not in data/raw/ (they are not committed to the repo).
"""
import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW, GOLDEN = ROOT / "data" / "raw", ROOT / "results" / "features.csv"


@pytest.mark.skipif(not (RAW / "trans.csv").exists(), reason="Berka raw data not present")
def test_berka_features_match_golden_file():
    from flowscore.data import load_berka
    from flowscore.features.application import build_application_features
    from flowscore.features.transactions import build_transaction_features

    t = load_berka(str(RAW) + "/")
    app = build_application_features(t["loan"], t["account"], t["disp"], t["card"], t["district"])
    tx = build_transaction_features(t["loan"], t["trans"], months=3)
    df = app.merge(tx, on="loan_id").merge(t["loan"][["loan_id", "bad"]], on="loan_id")
    new = pd.read_csv(io.StringIO(df.to_csv(index=False)))      # same CSV round-trip as the golden file
    gold = pd.read_csv(GOLDEN)

    assert list(new.columns) == list(gold.columns) and len(new) == len(gold)
    for c in gold.columns:
        if pd.api.types.is_numeric_dtype(gold[c]):
            assert (gold[c].isna() == new[c].isna()).all(), c
            assert np.array_equal(gold[c].fillna(0).to_numpy(), new[c].fillna(0).to_numpy()), c
        else:
            assert (gold[c].fillna("") == new[c].fillna("")).all(), c
