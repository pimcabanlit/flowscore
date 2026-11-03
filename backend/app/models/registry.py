"""The model registry (spec S3-R7): one row per artifact, registered at startup.

The registry records which artifacts have scored assessments; it never stores a path and
nothing is ever loaded from it. Artifacts still load only from the repo's models/ folder (D22).
A version name must always mean one model: if the registered hashes differ from the artifact
being loaded, startup fails.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path

from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.db import Base, JSONType, UTCDateTime, utcnow
from backend.app.models.artifact import MODEL_FILE, LoadedModel


class RegistryMismatch(RuntimeError):
    """The registered artifact with this version is not the one being loaded."""


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    model_version: Mapped[str] = mapped_column(String(100), primary_key=True)
    trained_at: Mapped[str] = mapped_column(String(40))      # metadata.json created_at, as written
    git_commit: Mapped[str] = mapped_column(String(40))
    artifact_metadata: Mapped[dict] = mapped_column(JSONType)          # the whole metadata.json
    model_sha256: Mapped[str] = mapped_column(String(64))
    metadata_sha256: Mapped[str] = mapped_column(String(64))
    registered_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)


def metadata_digest(meta: dict) -> str:
    """SHA-256 of the metadata as canonical JSON (sorted keys), not of the file's bytes: a
    Windows checkout may turn metadata.json's line endings into CRLF without changing a value."""
    return hashlib.sha256(json.dumps(meta, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


async def register(session: AsyncSession, model: LoadedModel, artifact_dir: Path) -> ModelRegistry:
    """Add the loaded artifact to the registry, or check it against its existing row."""
    meta = model.metadata
    model_sha, meta_sha = file_digest(Path(artifact_dir) / MODEL_FILE), metadata_digest(meta)
    row = await session.get(ModelRegistry, model.model_version)
    if row is not None:
        if (row.model_sha256, row.metadata_sha256) != (model_sha, meta_sha):
            raise RegistryMismatch(f"model_version {model.model_version} is registered with different "
                                   "files; give a changed artifact a new version")
        return row
    row = ModelRegistry(model_version=model.model_version, trained_at=str(meta.get("created_at", "")),
                        git_commit=str(meta.get("git_commit", "")), artifact_metadata=meta,
                        model_sha256=model_sha, metadata_sha256=meta_sha)
    session.add(row)
    await session.commit()
    return row
