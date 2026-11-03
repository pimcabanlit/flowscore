"""Settings from environment variables (pydantic-settings).

The database URL is a secret (hard rule 8): it comes only from FLOWSCORE_DATABASE_URL, is held as
a SecretStr so it never appears in a repr or a log line, and has no default (S3-R4).
"""
from pathlib import Path
from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS_ROOT = REPO_ROOT / "models"    # the only place artifacts are loaded from (D22)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLOWSCORE_")

    # FLOWSCORE_MODEL_DIR (S1-R17). A relative path is taken from the repository root.
    model_dir: Path = Path("models/catboost-sf-v1")

    # FLOWSCORE_DATABASE_URL (S3-R4), e.g. postgresql+asyncpg://... or sqlite+aiosqlite:///file.db.
    # Unset: the database endpoints answer 503 and the slice 1 endpoints still work.
    database_url: Optional[SecretStr] = None

    def resolved_model_dir(self, models_root: Path = MODELS_ROOT) -> Path:
        """The artifact folder, which must lie inside `models_root` (the repo's models/ folder).
        Loading a joblib file can execute code, so a path outside it is refused (D22)."""
        path = (self.model_dir if self.model_dir.is_absolute() else REPO_ROOT / self.model_dir).resolve()
        root = Path(models_root).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"FLOWSCORE_MODEL_DIR {path} is outside {root}; refusing to load it")
        return path
