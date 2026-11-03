# Slice 1: Scoring API

## Goal

A single API call takes one borrower's canonical transactions and an as-of date. It returns the
D21 scale-free features, a relative risk band, and the SHAP contribution of each feature. The
score comes from a CatBoost model that is trained once and saved as a versioned artifact.
There is no database yet.

## Status

One row per requirement. Statuses are `planned`, `implemented` or `dropped`.
`tests/test_spec_status.py` checks this table in CI. See "Status tracking" in
[README.md](README.md).

| Req | Status | Date | PR | Evidence |
|---|---|---|---|---|
| S1-R1 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_committed_artifact_matches_the_research; owner's run: CV AUROC 0.7913 reproduces results/d21_scale_free.csv |
| S1-R2 | implemented | 2026-11-03 | #9 | owner's machine: two runs of scripts/train_app_model.py gave the same training_predictions_sha256 (c6d97b85...); script also checks two in-process fits match |
| S1-R3 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_artifact_contents (real artifact: train_app_model.py run pending) |
| S1-R4 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_artifact_with_wrong_features_is_refused |
| S1-R5 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_every_validation_error_is_listed, test_transactions_before_history_start_are_rejected |
| S1-R6 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_short_history_is_refused |
| S1-R7 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_transactions_on_or_after_as_of_change_nothing, test_future_transaction_never_sets_the_opening_balance |
| S1-R8 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_backend_layout_and_one_feature_library (service calls cashflow.py only; no wrapper added) |
| S1-R9 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_percentile_is_share_of_strictly_lower_scores, test_percentile_matches_reference_scores, test_raw_score_is_never_returned |
| S1-R10 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_band_cutoffs_come_from_the_artifact |
| S1-R11 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_shap_adds_up_to_log_odds (CatBoost's own ShapValues; no shap package call) |
| S1-R12 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_missing_income_is_null_not_zero |
| S1-R13 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_far_out_of_range_is_refused, test_range_rule_counts_only_present_features |
| S1-R14 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_notice_is_always_present |
| S1-R15 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_hand_worked_account_is_scored, test_health; uvicorn smoke run in PR #9 |
| S1-R16 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_backend_layout_and_one_feature_library |
| S1-R17 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_model_is_held_in_memory |
| S1-R18 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_logs_hold_no_transaction_data |
| S1-R19 | implemented | 2026-11-03 | #9 | tests/test_scoring_api.py::test_hand_worked_account_is_scored, test_missing_income_is_null_not_zero, test_far_out_of_range_is_refused |
| S1-R20 | implemented | 2026-11-03 | #9 | CI / tests runs tests/test_scoring_api.py on a tiny synthetic artifact built with build_artifact |

## In scope

- A training script that builds the app model and its artifact.
- A model loader that reads the artifact and refuses one that does not match the code.
- A FastAPI service with one scoring endpoint and one health endpoint.
- Tests with hand-worked expected values, and API tests that CI can run.

## Out of scope

- Storage of borrowers, transactions or assessments (slice 3).
- Authentication. The service runs locally only in this slice.
- PDF or statement upload. The API takes canonical transactions; parsing stays local (D19).
- A calibrated probability of default (D21). The original spec's PD output is replaced by the
  risk band.
- Retraining from the app, model comparison, or TabPFN (D16).

## Requirements

### Model artifact

- **S1-R1. Training data.** The model is trained on all 682 Berka loans, with the label as
  defined in D2. Features are `SCALE_FREE_FEATURES` from `features/cashflow.py`, computed on
  the 3-month window before the loan date (D3). The training script reuses
  `build_transaction_features(..., scale_free=True)` and `make_catboost` from
  `experiment.py`, with the same fixed settings (D15) and seed. It reimplements nothing.
- **S1-R2. Script.** The training script is `scripts/train_app_model.py`. It needs `data/raw/`,
  runs in a few minutes, and is deterministic: two runs produce identical predictions on the
  training rows.
- **S1-R3. Artifact contents.** The artifact is one folder per version,
  `models/<model_version>/`, for example `models/catboost-sf-v1/`. It holds:
  - the fitted pipeline (imputer, scaler and CatBoost), saved with `joblib`;
  - `metadata.json`, containing:
    - `model_version`, `created_at`, and the git commit of the training run;
    - the feature list, in order;
    - the training data description: dataset, number of loans and defaults, window length,
      and label definition;
    - metrics copied from `results/d21_scale_free.csv`: CV AUROC and its paired confidence
      interval against the research feature set;
    - each feature's reference range (min and max over the training rows, ignoring NaN; D21);
    - the reference scores used for the percentile (S1-R9);
    - the band cut-offs (S1-R10).
- **S1-R4. Integrity check.** At load time the loader checks that the artifact's feature list
  equals `SCALE_FREE_FEATURES`. On a mismatch it refuses to start, so the model can never score
  features in the wrong order.

### Scoring

- **S1-R5. Input.** The request carries:
  - `as_of`, the date of the assessment;
  - `history_start`, the first date the supplied transactions cover;
  - a list of transactions with the canonical fields from `schema.py`.

  The request is checked with Pydantic, then with `schema.validate()`. Every validation error is
  returned as a 422 response that lists all errors, not just the first.
- **S1-R6. History covers the window.** If `history_start` is later than
  `as_of - 3 months`, the request is refused with a 422 response. Otherwise empty months would
  look like months with no income.
- **S1-R7. No future information.** Only transactions strictly before `as_of` are used
  (`window_slice`). A test shows that a transaction on or after `as_of` does not change any
  output.
- **S1-R8. One feature library.** Features are computed only by functions in
  `features/cashflow.py`: `window_features`, `opening_balance`, `income_denominator` and
  `scale_free_features`. If a single wrapper is needed (for example `scale_free_as_of`), it is
  added to `cashflow.py`, which makes that PR High tier with Berka evidence. The API does not
  compute any feature itself.
- **S1-R9. Risk percentile.** The output is the share of the Berka reference borrowers whose
  model score is lower than the borrower's score, from 0 to 100. The raw model score is
  **not** returned and is not labelled a probability anywhere (D17, D21).
- **S1-R10. Risk band.** The percentile maps to a band: `lower`, `middle` or `higher` relative
  risk. The cut-offs are stored in the artifact, not in code (see open question 2).
- **S1-R11. SHAP.** Every feature gets a contribution in log-odds, from CatBoost's own SHAP
  values (`TreeExplainer` on the fitted model), plus the base value. A test checks that the
  base value plus the contributions equals the model's raw log-odds output.
- **S1-R12. Missing is not zero.** A feature that cannot be computed (for example, income is
  NaN) is returned as `null` and listed under `missing`. The model's imputer still fills it with
  the training median, as in D21, and the response says so for that feature.
- **S1-R13. Out of range.** A feature outside its reference range is flagged with its value
  and the range. If more than half of the *non-missing* features are out of range, the response
  has `status: "refused"`: it still returns the features and flags, but no percentile, band or
  SHAP values. Missing features are never counted as out of range (D21).
- **S1-R14. Permanent notice.** Every scored response carries the notice
  `"Relative risk among 1990s Czech borrowers. Not validated on Philippine outcomes."`
  (the exact wording can change; the notice cannot be removed).

### Service

- **S1-R15. Endpoints** (under `/api/v1`, matching the planned frontend rewrites):
  - `POST /api/v1/assessments/score` takes the input from S1-R5 and returns:
    - `status`: `"scored"` or `"refused"`;
    - `model_version` and `as_of`;
    - `income_denominator`;
    - `features`, mapping each name to a value or `null`;
    - `missing` and `out_of_range`, each a list;
    - `risk_percentile` and `risk_band`;
    - `shap`, holding `base_value` and `contributions`;
    - `notice`.
  - `GET /api/v1/health` returns `model_version` and the feature list.
- **S1-R16. Layout by domain** (D20). Backend code lives in `backend/app/`:
  - `assessments/` holds the router, schemas and scoring service;
  - `models/` holds the artifact loader and model registry;
  - `core/` holds settings and app creation.

  It imports `flowscore` and never copies from it.
- **S1-R17. Model in memory.** The model loads once at startup, and requests do not touch the
  disk. The artifact folder is set by an environment variable, with a default of
  `models/catboost-sf-v1`.
- **S1-R18. No logging of transaction data.** Request bodies and feature values are not
  logged. Only the model version, status and timing are logged.

### Tests

- **S1-R19. Hand-worked values.** A small synthetic account (round numbers, made up, not
  modelled on anyone's statements) has hand-calculated values for `income_denominator`, each of
  the 5 features, and the out-of-range and missing outputs. These values are written into the
  test.
- **S1-R20. API tests run in CI** without Berka data. They use the committed artifact (see open
  question 1), or a tiny artifact built in the test from synthetic rows if the real one is not
  committed.

## Acceptance

1. `python scripts\train_app_model.py` creates `models/catboost-sf-v1/`. A second run produces
   identical predictions.
2. Starting the service and posting the synthetic account from S1-R19 returns `status: "scored"`,
   the hand-worked feature values, a percentile, a band, and SHAP values that add up to the
   log-odds output.
3. Posting an account whose values are all far out of range returns `status: "refused"` with
   the flags.
4. Adding a transaction dated on `as_of` changes nothing in the response.
5. The output from pytest (all tests passing), the privacy check, and the Berka evidence are
   pasted into each PR, as `CLAUDE.md` requires.

## Risk tier

**High.** The slice adds model artifacts and new dependencies, and any wrapper added to
`cashflow.py` is research-frozen.

## Known limitations carried into this slice

- **Unused income signal.** Income is NaN for 28 Berka loans, and 36% of them defaulted. The
  model imputes the median, so this signal is unused (D21). Adding an "income missing" flag as
  a feature would change the D21 numbers, so it needs its own decision entry. It is not part of
  this slice.
- **Opening balance.** For Berka, the opening balance always comes from earlier history, since
  every account has at least 3.4 months of it. For an uploaded statement, `opening_balance`
  rebuilds it by undoing the first transaction. The two agree whenever a running balance is
  present.

## Open questions

1. **Should the artifact be committed to git?**
   *Recommendation:* yes, `models/` is committed. The file is small, it lets CI run the API
   tests, and it is derived from public Berka data in the same way `results/features.csv` is.
   *Adopted by default (D22), pending the owner's confirmation.*
2. **Where should the band cut-offs sit?**
   *Recommendation:* `lower` below the 50th percentile, `middle` from 50 to 80, `higher` above
   80. Under these cut-offs roughly the top fifth is flagged. Record the choice as a decision.
   *Adopted by default (D22), pending the owner's confirmation.*
3. **Which scores define the percentile reference?** The options are in-sample scores from the
   final model, or out-of-fold scores from CV.
   *Recommendation:* out-of-fold mean scores. In-sample scores are overfitted, which pushes
   known defaulters to the extremes and would make new borrowers look safer than they are.
   *Adopted by default (D22), pending the owner's confirmation.*
4. **Which new dependencies should be added?** The slice needs `fastapi`, `uvicorn`, and
   `httpx` for the test client. `pydantic` v2 comes with FastAPI.
   *Recommendation:* add these to `requirements.txt` and the lock in their own flagged PR,
   before any API code (hard rule 10).
   *Done as the first, separate commit of the slice 1 PR:* `fastapi`, `uvicorn`, and FastAPI's
   own dependencies (`starlette`, `opentelemetry-api`, `annotated-doc`). `httpx` is not needed:
   the test client uses `httpx2`, which the lock already had.
