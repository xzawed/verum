from __future__ import annotations

import contextlib
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Validate DATABASE_URL on module load.
# Throws immediately if DATABASE_URL is not set and we appear to be in production.
# This prevents misconfigured deployments from silently using insecure hardcoded credentials.
_KNOWN_INSECURE_DEFAULT = "postgresql+asyncpg://verum:verum@localhost:5432/verum"
_railway = os.environ.get("RAILWAY_ENVIRONMENT")

# Consolidate production guard: fail if on Railway with missing or insecure default DATABASE_URL
if _railway and (not _DATABASE_URL or _DATABASE_URL == _KNOWN_INSECURE_DEFAULT):
    raise RuntimeError(
        "DATABASE_URL must be set to a real PostgreSQL URL in production. "
        "Found missing or insecure default."
    )

# Fall back to insecure default in development (no RAILWAY_ENVIRONMENT)
if not _DATABASE_URL:
    _FINAL_URL = _KNOWN_INSECURE_DEFAULT
else:
    # Railway provides postgres://, standard is postgresql://, asyncpg needs postgresql+asyncpg://
    if _DATABASE_URL.startswith("postgres://"):
        _FINAL_URL = _DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif _DATABASE_URL.startswith("postgresql://"):
        _FINAL_URL = _DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        _FINAL_URL = _DATABASE_URL

engine = create_async_engine(
    _FINAL_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "40")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def get_db_for_user(user_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Session with app.current_user_id set for Row-Level Security enforcement.

    Uses set_config() (session-scoped) rather than SET LOCAL so the GUC
    persists across multiple commits within the same connection.  The finally
    block resets it before the connection is returned to the pool.

    When RLS is FORCED (migration 0022) and the application connects as
    verum_app (not the table-owner), this context manager is what activates
    per-user row filtering.  Until then it is a no-op for the owner role.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_user_id', :uid, false)"),
            {"uid": str(user_id)},
        )
        try:
            yield session
        finally:
            with contextlib.suppress(Exception):
                await session.execute(text("RESET app.current_user_id"))
