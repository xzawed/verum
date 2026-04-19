from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Railway provides postgres://, standard is postgresql://, asyncpg needs postgresql+asyncpg://
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif _DATABASE_URL.startswith("postgresql://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

_FINAL_URL = _DATABASE_URL or "postgresql+asyncpg://verum:verum@localhost:5432/verum"

# Remote hosts (Railway, etc.) require SSL; local/Docker hosts do not.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "db", "db-test", ""}
try:
    _db_host = urlparse(_FINAL_URL).hostname or ""
except Exception:
    _db_host = ""
_ENGINE_KWARGS: dict[str, object] = (
    {"connect_args": {"ssl": True}} if _db_host not in _LOCAL_HOSTS else {}
)

engine = create_async_engine(
    _FINAL_URL,
    echo=False,
    pool_pre_ping=True,
    **_ENGINE_KWARGS,  # type: ignore[arg-type]
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
