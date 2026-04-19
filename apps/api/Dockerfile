# Multistage build — final image target < 1GB (CLAUDE.md §🏗 §인프라)
# Build context = REPO ROOT. Build with: `docker build -f apps/api/Dockerfile .`
# Railway uses the repo root as context with railway.toml's dockerfilePath setting.

FROM python:3.13-slim AS builder
WORKDIR /build

# git is needed at runtime for ANALYZE stage (git clone of repos)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml + src so hatchling can resolve the package during install
COPY apps/api/pyproject.toml .
COPY apps/api/src/ ./src/
RUN pip install --no-cache-dir .

FROM python:3.13-slim AS final
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY apps/api/src/ ./src/
COPY apps/api/alembic/ ./alembic/
COPY apps/api/alembic.ini ./alembic.ini

EXPOSE 8000
# Migrations are applied via Supabase MCP or Railway Pre-Deploy command.
# Alembic upgrade is NOT run here to avoid startup failures on DB connectivity issues.
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
