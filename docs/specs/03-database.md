# Slice 3: Database

## Goal

Borrowers, their transactions, the features computed from them, and every assessment are stored
in Postgres. The API reads from and writes to the database instead of taking every transaction
in each request.

## In scope

Neon Postgres, SQLAlchemy 2 (async, with asyncpg), and Alembic migrations, using a repository
per domain (D20). There are tables for borrowers, transactions, feature snapshots, assessments,
and the model registry, plus a script that loads the slice 2 synthetic borrowers.

## Out of scope

Authentication and multiple users (deferred to a later slice; see open question 1), and any
real borrower data.

## Requirements (draft)

- **S3-R1. Tables.**
  - `borrowers`: id, display name, the `synthetic` flag, and a created timestamp.
  - `transactions`: the canonical schema plus `borrower_id`.
  - `feature_snapshots`: the borrower, `as_of`, the feature values (NULL stays NULL), the
    income denominator, and the code version.
  - `assessments`: the snapshot, the model version, status, percentile, band, SHAP values,
    flags, and the notice.
  - `model_registry`: one row per artifact, holding the metadata from S1-R3.
- **S3-R2. Assessments cannot be edited.** An assessment is never updated in place. A new
  score is a new row, so the history shows which model said what, and when.
- **S3-R3. Reproducibility.** Each assessment links to the exact feature snapshot and model
  version it used. Rescoring a stored snapshot with the same model version gives the same
  output.
- **S3-R4. Secrets.** The database URL is read from an environment variable only (hard rule 8).
- **S3-R5. Migrations.** Every schema change is an Alembic migration with a working downgrade.
  Migrations are High tier.
- **S3-R6. Missing is not zero.** Unknown values are stored as NULL, never 0.

## Acceptance (draft)

A fresh database followed by `alembic upgrade head`, then the synthetic seed, then the
endpoint `POST /api/v1/borrowers/{id}/assessments` stores an assessment. Fetching it returns
the same output the slice 1 endpoint gives for the same transactions.

## Risk tier

**High** (migrations and secrets).

## Open questions

1. **Does the demo need sign-in?**
   *Recommendation:* not in this slice. The demo is single-user with synthetic data only.
   Decide before anything is deployed publicly.
2. **Should transactions be stored per row or as one uploaded batch per statement?**
   *Recommendation:* per row, with a `batch_id`. Then the cash-flow view (slice 4) can query
   by date.
