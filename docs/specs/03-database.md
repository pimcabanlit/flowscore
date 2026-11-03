# Slice 3: Database

## Goal

Borrowers, their transactions, the features computed from them, and every assessment are stored
in a database. The API reads from and writes to it: `POST /api/v1/borrowers/{id}/assessments`
scores a stored borrower as of a date and keeps the result, so nobody has to send every
transaction in each request. The slice 1 endpoint keeps working unchanged.

## Status

One row per requirement. Statuses are `planned`, `implemented` or `dropped`.
`tests/test_spec_status.py` checks this table in CI. See "Status tracking" in
[README.md](README.md).

| Req | Status | Date | PR | Evidence |
|---|---|---|---|---|
| S3-R1 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_migration_matches_the_models, test_only_synthetic_borrowers_are_accepted |
| S3-R2 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_assessments_and_snapshots_cannot_be_edited (database triggers on SQLite and Postgres) |
| S3-R3 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_rescoring_a_snapshot_gives_the_same_output, test_changed_transactions_give_a_new_snapshot, test_fingerprint_is_hand_worked |
| S3-R4 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_database_url_comes_only_from_the_environment, test_unreachable_database_error_hides_the_url |
| S3-R5 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_upgrade_downgrade_upgrade; alembic upgrade/downgrade/upgrade on Postgres 16 in PR #14 |
| S3-R6 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_missing_values_are_null_not_zero, test_amounts_keep_two_places_and_missing_stays_none |
| S3-R7 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_model_is_registered_once, test_changed_artifact_under_the_same_version_is_refused |
| S3-R8 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_window_coverage_is_hand_worked, test_window_must_be_covered |
| S3-R9 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_endpoints, test_without_a_database_slice_1_still_works |
| S3-R10 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_same_output_as_slice_1_for_every_demo_borrower (all 30), test_stored_features_are_the_hand_worked_values |
| S3-R11 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_layout_by_domain, test_stored_features_are_the_hand_worked_values; tests/test_scoring_api.py::test_backend_layout_and_one_feature_library |
| S3-R12 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_seed_runs_twice_without_changes, test_seed_reports_a_borrower_that_differs, test_seed_refuses_bad_files |
| S3-R13 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_demo_code_stays_out |
| S3-R14 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_logs_hold_no_transaction_data, test_database_errors_hide_their_parameters |
| S3-R15 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_layout_by_domain |
| S3-R16 | implemented | 2026-11-03 | #14 | tests/test_database.py::test_engine_under_test; CI runs SQLite, Postgres 16 run pasted in PR #14 |

## In scope

- SQLAlchemy 2 (async) models and one repository per domain (D20): borrowers, transactions,
  features, assessments, models.
- One Alembic migration that creates the six tables below, with a working downgrade.
- Endpoints to list borrowers, read a borrower's transactions, create an assessment, and read
  stored assessments.
- A script that loads the slice 2 synthetic borrowers (`demo/synthetic/`) into the database.
- Tests that CI runs without a database server (SQLite), and that run unchanged against
  Postgres when a test database URL is set (D24).

## Out of scope

- Authentication and multiple users. The demo is single-user, with synthetic data only, and
  runs locally (open question 1).
- Any real borrower data. There is no endpoint that creates a borrower or uploads transactions;
  data gets in only through the synthetic seed script (S3-R12), and the database itself refuses
  a borrower that is not marked synthetic (S3-R1).
- Deployment (Neon project, connection pooling, backups). The code runs against Neon, but
  setting one up is the job of the slice that deploys.
- Monthly cash-flow aggregates for the slice 4 view. Slice 4 adds the endpoint it needs, so the
  frontend still computes nothing.

## Requirements

### Storage

