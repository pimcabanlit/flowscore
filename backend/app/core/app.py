"""App creation. The model loads once at startup and stays in memory (S1-R17); if the artifact is
missing or does not match the code, startup fails (S1-R4)."""
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request

from backend.app.assessments.router import router as assessments_router
from backend.app.assessments.schemas import Health
from backend.app.core.settings import Settings
from backend.app.models.artifact import load_artifact

log = logging.getLogger("flowscore.api")


def create_app(settings: Settings = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.model = load_artifact(settings.resolved_model_dir())
        log.info("loaded model=%s", app.state.model.model_version)
        yield

    app = FastAPI(title="FlowScore scoring API", version="0.1.0", lifespan=lifespan)
    api = APIRouter(prefix="/api/v1")

    @api.get("/health", response_model=Health)
    def health(request: Request) -> dict:
        m = request.app.state.model
        return {"model_version": m.model_version, "features": m.features}

    api.include_router(assessments_router)
    app.include_router(api)
    return app
