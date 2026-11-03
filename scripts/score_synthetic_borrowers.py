"""Score every synthetic demo borrower through the scoring API (spec S2-R9, S2-R10).

    $env:PYTHONPATH="src"; python scripts\\score_synthetic_borrowers.py

Posts each borrower in demo/synthetic/ to POST /api/v1/assessments/score on an in-process copy
of the app, with the committed model (models/catboost-sf-v1/), and prints a Markdown table:
persona, status, percentile, band, top SHAP driver and out-of-range flags. A refused borrower is
listed with its flags, never dropped. The band is whatever the model returns; nothing here sets it.
Prints synthetic data only.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))            # for backend.app

from fastapi.testclient import TestClient                       # noqa: E402

from flowscore_demo.synthetic import read                             # noqa: E402

from backend.app.core.app import create_app                      # noqa: E402

URL = "/api/v1/assessments/score"


def request_body(borrower, tx) -> dict:
    """The score request for one borrower, from the rows as written (empty cell -> null)."""
    rows = tx[tx.borrower_id == borrower.borrower_id]
    num = lambda v: float(v) if v != "" else None
    return {"as_of": borrower.as_of, "history_start": borrower.history_start,
            "transactions": [{"transaction_id": r.transaction_id, "transaction_date": r.transaction_date,
                              "debit_amount": num(r.debit_amount), "credit_amount": num(r.credit_amount),
                              "running_balance": float(r.running_balance),
                              "transaction_category": r.transaction_category}
                             for r in rows.itertuples(index=False)]}


def top_driver(shap: dict) -> str:
    """The feature with the largest absolute contribution, with its sign (+ = toward higher risk)."""
    if not shap:
        return ""
    f, v = max(shap["contributions"].items(), key=lambda kv: abs(kv[1]))
    return f"{f} ({v:+.2f})"


def score_all(client, folder=ROOT / "demo" / "synthetic") -> list:
    borrowers, tx = read(folder)
    out = []
    for b in borrowers.itertuples(index=False):
        r = client.post(URL, json=request_body(b, tx))
        r.raise_for_status()
        out.append((b, r.json()))
    return out


def main():
    with TestClient(create_app()) as client:
        results = score_all(client)
    print("| Borrower | Persona | Status | Percentile | Band | Top SHAP driver | Out of range |")
    print("|---|---|---|---|---|---|---|")
    for b, s in results:
        pct = "" if s["risk_percentile"] is None else f"{s['risk_percentile']:.1f}"
        flags = ", ".join(o["feature"] for o in s["out_of_range"]) or "none"
        print(f"| {b.borrower_id} | {b.persona} | {s['status']} | {pct} | {s['risk_band'] or ''} | "
              f"{top_driver(s['shap'])} | {flags} |")


if __name__ == "__main__":
    main()