- **S3-R1. Tables.** One Alembic migration creates:
  - `borrowers`: `id` (for example `SYN-001`), `display_name`, `synthetic`, `created_at`. A
    check constraint accepts only `synthetic = true` in this slice. The slice that admits real
    borrowers removes it with its own migration and decision entry.
  - `transaction_batches`: one row per loaded statement or synthetic history: `borrower_id`,
    `source`, the period it covers (`period_start` inclusive, `period_end` exclusive), and
    `loaded_at` (open question 2, answered: per row, with a batch).
  - `transactions`: the canonical schema (`transaction_id`, `transaction_date`, `debit_amount`,
    `credit_amount`, `running_balance`, `transaction_category`) plus `borrower_id` and
    `batch_id`. Amounts are `NUMERIC(14, 2)`. `transaction_id` is unique per borrower, and there
    is an index on (`borrower_id`, `transaction_date`) for the slice 4 cash-flow view.
  - `feature_snapshots`: `borrower_id`, `as_of`, `window_months`, `income_denominator`, the
    feature values as a JSON object, `features_version`, `transactions_sha256`,
    `transaction_count`, `created_at` (S3-R3).
  - `assessments`: `snapshot_id`, `model_version`, `created_at`, `status`, `risk_percentile`,
    `risk_band`, `shap`, `missing`, `out_of_range`, `notice`. A check constraint ties the
    status to the outputs: `scored` has a percentile and a band, `refused` has neither.
  - `model_registry`: one row per artifact: `model_version`, `trained_at`, `git_commit`, the
    full `metadata.json` from S1-R3, the SHA-256 of `model.joblib` and of the metadata, and
    `registered_at`.

  A test compares the migrated database with the SQLAlchemy models, so the two cannot drift.
- **S3-R2. Assessments cannot be edited.** An assessment is never updated or deleted. A new
  score is a new row, so the history shows which model said what, and when. The repository has
  no update or delete method, and a database trigger refuses `UPDATE` and `DELETE` on
  `assessments` and on `feature_snapshots` (an assessment is only as fixed as the snapshot it
  points to).
- **S3-R3. Reproducibility.** Each assessment points to the exact feature snapshot and model
  version it used. A snapshot records:
  - `features_version`: the SHA-256 of `src/flowscore/features/cashflow.py`, so a change to the
    feature code shows up in every later snapshot without anyone remembering to bump a number;
  - `transactions_sha256` and `transaction_count`: a fingerprint of the stored transactions
    strictly before `as_of` that went into it.

  Scoring always reads the feature values back from the stored snapshot. Assessing the same
  borrower and date again reuses the snapshot when the fingerprint and features version are the
  same, and stores a new assessment with the same output.
- **S3-R4. Secrets.** The database URL is read only from the `FLOWSCORE_DATABASE_URL`
  environment variable (hard rule 8), by the app and by Alembic. `alembic.ini` holds no URL,
  the setting is a `SecretStr` so it never prints, and no log line or error response contains
  it.
- **S3-R5. Migrations.** Every schema change is an Alembic migration with a working downgrade.
  A test runs upgrade, downgrade and upgrade again on an empty database and on one with data.
  Migrations are High tier.
- **S3-R6. Missing is not zero.** Unknown values are stored as NULL, never 0: an absent debit or
  credit, an income denominator that cannot be computed, and a feature that cannot be computed
  (JSON `null`). Reading them back gives `None` or NaN, never 0.
