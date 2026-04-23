from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Validate DATABASE_URL on module load.
# Throws immediately if DATABASE_URL is not set and we appear to be in production.
# This prevents misconfigured deployments from silently using insecure hardcoded credentials.
_KNOWN_INSECURE_DEFAULT = "postgresql+asyncpg://verum:verum@localhost:5432/verum"
_railway = os.environ.get("RAILWAY_ENVIRONMENT")

if not _DATABASE_URL:
    if _railway:
        raise RuntimeError(
            "DATABASE_URL must be set to a real PostgreSQL URL in production. "
            "Found missing or insecure default."
        )
    # In development (no RAILWAY_ENVIRONMENT), allow empty DATABASE_URL to fall back to local default
    _FINAL_URL = _KNOWN_INSECURE_DEFAULT
else:
    # Check if we're on Railway with an insecure default URL
    if _railway and _DATABASE_URL == _KNOWN_INSECURE_DEFAULT:
        raise RuntimeError(
            "DATABASE_URL must be set to a real PostgreSQL URL in production. "
            "Found missing or insecure default."
        )
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
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
