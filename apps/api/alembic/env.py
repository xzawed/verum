from __future__ import annotations

import asyncio
import logging
import os
import ssl
from logging.config import fileConfig
from urllib.parse import urlparse

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# import all models so Alembic can see their metadata
from src.db.base import Base
import src.db.models.repos  # noqa: F401
import src.db.models.analyses  # noqa: F401
import src.db.models.inferences  # noqa: F401
import src.db.models.harvest_sources  # noqa: F401
import src.db.models.chunks  # noqa: F401
import src.db.models.users  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

logger = logging.getLogger("alembic.env")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    config.get_main_option("sqlalchemy.url", "postgresql+asyncpg://verum:verum@localhost:5432/verum"),
)
# Railway provides postgres://, standard is postgresql://, asyncpg needs postgresql+asyncpg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Remote hosts (Railway, etc.) require SSL; local/Docker hosts do not.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "db", "db-test", ""}
try:
    _db_host = urlparse(DATABASE_URL).hostname or ""
except Exception:
    _db_host = ""
# Supabase Connection Pooler uses a self-signed certificate chain; ssl="require"
# and ssl=True both trigger chain verification which fails. Use a custom SSLContext.
_ssl_context: ssl.SSLContext | None = None
if _db_host not in _LOCAL_HOSTS:
    _ssl_context = ssl.create_default_context()
    _ssl_context.check_hostname = False
    _ssl_context.verify_mode = ssl.CERT_NONE

_ENGINE_KWARGS: dict[str, object] = (
    {"connect_args": {"ssl": _ssl_context}} if _ssl_context is not None else {}
)
logger.info("alembic: host=%s ssl=%s", _db_host, "custom-ctx" if _ssl_context else "off")


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)  # type: ignore[arg-type]
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False, **_ENGINE_KWARGS)  # type: ignore[arg-type]
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
