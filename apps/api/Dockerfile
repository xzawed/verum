# Multistage build — final image target < 1GB (CLAUDE.md §🏗 §인프라)
# Phase 0: installs Phase 0 deps only; uncomment Phase 1+ deps in pyproject.toml as stages ship.

FROM python:3.13-slim AS builder
WORKDIR /build
COPY pyproject.toml .
# Install deps from pyproject.toml without building the package itself
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "pydantic>=2.7" \
    "sqlalchemy[asyncio]>=2.0" \
    "alembic>=1.13" \
    "asyncpg>=0.29" \
    "pgvector>=0.3"

FROM python:3.13-slim AS final
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/
EXPOSE 8000
# $PORT is set by Railway; fallback to 8000 for local dev
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
