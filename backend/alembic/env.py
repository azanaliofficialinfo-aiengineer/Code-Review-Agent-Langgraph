"""
Alembic async migration environment.

Reads DATABASE_URL from app settings so migrations always target the same
database as the running application — no separate config required.

Usage (from backend/ directory):
    alembic upgrade head
    alembic revision --autogenerate -m "description"
    alembic downgrade -1
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Make the backend package importable when running alembic from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load settings before importing models so DATABASE_URL is available.
from app.core.config import settings  # noqa: E402
from app.db.session import Base  # noqa: E402

# Register all ORM models with the shared metadata.
import app.models  # noqa: E402, F401 — side-effect import populates Base.metadata

config = context.config

# Override the placeholder URL with the real one from settings.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ── Offline mode (generate SQL without a live DB) ─────────────────────────────

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (run against live database) ───────────────────────────────────

def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
