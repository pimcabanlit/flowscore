"""Initial tables

Borrowers, transaction batches, transactions, feature snapshots, assessments and the model
registry (spec S3-R1), with append-only triggers on assessments and feature snapshots (S3-R2).

Revision ID: 0001
Revises:
Create Date: 2026-11-03

Written out in full rather than imported from the app's models, so this migration stays what it
was when it ran. tests/test_database.py checks that the migrated schema matches the models.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
MONEY = sa.Numeric(precision=14, scale=2)
APPEND_ONLY = ("assessments", "feature_snapshots")


def _append_only_up() -> None:
    """The database itself refuses UPDATE and DELETE on these tables (S3-R2)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE FUNCTION flowscore_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION '% is append-only: rows cannot be updated or deleted', TG_TABLE_NAME;
            END $$""")
        for t in APPEND_ONLY:
            op.execute(f"CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} "
                       "FOR EACH ROW EXECUTE FUNCTION flowscore_append_only()")
            op.execute(f"CREATE TRIGGER {t}_no_truncate BEFORE TRUNCATE ON {t} "
                       "FOR EACH STATEMENT EXECUTE FUNCTION flowscore_append_only()")
    else:                                                   # SQLite (tests, offline demo)
        for t in APPEND_ONLY:
            for action in ("UPDATE", "DELETE"):
                op.execute(f"CREATE TRIGGER {t}_no_{action.lower()} BEFORE {action} ON {t} BEGIN "
                           f"SELECT RAISE(ABORT, '{t} is append-only: rows cannot be updated or deleted'); END")


def _append_only_down() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for t in APPEND_ONLY:
            op.execute(f"DROP TRIGGER {t}_append_only ON {t}")
            op.execute(f"DROP TRIGGER {t}_no_truncate ON {t}")
        op.execute("DROP FUNCTION flowscore_append_only()")
    else:
        for t in APPEND_ONLY:
            for action in ("update", "delete"):
                op.execute(f"DROP TRIGGER {t}_no_{action}")


def upgrade() -> None:
    op.create_table(
        "borrowers",
        sa.Column("id", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # Synthetic borrowers only until a later slice admits real data (spec 03, out of scope).
        sa.CheckConstraint("synthetic", name=op.f("ck_borrowers_synthetic_only")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_borrowers")),
    )
    op.create_table(
        "model_registry",
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("trained_at", sa.String(length=40), nullable=False),
        sa.Column("git_commit", sa.String(length=40), nullable=False),
        sa.Column("artifact_metadata", JSON, nullable=False),
        sa.Column("model_sha256", sa.String(length=64), nullable=False),
        sa.Column("metadata_sha256", sa.String(length=64), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("model_version", name=op.f("pk_model_registry")),
    )
    op.create_table(
        "transaction_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("borrower_id", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("period_start < period_end", name=op.f("ck_transaction_batches_period_not_empty")),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"],
                                name=op.f("fk_transaction_batches_borrower_id_borrowers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction_batches")),
    )
    op.create_index(op.f("ix_transaction_batches_borrower_id"), "transaction_batches", ["borrower_id"])
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("borrower_id", sa.String(length=20), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.String(length=100), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("debit_amount", MONEY, nullable=True),
        sa.Column("credit_amount", MONEY, nullable=True),
        sa.Column("running_balance", MONEY, nullable=False),
        sa.Column("transaction_category", sa.String(length=50), nullable=False),
        sa.CheckConstraint("debit_amount IS NULL OR debit_amount >= 0",
                           name=op.f("ck_transactions_debit_not_negative")),
        sa.CheckConstraint("credit_amount IS NULL OR credit_amount >= 0",
                           name=op.f("ck_transactions_credit_not_negative")),
        sa.ForeignKeyConstraint(["batch_id"], ["transaction_batches.id"],
                                name=op.f("fk_transactions_batch_id_transaction_batches")),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], name=op.f("fk_transactions_borrower_id_borrowers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint("borrower_id", "transaction_id", name=op.f("uq_transactions_borrower_id_transaction_id")),
    )
    op.create_index(op.f("ix_transactions_batch_id"), "transactions", ["batch_id"])
    op.create_index("ix_transactions_borrower_id_transaction_date", "transactions",
                    ["borrower_id", "transaction_date"])
    op.create_table(
        "feature_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("borrower_id", sa.String(length=20), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("window_months", sa.Integer(), nullable=False),
        sa.Column("income_denominator", sa.Double(), nullable=True),
        sa.Column("features", JSON, nullable=False),
        sa.Column("features_version", sa.String(length=64), nullable=False),
        sa.Column("transactions_sha256", sa.String(length=64), nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"],
                                name=op.f("fk_feature_snapshots_borrower_id_borrowers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feature_snapshots")),
        sa.UniqueConstraint("borrower_id", "as_of", "features_version", "transactions_sha256",
                            name=op.f("uq_feature_snapshots_borrower_id_as_of_features_version_transactions_sha256")),
    )
    op.create_index(op.f("ix_feature_snapshots_borrower_id"), "feature_snapshots", ["borrower_id"])
    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("risk_percentile", sa.Double(), nullable=True),
        sa.Column("risk_band", sa.String(length=10), nullable=True),
        sa.Column("shap", JSON, nullable=True),
        sa.Column("missing", JSON, nullable=False),
        sa.Column("out_of_range", JSON, nullable=False),
        sa.Column("notice", sa.Text(), nullable=False),
        sa.CheckConstraint("(status = 'scored' AND risk_percentile IS NOT NULL AND risk_band IS NOT NULL) OR "
                           "(status = 'refused' AND risk_percentile IS NULL AND risk_band IS NULL)",
                           name=op.f("ck_assessments_status_matches_outputs")),
        sa.CheckConstraint("risk_band IS NULL OR risk_band IN ('lower', 'middle', 'higher')",
                           name=op.f("ck_assessments_band_is_relative")),
        sa.ForeignKeyConstraint(["model_version"], ["model_registry.model_version"],
                                name=op.f("fk_assessments_model_version_model_registry")),
        sa.ForeignKeyConstraint(["snapshot_id"], ["feature_snapshots.id"],
                                name=op.f("fk_assessments_snapshot_id_feature_snapshots")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessments")),
    )
    op.create_index(op.f("ix_assessments_snapshot_id"), "assessments", ["snapshot_id"])
    _append_only_up()


def downgrade() -> None:
    """Removes every table, and with them every stored assessment."""
    _append_only_down()
    op.drop_index(op.f("ix_assessments_snapshot_id"), table_name="assessments")
    op.drop_table("assessments")
    op.drop_index(op.f("ix_feature_snapshots_borrower_id"), table_name="feature_snapshots")
    op.drop_table("feature_snapshots")
    op.drop_index("ix_transactions_borrower_id_transaction_date", table_name="transactions")
    op.drop_index(op.f("ix_transactions_batch_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_transaction_batches_borrower_id"), table_name="transaction_batches")
    op.drop_table("transaction_batches")
    op.drop_table("model_registry")
    op.drop_table("borrowers")
