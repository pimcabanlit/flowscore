"""Settings from environment variables (pydantic-settings). No secrets are needed in slice 1."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLOWSCORE_")

    # FLOWSCORE_MODEL_DIR (S1-R17). A relative path is taken from the repository root.
    model_dir: Path = Path("models/catboost-sf-v1")

    def resolved_model_dir(self) -> Path:
        return self.model_dir if self.model_dir.is_absolute() else REPO_ROOT / self.model_dir
