"""Alembic environment (spec S3-R4, S3-R5).

The URL comes only from FLOWSCORE_DATABASE_URL, through the app's own Settings, never from
alembic.ini. Migrations run on the async engine (asyncpg for Postgres, aiosqlite for SQLite).
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection

from backend.app.core.db import make_engine
from backend.app.core.settings import Settings
from backend.app.core.tables import metadata

config = context.config
if config.config_file_name is not None:
    # Keep the app's loggers alive when migrations run inside the same process (tests).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = metadata


def database_url() -> str:
    url = Settings().database_url
    if url is None:
        raise SystemExit("FLOWSCORE_DATABASE_URL is not set: Alembic reads the database URL only "
                         "from that environment variable")
    return url.get_secret_value()


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it."""
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata,
                      render_as_batch=connection.dialect.name == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = make_engine(database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
