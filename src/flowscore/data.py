"""Load the Berka tables with parsed dates."""
import pandas as pd
from flowscore.window import parse_berka_date

def load_berka(raw="data/raw/"):
    rd = lambda f: pd.read_csv(raw + f, sep=";", low_memory=False)
    t = {k: rd(k + ".csv") for k in ["loan", "account", "disp", "card", "district", "trans"]}
    t["loan"]["loan_date"] = parse_berka_date(t["loan"]["date"])
    t["loan"]["bad"] = t["loan"]["status"].isin(["B", "D"]).astype(int)
    t["account"]["account_date"] = parse_berka_date(t["account"]["date"])
    t["card"]["card_issued"] = parse_berka_date(t["card"]["issued"])
    t["trans"]["trans_date"] = parse_berka_date(t["trans"]["date"])
    return t
