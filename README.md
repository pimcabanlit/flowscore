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
PYTHONPATH=src pytest -q tests                 # 4 tests
PYTHONPATH=src python scripts/run_research.py  # all results -> results/
```

## Layout
- `src/flowscore/window.py`: 3-month pre-loan observation window
- `src/flowscore/features/`: application and transaction features
- `src/flowscore/experiment.py`: feature sets, models, CV, bootstrap
- `scripts/run_research.py`: RQ1–RQ5 end to end
- `results/`: output CSVs and run log

## Privacy
Never commit personal bank statements. Keep them in `personal/` (git-ignored) and use them locally only.
