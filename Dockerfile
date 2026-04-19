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

# ── Stage 3: Runtime (Node base + Python overlaid) ───────────────────────────
FROM node:20-slim AS runtime

# Install Python 3.13 runtime (not dev) and git (for repo cloning in ANALYZE)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.13 python3.13-venv git \
    && rm -rf /var/lib/apt/lists/*

# Python bin alias so spawn.ts can call "python3" uniformly
RUN ln -sf /usr/bin/python3.13 /usr/local/bin/python3

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

EXPOSE 3000
# Node is PID 1; it spawns the Python worker via instrumentation.ts
CMD ["node", "server.js"]
