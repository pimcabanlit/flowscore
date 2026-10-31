import numpy as np
import pandas as pd
import pytest
from flowscore.features.transactions import build_transaction_features, loan_features

T = pd.Timestamp
LOAN = T("1996-04-01")   # window = 1996-01-01 .. 1996-03-31 (91 days)

def tx(rows):
    return pd.DataFrame(rows, columns=["trans_id", "trans_date", "type", "amount", "balance", "k_symbol"]) \
             .assign(trans_date=lambda d: pd.to_datetime(d.trans_date))

def test_hand_calculated_example():
    t = tx([
        (1, "1996-01-05", "PRIJEM", 1000, 1500, None),        # month 3 (oldest): inflow 1000
        (2, "1996-01-20", "VYDAJ",   300, 1200, "SIPO"),      #                  outflow 300
        (3, "1996-02-10", "PRIJEM", 1000, 2200, None),        # month 2: inflow 1000
        (4, "1996-02-28", "PRIJEM",   10, 2210, "UROK"),      #   bank interest -> not income
        (5, "1996-03-05", "VYBER",  2500, -290, None),        # month 1: outflow 2500, goes negative
        (6, "1996-03-06", "VYDAJ",    20, -310, "SANKC. UROK"),  # penalty, outflow 20
        (7, "1996-03-15", "PRIJEM", 1600, 1290, None),        # inflow 1600
    ])
    f = loan_features(t, LOAN, opening_balance=500)
    assert f["avg_monthly_inflow"] == pytest.approx(3600 / 3)
    assert f["inflow_cv"] == pytest.approx(np.std([1000, 1000, 1600]) / 1200)
    assert f["min_balance"] == -310
    assert f["days_negative_balance"] == 10          # Mar 5 .. Mar 14
    assert f["penalty_interest_count"] == 1
    assert f["months_net_outflow"] == 1              # only March: 2520 out > 1600 in
    assert f["outflow_inflow_ratio"] == pytest.approx(2820 / 3600)
    assert f["tx_count"] == 7
    # daily balance: Jan1-4 500(4d), Jan5-19 1500(15), Jan20-Feb9 1200(21), Feb10-27 2200(18),
    # Feb28-Mar4 2210(6), Mar5 -290(1), Mar6-14 -310(9), Mar15-31 1290(17)  = 91 days
    exp = (500*4 + 1500*15 + 1200*21 + 2200*18 + 2210*6 - 290 - 310*9 + 1290*17) / 91
    assert f["avg_daily_balance"] == pytest.approx(exp)

def test_no_transactions_is_handled():
    f = loan_features(tx([]), LOAN, opening_balance=800)
    assert f["avg_monthly_inflow"] == 0 and np.isnan(f["inflow_cv"])   # unavailable, not zero
    assert f["avg_daily_balance"] == 800 and f["min_balance"] == 800 and f["tx_count"] == 0


def test_build_scale_free_features_berka_path():
    # same hand example; the Berka entry point must give the canonical-schema numbers (D21)
    t = tx([
        (1, "1996-01-05", "PRIJEM", 1000, 1500, None), (2, "1996-01-20", "VYDAJ", 300, 1200, "SIPO"),
        (3, "1996-02-10", "PRIJEM", 1000, 2200, None), (4, "1996-02-28", "PRIJEM", 10, 2210, "UROK"),
        (5, "1996-03-05", "VYBER", 2500, -290, None), (6, "1996-03-06", "VYDAJ", 20, -310, "SANKC. UROK"),
        (7, "1996-03-15", "PRIJEM", 1600, 1290, None),
    ]).assign(account_id=9)
    loans = pd.DataFrame({"loan_id": [1], "account_id": [9], "loan_date": [LOAN]})
    f = build_transaction_features(loans, t, scale_free=True).iloc[0]
    assert f["income"] == 1000                                   # median(1600, 1000, 1000)
    assert f["min_balance_to_income"] == pytest.approx(-0.31)
    assert f["months_net_outflow"] == 1
