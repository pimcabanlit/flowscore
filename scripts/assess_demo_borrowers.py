"""Assess every borrower in the database once, as of the end of its stored history (spec S4-R9).

    $env:PYTHONPATH="src"; $env:FLOWSCORE_DATABASE_URL="sqlite+aiosqlite:///flowscore-demo.db"
    alembic upgrade head; python scripts\\seed_demo_database.py
    python scripts\\assess_demo_borrowers.py

So the borrower list of the frontend has a band to show. Goes through the API itself
(POST /api/v1/borrowers/{id}/assessments on an in-process app with the committed model), so the
result is exactly what the frontend's "Run assessment" button would store. A borrower that
already has an assessment is skipped, so a second run adds nothing. Prints ids only.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))            # for backend.app

from fastapi.testclient import TestClient                       # noqa: E402

from backend.app.core.app import create_app                      # noqa: E402
from backend.app.core.settings import Settings                   # noqa: E402


def assess_all(settings: Settings = None) -> dict:
    """{assessed, skipped}: borrower ids. The as_of is the borrower's history_end from the API
    (the first day after its stored batches), so the window is the last 3 months it covers."""
    report = {"assessed": [], "skipped": []}
    with TestClient(create_app(settings or Settings())) as c:
        borrowers = c.get("/api/v1/borrowers")
        borrowers.raise_for_status()
        for b in borrowers.json():
            if b["latest_assessment"] is not None or b["history_end"] is None:
                report["skipped"].append(b["id"])
                continue
            r = c.post(f"/api/v1/borrowers/{b['id']}/assessments", json={"as_of": b["history_end"]})
            r.raise_for_status()
            report["assessed"].append(b["id"])
    return report


def main():
    report = assess_all()
    print(f"assessed {len(report['assessed'])}: {', '.join(report['assessed']) or '-'}")
    print(f"skipped (already assessed or no history) {len(report['skipped'])}: {', '.join(report['skipped']) or '-'}")


if __name__ == "__main__":
    main()
