"""Database engine, sessions and the declarative base (spec S3-R15).

The engine is built from FLOWSCORE_DATABASE_URL (S3-R4). Postgres (Neon) through asyncpg is the
deployment target; SQLite through aiosqlite runs the tests and the offline demo (D24). The schema
uses only types both support: JSON becomes JSONB on Postgres, and money is NUMERIC(14, 2).
"""
import datetime as dt
from collections.abc import AsyncIterator

from fastapi import HTTPException, Request
from sqlalchemy import JSON, DateTime, MetaData, TypeDecorator, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Constraint names fixed by convention, so migrations name them the same on every engine.
NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

JSONType = JSON().with_variant(JSONB(), "postgresql")


class UTCDateTime(TypeDecorator):
    """A timestamp with time zone that always comes back in UTC. Postgres keeps the zone; SQLite
    stores none, so a naive value read from it is marked UTC (every value written is UTC)."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def make_engine(url: str, **kwargs) -> AsyncEngine:
    """An async engine. On SQLite, foreign keys are switched on for every connection (SQLite
    leaves them off by default), so both engines enforce the same rules."""
    engine = create_async_engine(url, **kwargs)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine.sync_engine, "connect")
        def _fk_on(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request. 503 when no database is configured, so the
    slice 1 endpoints keep working without one (S3-R9)."""
    maker = getattr(request.app.state, "sessionmaker", None)
    if maker is None:
        raise HTTPException(status_code=503, detail="no database configured (FLOWSCORE_DATABASE_URL)")
    async with maker() as session:
        yield session
