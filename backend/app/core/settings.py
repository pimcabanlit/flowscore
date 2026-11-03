"""Settings from environment variables (pydantic-settings). No secrets are needed in slice 1."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS_ROOT = REPO_ROOT / "models"    # the only place artifacts are loaded from (D22)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLOWSCORE_")

    # FLOWSCORE_MODEL_DIR (S1-R17). A relative path is taken from the repository root.
    model_dir: Path = Path("models/catboost-sf-v1")

    def resolved_model_dir(self, models_root: Path = MODELS_ROOT) -> Path:
        """The artifact folder, which must lie inside `models_root` (the repo's models/ folder).
        Loading a joblib file can execute code, so a path outside it is refused (D22)."""
        path = (self.model_dir if self.model_dir.is_absolute() else REPO_ROOT / self.model_dir).resolve()
        root = Path(models_root).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"FLOWSCORE_MODEL_DIR {path} is outside {root}; refusing to load it")
        return path