- **S3-R7. Model registry.** At startup the app loads the artifact as in slice 1 (only from the
  repo's `models/` folder, D22) and registers it: if its `model_version` is not in
  `model_registry`, a row is added; if it is there with different hashes, startup fails,
  because one version name must always mean one model. The registry never stores a path, and
  nothing is ever loaded from it.
- **S3-R8. Stored history covers the window.** An assessment needs transaction batches that
  together cover the whole window, from `as_of` minus 3 months up to `as_of`. Otherwise the
  request is refused with a 422 response, because months without stored transactions would look
  like months without income (the S1-R6 rule, now also checked at the end of the window). Only
  transactions strictly before `as_of` are used (S1-R7).

### Service

- **S3-R9. Endpoints** (under `/api/v1`):
  - `GET /borrowers`: every borrower with its covered period and its latest assessment summary
    (id, as-of date, status, band, percentile, model version), or `null`.
  - `GET /borrowers/{id}`: one borrower, in the same shape.
  - `GET /borrowers/{id}/transactions?start=&end=`: the stored canonical rows, `start`
    inclusive and `end` exclusive, in statement order.
  - `POST /borrowers/{id}/assessments` with `{"as_of": "YYYY-MM-DD"}`: computes or reuses the
    snapshot, scores it with the loaded model, stores the assessment, and returns it with
    status 201.
  - `GET /borrowers/{id}/assessments`: that borrower's assessments, newest first.
  - `GET /assessments/{id}`: one stored assessment.

  A stored assessment has every field of the slice 1 response (S1-R15) plus `id`,
  `borrower_id`, `snapshot_id`, `features_version` and `created_at`. An unknown borrower or
  assessment returns 404. When `FLOWSCORE_DATABASE_URL` is not set, these endpoints return 503
  and the slice 1 endpoints still work.
- **S3-R10. Same output as slice 1.** For the same transactions and `as_of`, a stored assessment
  has the same status, model version, features, income denominator, missing and out-of-range
  lists, percentile, band, SHAP values and notice as `POST /api/v1/assessments/score`. A test
  checks this for all 30 synthetic borrowers with the committed model.
- **S3-R11. One feature library.** Snapshots are computed by the slice 1 service
  (`compute_features`), which calls `features/cashflow.py`. Nothing in the database code
  computes a feature.
- **S3-R12. Seed script.** `scripts/seed_demo_database.py` loads `demo/synthetic/` into the
  database, one batch per borrower covering `history_start` to `as_of`. Every row passes
  `schema.validate()` first and every borrower must be `synthetic = true`. A second run changes
  nothing; a borrower whose stored transactions differ from the files is reported, never
  overwritten.
- **S3-R13. Demo code stays out.** The backend never imports `flowscore_demo`, and
  `src/flowscore/` never imports the backend. Only the scripts read the demo files.
- **S3-R14. No logging of transaction data.** As S1-R18: the new endpoints log only ids, the
  model version, the status and timing, never amounts, categories or feature values.
- **S3-R15. Layout by domain** (D20). New code lives in `backend/app/borrowers/`,
  `transactions/`, `features/`, `assessments/` and `models/`, each with its own SQLAlchemy
  models and repository. `core/db.py` holds the engine and session. Migrations live in
  `alembic/` at the repository root.

### Tests

- **S3-R16. Engines.** The database tests run in CI on SQLite (a temporary file, through
  `aiosqlite`), with no server. Setting `FLOWSCORE_TEST_DATABASE_URL` to an empty Postgres
  database runs the same tests against Postgres; that output is pasted into the PR.

## Acceptance

On a fresh database:

```powershell
$env:PYTHONPATH="src"
$env:FLOWSCORE_DATABASE_URL="sqlite+aiosqlite:///flowscore-demo.db"   # or a Neon URL, see README
alembic upgrade head
python scripts\seed_demo_database.py
uvicorn backend.app.main:app
# then: POST /api/v1/borrowers/SYN-001/assessments with {"as_of": "2026-10-01"}
```

The response is stored, `GET /api/v1/assessments/{id}` returns it, and it matches the slice 1
endpoint for the same transactions (S3-R10). `alembic downgrade base` then removes every table.

## Risk tier

**High** (migrations, new dependencies, and a setting that holds a secret).

## Open questions

1. **Does the demo need sign-in?**
   *Recommendation:* not in this slice. The demo is single-user with synthetic data only, and
   the database refuses non-synthetic borrowers (S3-R1). Decide before anything is deployed
   publicly or before real data is admitted, whichever comes first.
   *Proceeding on the recommendation; the owner confirms by merging (D24).*
