# Decision log

Each entry: what was decided, why, and what would reopen it. Newest decisions go at the bottom.

## Data

**D1. Research uses Berka/PKDD'99; synthetic data is demo-only.**
No Philippine lender data was available. Synthetic borrowers with generated default labels would
make the research circular (the model rediscovers the generator's rules). Berka is real behaviour
with real outcomes, and its size (682 loans, 76 defaults) is close to the Malaysian paper's.
*Reopen if:* real labelled Philippine lender data becomes available.

**D2. Default = Berka status B or D.**
B = finished, not paid; D = running, in debt. Standard on this dataset. Berka has no days-past-due
field, so the spec's "90+ DPD in 12 months" cannot apply; the target is defined per dataset.

**D3. 3-month observation window, strictly before the loan date.**
Every account has at least 3.4 months of history, so 3 months keeps all 76 defaults. A 6-month
window would drop 15 of them (20%). Transactions on the loan day itself are excluded.

**D4. The owner's bank statements are local-only validation data.**
Used to calibrate realism and check that features measure what their names claim. Never
committed, never used as research evidence, never placed in the demo.

## Features

**D5. Sex and birth date excluded** (fairness; spec FR-01). District columns remain and are
potential proxies; a fairness audit is future work.

**D6. `is_joint_account` excluded from main results.**
145 joint accounts, 0 defaults (perfect separation), and the `disp` table has no dates, so the
second holder may have been added after the loan. It breaks the no-future-information rule.
Kept as a sensitivity check: adding it lifts LR application-only from 0.654 to 0.751 AUROC.

**D7. Bank interest is not income.** Credits categorised `interest` are excluded from
`avg_monthly_inflow`.

**D8. Balances are standardised, not log-transformed** (disclosed change).
The first version used a signed log that jumps around zero and distorted SHAP values. Changed
after seeing SHAP output; moved LR transactions-only from 0.801 to 0.810 (inside the CI). All
reported numbers use the final version.

**D9. Debt ratios use take-home salary.**
Payroll credits are net of tax and contributions; lenders usually use gross income. Our ratios
therefore run higher, which is the conservative direction.

**D10. Two debt views: conservative and net.**
Money is fungible: transfers in that reimburse card spending look like income. `debt_service_ratio`
(gross card + loan payments / salary) is the lender view; `net_debt_service_ratio` subtracts
transfers the owner labels `reimbursement`. The gap between them is itself informative.

**D11. Salary baseline = median of up to 12 full calendar months before as-of.**
3-month salary totals jump when a window holds 5 vs 6 paydays or a bonus. A median ignores one
odd month. Partial months are excluded; zero-pay months count as 0 (a real income stop must show).
Missing until 3 full months exist.

**D12. Payee names live in a private rules file**, `personal/category_rules.csv`, checked
before the built-in rules, so names of landlords, lenders and friends never reach the repo.

## Evaluation

**D13. Repeated stratified 5-fold CV, no separate test set.**
A 20% holdout would leave about 15 defaults. Repeated CV tests every loan many times. Nothing is
tuned on the evaluation folds, so there is no optimistic bias for a holdout to catch.

**D14. Bootstrap 95% CIs and paired differences for every comparison.**
Overlapping CIs can hide consistent gaps; paired tests answer "is A better than B?" directly.

**D15. Tree models use fixed sensible constraints, not defaults and not tuning.**
Defaults overfit a few hundred rows (the Malaysian paper's weakness); tuning on the evaluation
folds inflates scores. Nested CV tuning is future work.

## Models

**D16. App model = CatBoost; LR + Platt is the transparent benchmark; TabPFN is the ceiling.**
TabPFN scored best (0.863 combined) but only +0.013 over CatBoost (CI includes zero), costs about
12 s per fit on CPU, gives slow explanations and has a licence restricting commercial use.

**D17. CatBoost is used without extra calibration.**
Platt scaling over-corrected it (slope 0.77 -> 1.31) and worsened ECE. LR does get Platt scaling
(slope 0.72 -> 1.09).

## Engineering

**D18. One canonical transaction schema; sources get adapters.**
`features/cashflow.py` is the only feature implementation. Berka goes through
`adapters/berka.py`; BPI statements come out of the parser already in the schema. The refactor
reproduced every research output byte for byte; `tests/test_berka_golden.py` guards this.

**D19. PDF extraction is a local tool, not an app feature** (spec 4.2 keeps OCR/PDF out of
scope). BPI PDFs are rebuilt with qpdf (pikepdf) before parsing because some have a damaged page
index that hides pages from pdfplumber.

**D20. Backend organised by domain, not by technical type.** Follows the owner's stack
conventions; overrides spec section 9.3.

## App

**D21. The app scores on a scale-free feature set and reports a relative risk band, not a PD.**
Closes O1 (how the app handles the Berka -> Philippines gap). The model learned from Czech 1990s
borrowers in koruna, so absolute amounts (balances, income) mean nothing for a PHP account, and
converting currencies across 30 years and two economies has no empirical basis.
- *Income denominator:* `income_denominator` in `features/cashflow.py`, the median monthly inflow
  excluding interest over the window's month buckets. One definition for every data source; not
  salary, because Berka has no salary category. NaN when the median is not positive.
- *Feature set* (`SCALE_FREE_FEATURES`): `inflow_cv`, `outflow_inflow_ratio`, `months_net_outflow`,
  `min_balance_to_income`, `avg_balance_to_income`. Dropped: `avg_monthly_inflow`, `min_balance`,
  `avg_daily_balance` (absolute amounts), `days_negative_balance` and `penalty_interest_count`
  (Czech overdraft mechanics; Philippine savings accounts rarely go negative), `tx_count`
  (driven by banking habits, e.g. many small InstaPay transfers).
- *Output:* the borrower's percentile among the Berka reference borrowers, with a permanent
  "not validated on Philippine outcomes" notice. No calibrated PD is claimed.
- *Out-of-range inputs:* the reference range of each feature is its min-max in the training data
  (outside it, trees extrapolate flat and the model has never seen the case). Each feature outside
  it is flagged in the response; scoring is refused only if more than half the features are out of
  range. Missing values are reported as missing, not as out of range.
- *Measured cost* (`scripts/run_scale_free.py`, same folds and bootstrap resamples as
  `run_research.py`, paired; `results/d21_scale_free.csv`): CatBoost 0.831 -> 0.791 AUROC,
  paired difference -0.034 [95% CI -0.077, +0.008]; LR 0.810 -> 0.770, -0.038 [-0.101, +0.028].
  Both CIs include zero: a real but modest cost, and the scale-free set keeps most of the
  transaction signal (application-only CatBoost is 0.604). The 0.831 reproduces results/rq1_rq2.csv.
  Income is NaN for 28 loans (median month had no inflow); 10 of them defaulted (36% vs 11%
  overall). The imputer fills them with the median, so this signal is currently unused.
Research results are unchanged: the research feature path and `results/` are untouched.
*Reopen if:* labelled Philippine outcomes become available (then validate or retrain), or the
measured cost is large enough that a different transfer approach is worth trying.

**D22. Slice 1 artifact choices: committed model, out-of-fold reference, 50/80 band cut-offs.**
Answers the slice 1 spec's open questions 1 to 4. Confirmed by owner (2026-11-03).
- *Artifact committed:* `models/catboost-sf-v1/` is committed, like `results/features.csv`: it is
  small and derived from public Berka data. Most API tests build a tiny artifact from made-up
  rows with the same `build_artifact`; one test checks the committed artifact against
  `results/d21_scale_free.csv`. CI never needs Berka data.
- *Loading is code execution:* `model.joblib` is a pickle, and loading it can run code. So the
  artifact folder is chosen once at startup from `FLOWSCORE_MODEL_DIR`, must resolve inside the
  repo's `models/` folder (anything else is refused), and is never named by a request. Changes
  to `models/` are High tier and are read by hand before merging.
- *Percentile reference:* each Berka loan's out-of-fold CatBoost score, averaged over the 10
  repeats of the D21 folds. In-sample scores are overfitted and push known defaulters to the
  extremes, which would make a new borrower look safer than they are. The training script checks
  that these scores reproduce the D21 CV AUROC before it writes anything.
- *Band cut-offs:* `lower` below the 50th percentile, `middle` from 50 to 80, `higher` above 80,
  so roughly the top fifth of the reference population is flagged. Stored in the artifact's
  `metadata.json`, not in the service code. Bands are always relative ("lower / middle / higher
  relative risk" among the Berka reference borrowers), never an absolute label such as "high risk".
- *Dependencies:* `fastapi`, `uvicorn` and FastAPI's own dependencies were added to the lock.
  `httpx2` (the test client) was already locked, but only as a TabPFN dependency, so it is listed
  in `requirements.txt` explicitly.
*Reopen if:* a lender needs a different share flagged, or Philippine outcomes allow calibration.

**D23. Slice 2 demo borrowers: patterns from public figures, savings-account rules, committed.**
Answers the slice 2 draft spec's open questions. Confirmed by owner (merged in #11, 2026-11-03).
- *No new categories:* InstaPay and PESONet fees are `fee` rows next to their transfer, which
  uses `transfer_in`, `transfer_out`, `rent` or `loan_payment`. `schema.py` (High tier) is untouched.
- *30 borrowers, 6 per persona,* enough for the borrower list and portfolio views of later slices.
- *Near zero, not overdraft:* Philippine savings and payroll accounts rarely go negative (D21), so
  the fifth persona runs its balance down to zero and never below. A cash withdrawal is cut to
  what the account holds; any other debit it cannot cover is declined, never charged in part.
- *Dated fee schedule:* PHP 25 InstaPay and PHP 50 PESONet until 2026-06-30, free from 2026-07-01,
  when the big banks waived both. The 12-month history (2025-10 to 2026-09) spans the change, as
  a real statement would.
- *Committed demo data:* `demo/synthetic/` is committed, regenerated byte for byte by a test, and
  marked `synthetic: true` on every borrower. Names are "Demo Borrower nn", and there is no
  payee column, so nothing can resemble a real person.
- *Generator in `src/flowscore_demo/synthetic.py`*, a package of its own outside the research
  package `flowscore` (moved there in #13; #11 first put it in `src/flowscore/`). It
  imports `flowscore.schema`; nothing in `src/flowscore/` may import it (S2-R12), so research code
  can never use synthetic data (hard rule 9). Slice 3 can seed the database from the same code.
*Reopen if:* the demo needs a persona the D21 features cannot tell apart, or real patterns
(not amounts) from the owner's statements show a habit the generator misses.

## Open questions

**O2. Use the "income missing" signal?** Income is NaN for 28 Berka loans (the median month had
no inflow), and 10 of them defaulted: 36% against 11% overall. The D21 model imputes the median,
so this signal is unused. An "income missing" flag as a sixth feature would likely help, but it
changes the D21 numbers, so it needs its own decision entry, a rerun of
`scripts/run_scale_free.py` and a new artifact version. It also needs a check that a missing
income means the same thing for a Philippine statement as for Berka. For a later slice.
