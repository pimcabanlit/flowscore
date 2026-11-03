"""Every table, for Alembic and the tests: importing this module registers each domain's
SQLAlchemy models on Base.metadata (spec S3-R1, S3-R15)."""
from backend.app.assessments.models import Assessment
from backend.app.borrowers.models import Borrower
from backend.app.core.db import Base
from backend.app.features.models import FeatureSnapshot
from backend.app.models.registry import ModelRegistry
from backend.app.transactions.models import Transaction, TransactionBatch

metadata = Base.metadata

__all__ = ["metadata", "Assessment", "Borrower", "FeatureSnapshot", "ModelRegistry", "Transaction",
           "TransactionBatch"]
