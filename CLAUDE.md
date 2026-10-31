# FlowScore AI

Explainable, cash-flow-based credit risk assessment for individual borrowers (initial context:
unsecured personal loans, Philippines). Portfolio project: a research study plus an app.
The owner is building this to learn and to defend it in interviews, so explain decisions
plainly, work in small verified steps, and say what each step proves.

Full research write-up (methods, results, limitations, defence guide):
https://claude.ai/artifact/2axzRJypSYyHAj7AULgjR7
Why things are the way they are: `docs/decisions.md`. Read it before changing anything it covers.

## Current state

- **Research core: done.** Berka/PKDD'99 (682 loans, 76 defaults). Transaction features beat
  application features by +0.16 to +0.23 AUROC across LR, random forest, CatBoost and TabPFN.
  Results in `results/`, reproducible exactly.
- **BPI statement tools: done** (`tools/`), local use only.
- **Feature library: done.** `src/flowscore/features/cashflow.py` on the canonical schema,
  guarded by a golden test.
- **App: not started.** Next is slice 1 (see "App plan").

## Layout

```
src/flowscore/
  schema.py               canonical transaction schema + category vocabulary + validate()
  features/cashflow.py    THE feature library: window, obligation and salary-baseline features
  features/application.py Berka application features (research only)
  features/transactions.py Berka entry points -> cashflow.py (research only)
  adapters/berka.py       Berka codes -> canonical schema
  window.py, data.py      Berka loading and observation window
  experiment.py           feature sets, models, CV, bootstrap helpers
scripts/run_research.py   RQ1-RQ5 end to end (~10 min)
scripts/run_tabpfn.py     TabPFN on the same folds (~50 min CPU; needs TABPFN_TOKEN)
tools/bpi_parser.py       BPI statement PDF -> canonical CSV (local only)
tools/verify_transactions.py  reconcile parsed CSV against statement totals
tools/personal_features.py    features on the owner's own statements
tests/                    unit tests, hand-calculated values; golden test vs results/features.csv
results/                  research outputs (committed); features.csv is the golden file
data/raw/                 Berka CSVs (NOT committed)
personal/                 owner's statements, transactions.csv, category_rules.csv (NOT committed)
```

## Commands

Owner's machine: Windows 11 on ARM, PowerShell, x64 Python 3.12 venv in `.venv`
(the ARM64 Python could not install CatBoost). Give PowerShell commands.

```powershell
.venv\Scripts\Activate.ps1
$env:PYTHONPATH="src"; pytest -q tests        # 33 tests; golden test needs data/raw/
python scripts\run_research.py                # must reproduce results/ byte for byte
python tools\bpi_parser.py personal\statements -o personal\transactions.csv
python tools\verify_transactions.py personal\transactions.csv
python tools\personal_features.py personal\transactions.csv
```

26 tests; the golden test skips without `data/raw/` and must be run locally (or anywhere the
Berka data is present) before merging any change to `src/flowscore/`, `tools/` or `results/`.
Install from `requirements-lock.txt` (the owner's verified environment), not `requirements.txt`.

## How changes land

Human attention is the scarce resource: checks do most of the reading, the owner reads by risk,
and every change must be cheap to undo.

1. **Branch.** Work on a branch. Never push to `main`.
2. **Verify before opening a PR**, and paste the real command output into the PR description:
   - `$env:PYTHONPATH="src"; pytest -q tests`: everything passes.
   - **Research-frozen paths** (`src/flowscore/features/`, `adapters/`, `schema.py`, `window.py`,
     `experiment.py`, `results/`): paste output **from the owner's machine** (or anywhere the
     Berka data is present) showing every test passed and none skipped, then
     `python scripts\run_research.py` followed by `git diff --exit-code results/` exiting 0.
     Without that evidence the PR is not ready.
   - **Privacy check:** `git status` shows nothing from `personal/` or `data/`, and no new
     `print` or log line in `tools/` outputs unmasked transaction data (use `_mask`).
   - **UI changes** (once the frontend exists): open the page in a browser, exercise the change,
     and attach a screenshot made with synthetic data only.
3. **Open a PR** with Summary, Testing (the output above), Risk tier, and How to revert.
4. **Answer every review finding:** fix it, or reply with why not. None left silent.
5. **The owner merges.** Claude never merges and never calls a PR ready before its CI is green.
6. **Whoever asked for the change owns it after it lands**, including the revert if it breaks.

## Hard rules

1. **Privacy.** Never commit, print into logs, paste into prompts, or send anywhere anything from
   `personal/` or `data/`. Never put the owner's real figures in code, tests, fixtures, docs or
   screenshots. Payee names belong in `personal/category_rules.csv`, never in code. Check
   `git status` before every commit.
2. **No future information.** Features use only transactions strictly before the as-of date
   (`window_slice`). A field whose timing cannot be verified is excluded (see the joint-account
   decision).
3. **Research results are frozen.** Any change to feature code must keep
   `tests/test_berka_golden.py` passing and `run_research.py` output identical. If a result
   must change, it is a deliberate decision: record it in `docs/decisions.md` and the write-up.
4. **One feature library.** All cash-flow features live in `features/cashflow.py` on the canonical
   schema. Data sources get adapters; the app never re-implements a feature.
5. **Deterministic finance, grounded LLM.** Numbers come from code. An LLM may only summarise
   verified outputs (spec FR-08 B).
6. **Missing is not zero.** Unknown values are NaN, never 0.
7. **Tests with hand-worked expected values** for every new feature or financial calculation.
8. **Secrets** (TABPFN_TOKEN, HF token, Azure keys, DB URLs) come from environment variables only.
9. **Synthetic data is for the demo only**, never reported as evidence for a research question.
10. Don't bump dependencies as a side effect; flag any new framework or paid service.

## Conventions for the app

Follow the owner's default stack (Next.js App Router + TypeScript strict, Tailwind/shadcn,
FastAPI + Pydantic v2, SQLAlchemy 2 async + asyncpg, Alembic, Neon Postgres, `/api/v1` rewrites,
clean architecture core -> domain -> infrastructure, repository pattern, one LLM model-manager
module). **Organise backend code by domain** (borrowers, transactions, features, assessments,
models), not by technical type; this overrides section 9.3 of the spec.

## App plan (thin slices; each must work end to end before the next)

1. **Scoring API.** Train the app model once (CatBoost, transaction features) and save it as a
   versioned artifact with its feature list, training data version and metrics. FastAPI
   endpoint: canonical transactions in -> features + PD + SHAP contributions out. No DB yet.
   The Berka -> Philippines gap is settled by D21: scale-free features (`SCALE_FREE_FEATURES`),
   a relative risk band instead of a PD, per-feature out-of-range flags.
2. **Synthetic Philippine borrowers** for the demo, calibrated on statement *patterns*
   (semi-monthly payroll, InstaPay fees, card payments), never the owner's amounts.
3. **Database:** borrowers, transactions, feature snapshots, assessments, model registry.
4. **Frontend:** borrower list, borrower cash-flow view, assessment page (PD + SHAP).
5. **Extras:** portfolio analytics, LLM narrative, settings. Vintage/migration analysis is out
   of scope for v1 (no outcome history).

## Known limitations to keep in mind

Czech 1990s data; small sample; running loans labelled good; only approved loans; thin Berka
application data; take-home (not gross) salary; money is fungible (reimbursements and support
look like income without labels); TabPFN licence restricts commercial use.
