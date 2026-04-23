from __future__ import annotations

import os
import ssl
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Validate DATABASE_URL on module load.
# Throws immediately if DATABASE_URL is not set and we appear to be in production.
# This prevents misconfigured deployments from silently using insecure hardcoded credentials.
_KNOWN_INSECURE_DEFAULT = "postgresql+asyncpg://verum:verum@localhost:5432/verum"
_is_production_like = os.environ.get("RAILWAY_ENVIRONMENT") is not None or os.environ.get("NODE_ENV") == "production"

if not _DATABASE_URL:
    if _is_production_like:
        raise RuntimeError(
            "DATABASE_URL environment variable is required in production. "
            "Set it to a valid PostgreSQL connection string before starting the application."
        )
    # In development (no RAILWAY_ENVIRONMENT), allow empty DATABASE_URL to fall back to local default
    _FINAL_URL = _KNOWN_INSECURE_DEFAULT
else:
    # Railway provides postgres://, standard is postgresql://, asyncpg needs postgresql+asyncpg://
    if _DATABASE_URL.startswith("postgres://"):
        _FINAL_URL = _DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif _DATABASE_URL.startswith("postgresql://"):
        _FINAL_URL = _DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        _FINAL_URL = _DATABASE_URL

# Remote hosts (Railway, etc.) require SSL; local/Docker hosts do not.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "db", "db-test", ""}
try:
    _db_host = urlparse(_FINAL_URL).hostname or ""
except Exception:
    _db_host = ""
# Supabase Connection Pooler uses a self-signed certificate chain; full verification
# fails with asyncpg's ssl=True. We still require SSL (encrypt the connection) but
# skip chain verification — acceptable for a managed cloud pooler endpoint.
_ssl_context: ssl.SSLContext | None = None
if _db_host not in _LOCAL_HOSTS:
    _ssl_context = ssl.create_default_context()
    _ssl_context.check_hostname = False
    _ssl_context.verify_mode = ssl.CERT_NONE

_ENGINE_KWARGS: dict[str, object] = (
    {"connect_args": {"ssl": _ssl_context}} if _ssl_context is not None else {}
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
