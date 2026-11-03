# FlowScore AI: research core

Does bank transaction data predict loan default better than application data?
Tested on the public Berka/PKDD'99 dataset (682 loans, 76 defaults) with leakage-checked
features, repeated cross-validation and bootstrap confidence intervals.

**Headline:** transaction features beat application features by +0.16 to +0.23 AUROC
for logistic regression, random forest and CatBoost.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-lock.txt   # exact verified versions (Python 3.12)
```
Put the unzipped Berka CSVs (loan, account, trans, disp, card, district, client, order) in `data/raw/`.
They are not committed to the repo.

## Run
```bash
PYTHONPATH=src pytest -q tests                 # golden test runs only if data/raw/ exists
PYTHONPATH=src python scripts/run_research.py  # all results -> results/
PYTHONPATH=src python scripts/train_app_model.py  # app model -> models/catboost-sf-v1/
PYTHONPATH=src uvicorn backend.app.main:app       # scoring API: POST /api/v1/assessments/score
```

## Database (slice 3, optional)
The API stores borrowers, transactions, feature snapshots and assessments when
`FLOWSCORE_DATABASE_URL` is set (never in a file; see `docs/specs/03-database.md` and D24).
Without it, the scoring API works as before and the database endpoints answer 503.
```powershell
$env:PYTHONPATH="src"
# Offline: a local SQLite file (git-ignored). Or Neon: copy the *direct* (not pooled) connection
# string and write it as postgresql+asyncpg://USER:PASSWORD@HOST/DBNAME?ssl=require
$env:FLOWSCORE_DATABASE_URL="sqlite+aiosqlite:///flowscore-demo.db"
alembic upgrade head                           # create the tables
python scripts\seed_demo_database.py           # load the 30 synthetic demo borrowers
uvicorn backend.app.main:app                   # then POST /api/v1/borrowers/SYN-001/assessments {"as_of": "2026-10-01"}
alembic downgrade base                         # remove every table (and every stored assessment)
```
`pytest` runs the database tests on a temporary SQLite file. To run them on Postgres as well, set
`FLOWSCORE_TEST_DATABASE_URL` to an empty database whose name contains `test` (the tests wipe it).

## Layout
- `src/flowscore/schema.py`: the canonical transaction schema every feature works on
- `src/flowscore/features/cashflow.py`: **the feature library**: research features, obligation
  features (debt service, rent, reimbursements, fees) and the 12-month salary baseline
- `src/flowscore/adapters/berka.py`: Berka codes -> canonical schema
- `src/flowscore/features/application.py`, `transactions.py`: Berka entry points for the research
- `src/flowscore/experiment.py`: feature sets, models, CV, bootstrap
- `scripts/run_research.py`, `scripts/run_tabpfn.py`: RQ1–RQ5 end to end
- `backend/app/`: the FastAPI app, by domain (borrowers, transactions, features, assessments,
  models); `alembic/` holds the database migrations
- `tools/`: local-only BPI statement parser, verifier and personal feature runner
- `results/`: output CSVs and run log; `results/features.csv` is the golden file for
  `tests/test_berka_golden.py`

## Privacy
Never commit personal bank statements. Keep them in `personal/` (git-ignored) and use them locally only.

## Contributing
Changes land through pull requests: see "How changes land" in `CLAUDE.md`, `REVIEW.md` for what
reviewers check and the risk tiers, and the PR template in `.github/`. `main` requires the
`tests` CI check to pass.
