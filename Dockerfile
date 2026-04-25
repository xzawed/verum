# Single-image build: Next.js (Node PID 1) + Python worker (child process)
# Node spawns Python at startup; both share the Postgres DATABASE_URL.

# ── Stage 1: Next.js build ────────────────────────────────────────────────────
FROM node:20-slim AS web-build
WORKDIR /app

COPY apps/dashboard/package.json ./
# Install including devDeps (needed for build)
RUN npm install --legacy-peer-deps

COPY apps/dashboard .
RUN npm run build

# ── Stage 2: Python dependency wheel install ──────────────────────────────────
FROM python:3.13-slim AS py-build
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml ./
# Install all deps into /py-deps so we can copy the dir to the runtime layer
RUN pip install --no-cache-dir --target /py-deps "hatchling" \
    && pip install --no-cache-dir --target /py-deps .

# ── Stage 3: Runtime (Python base + Node.js overlaid) ────────────────────────
# python:3.13-slim is Trixie-based and ships Python 3.13 natively.
# node:20-slim is Bookworm-based where python3.13 is NOT in apt — hence we
# invert the base and install Node.js from NodeSource instead.
FROM python:3.13-slim AS runtime

# Install Node.js 20 from NodeSource using GPG key verification (not curl|bash)
# and git (for ANALYZE repo cloning) + dumb-init (PID 1 signal handling).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg git dumb-init \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
       | gpg --dearmor -o /usr/share/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
       > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* /usr/share/keyrings/nodesource.gpg

WORKDIR /app
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Next.js standalone bundle
COPY --from=web-build /app/.next/standalone ./
COPY --from=web-build /app/.next/static ./.next/static
COPY --from=web-build /app/public ./public

# Python worker source + deps
COPY --from=py-build /py-deps /py-deps
COPY apps/api ./apps/api
ENV PYTHONPATH=/py-deps:/app/apps/api

# Python worker location (read by spawn.ts via PYTHON_WORKER_CWD)
ENV PYTHON_WORKER_CWD=/app/apps/api
ENV PYTHON_BIN=python3

ENV HOSTNAME=0.0.0.0
EXPOSE 8080

# Non-root user for security; chown after all COPY ops complete
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app /py-deps
USER appuser

# dumb-init as PID 1 forwards signals to Node; Node spawns Python worker via instrumentation.ts
CMD ["dumb-init", "node", "server.js"]
