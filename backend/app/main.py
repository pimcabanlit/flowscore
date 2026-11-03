"""Entry point: `uvicorn backend.app.main:app` from the repository root, with PYTHONPATH=src."""
from backend.app.core.app import create_app

app = create_app()
