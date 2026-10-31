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

## Open

**O1. How the app handles the Berka -> Philippines gap.** The model learned from Czech 1990s
borrowers in koruna. Absolute amounts (balances, income) do not transfer; scale-free features
(ratios, counts, volatility) transfer better but are still unvalidated on Philippine outcomes.
Decide before slice 1.
