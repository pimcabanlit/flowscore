import pandas as pd
from flowscore.window import observation_window

def test_window_bounds():
    loans = pd.DataFrame({"loan_id": [1], "account_id": [10],
                          "loan_date": [pd.Timestamp("1995-06-15")]})
    trans = pd.DataFrame({"account_id": [10]*5 + [99],
        "trans_date": pd.to_datetime(["1995-03-14", "1995-03-15", "1995-06-14",
                                      "1995-06-15", "1995-07-01", "1995-05-01"])})
    out = observation_window(loans, trans, months=3)
    # keeps 03-15 (start, inclusive) and 06-14; drops before start, loan day, after, other account
    assert list(out.trans_date.dt.strftime("%m-%d")) == ["03-15", "06-14"]
