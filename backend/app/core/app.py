"""App creation. The model loads once at startup and stays in memory (S1-R17); if the artifact is
missing or does not match the code, startup fails (S1-R4).

With FLOWSCORE_DATABASE_URL set, startup also opens the database and registers the artifact in
`model_registry` (S3-R7); without it, the database endpoints answer 503 and the slice 1
endpoints still work (S3-R9)."""
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from sqlalchemy.exc import SQLAlchemyError

from backend.app.assessments.router import borrower_router as borrower_assessments_router
from backend.app.assessments.router import router as assessments_router
from backend.app.assessments.schemas import Health
from backend.app.borrowers.router import router as borrowers_router
from backend.app.core import tables  # noqa: F401  (registers every table)
from backend.app.core.db import make_engine, make_sessionmaker
from backend.app.core.settings import MODELS_ROOT, Settings
from backend.app.features.router import router as features_router
from backend.app.models.artifact import load_artifact
from backend.app.models.registry import register
from backend.app.transactions.router import router as transactions_router

log = logging.getLogger("flowscore.api")


def create_app(settings: Settings = None, models_root=MODELS_ROOT) -> FastAPI:
    """The artifact is chosen once, here, from settings (FLOWSCORE_MODEL_DIR) and must lie inside
    `models_root`. No request can name a model or a path (D22). `models_root` is a code argument,
    not a setting, so only tests can point it elsewhere."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        artifact_dir = settings.resolved_model_dir(models_root)
        app.state.model = load_artifact(artifact_dir)
        log.info("loaded model=%s", app.state.model.model_version)
        app.state.sessionmaker = None
        engine = None
        if settings.database_url is not None:
            engine = make_engine(settings.database_url.get_secret_value())
            app.state.sessionmaker = make_sessionmaker(engine)
            try:
                async with app.state.sessionmaker() as session:
                    await register(session, app.state.model, artifact_dir)
            except SQLAlchemyError as e:
                await engine.dispose()
                # The error's class only: driver messages can name the host (S3-R4).
                raise RuntimeError(f"database unreachable or not migrated ({type(e).__name__}); "
                                   "check FLOWSCORE_DATABASE_URL and run `alembic upgrade head`") from None
            log.info("database ready, model=%s registered", app.state.model.model_version)
        try:
            yield
        finally:
            if engine is not None:
                await engine.dispose()

    app = FastAPI(title="FlowScore scoring API", version="0.2.0", lifespan=lifespan)
    api = APIRouter(prefix="/api/v1")

    @api.get("/health", response_model=Health)
    def health(request: Request) -> dict:
        m = request.app.state.model
        return {"model_version": m.model_version, "features": m.features,
                "band_cutoffs": m.metadata["band_cutoffs"]}

    api.include_router(assessments_router)
    api.include_router(borrowers_router)
    api.include_router(borrower_assessments_router)
    api.include_router(transactions_router)
    api.include_router(features_router)
    app.include_router(api)
    return app
