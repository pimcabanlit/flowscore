import pandas as pd
from flowscore.features.application import build_application_features

def test_application_features():
    T = pd.Timestamp
    loans = pd.DataFrame({"loan_id": [1, 2], "account_id": [10, 20], "loan_date": [T("1996-01-10")] * 2,
                          "amount": [12000, 5000], "duration": [12, 24], "payments": [1000.0, 208.33]})
    accounts = pd.DataFrame({"account_id": [10, 20], "district_id": [1, 1],
                             "frequency": ["POPLATEK MESICNE", "POPLATEK TYDNE"],
                             "account_date": [T("1995-01-10"), T("1996-01-01")]})
    disp = pd.DataFrame({"disp_id": [1, 2, 3], "account_id": [10, 10, 20]})
    cards = pd.DataFrame({"disp_id": [1, 3], "card_issued": [T("1995-06-01"), T("1996-02-01")]})
    districts = pd.DataFrame({"A1": [1], "A4": [1000], "A10": [50.0], "A11": [9000],
                              "A12": ["?"], "A13": ["?"], "A14": [120]})
    f = build_application_features(loans, accounts, disp, cards, districts).set_index("loan_id")
    assert f.loc[1, "account_age_days"] == 365
    assert f.loc[2, "account_age_days"] == 9
    assert f.loc[1, "is_joint_account"] == 1 and f.loc[2, "is_joint_account"] == 0
    assert f.loc[1, "has_card_before_loan"] == 1
    assert f.loc[2, "has_card_before_loan"] == 0      # card issued after the loan date -> excluded
    assert f.loc[2, "statement_frequency"] == "weekly"
    assert pd.isna(f.loc[1, "district_unemployment_96"])  # '?' becomes missing, not zero
