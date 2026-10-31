# FlowScore AI: research core

Does bank transaction data predict loan default better than application data?
Tested on the public Berka/PKDD'99 dataset (682 loans, 76 defaults) with leakage-checked
features, repeated cross-validation and bootstrap confidence intervals.

**Headline:** transaction features beat application features by +0.16 to +0.23 AUROC
for logistic regression, random forest and CatBoost.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
Put the unzipped Berka CSVs (loan, account, trans, disp, card, district, client, order) in `data/raw/`.
They are not committed to the repo.

## Run
```bash
PYTHONPATH=src pytest -q tests                 # golden test runs only if data/raw/ exists
PYTHONPATH=src python scripts/run_research.py  # all results -> results/
```

## Layout
- `src/flowscore/schema.py`: the canonical transaction schema every feature works on
- `src/flowscore/features/cashflow.py`: **the feature library**: research features, obligation
  features (debt service, rent, reimbursements, fees) and the 12-month salary baseline
- `src/flowscore/adapters/berka.py`: Berka codes -> canonical schema
- `src/flowscore/features/application.py`, `transactions.py`: Berka entry points for the research
- `src/flowscore/experiment.py`: feature sets, models, CV, bootstrap
- `scripts/run_research.py`, `scripts/run_tabpfn.py`: RQ1–RQ5 end to end
- `tools/`: local-only BPI statement parser, verifier and personal feature runner
- `results/`: output CSVs and run log; `results/features.csv` is the golden file for
  `tests/test_berka_golden.py`

## Privacy
Never commit personal bank statements. Keep them in `personal/` (git-ignored) and use them locally only.
