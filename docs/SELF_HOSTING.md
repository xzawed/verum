# Verum — Self-Hosting Guide

Run Verum on your own infrastructure. No Verum account required.

---

## Prerequisites

- Docker 24+ and Docker Compose v2
- PostgreSQL 16+ with pgvector extension (or use the provided Compose file)
- A GitHub OAuth App (for repo access)
- API keys: Anthropic and Voyage AI

---

## Quick Start (Docker Compose)

Clone the repository and copy the example environment file:

```bash
git clone https://github.com/xzawed/verum.git
cd verum
cp .env.example .env   # edit with your values
```

Start the stack:

```bash
docker compose up -d
```

Open `http://localhost:3000` and sign in with GitHub.

The Docker Compose file starts two services: a PostgreSQL 16 + pgvector database and the Verum application image (Node.js PID 1 + Python worker child process). No Redis, no Celery, no separate API server.

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: verum
      POSTGRES_PASSWORD: verum
      POSTGRES_DB: verum
    ports:
      - "5432:5432"
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U verum"]
      interval: 5s
      retries: 5

  dashboard:
    build: .
    environment:
      DATABASE_URL: postgresql+asyncpg://verum:verum@db:5432/verum
      NEXTAUTH_SECRET: change-me
      NEXTAUTH_URL: http://localhost:3000
      GITHUB_CLIENT_ID: ...
      GITHUB_CLIENT_SECRET: ...
      ANTHROPIC_API_KEY: ...
      VOYAGE_API_KEY: ...
      HOSTNAME: 0.0.0.0
    ports:
      - "3000:8080"
    depends_on:
      db:
        condition: service_healthy

volumes:
  db_data:
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string. Must use `postgresql+asyncpg://` scheme. |
| `NEXTAUTH_SECRET` | Yes | Random 64-character hex string. Generate with `openssl rand -hex 32`. |
| `NEXTAUTH_URL` | Yes | Public base URL of your deployment (e.g. `https://verum.yourdomain.com`). |
| `GITHUB_CLIENT_ID` | Yes | From your GitHub OAuth App. |
| `GITHUB_CLIENT_SECRET` | Yes | From your GitHub OAuth App. |
| `ANTHROPIC_API_KEY` | Yes | Used for INFER, GENERATE, and LLM-as-Judge scoring. |
| `VOYAGE_API_KEY` | Yes | Used for HARVEST embeddings (voyage-3.5, 1024-dim). Must start with `pa-`. |
| `GENERATE_MODEL` | No | LLM for generation. Defaults to `claude-sonnet-4-6`. |
| `NODE_ENV` | No | Set to `production` for production deployments. |

---

## GitHub OAuth App Setup

1. Go to **github.com/settings/developers** → **OAuth Apps** → **New OAuth App**
2. Fill in the fields:
   - **Application name**: Verum (self-hosted)
   - **Homepage URL**: your deployment URL (e.g. `https://verum.yourdomain.com`)
   - **Authorization callback URL**: `https://verum.yourdomain.com/api/auth/callback/github`
3. Click **Register application**
4. Copy the **Client ID** and generate a **Client Secret**
5. Set `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` in your environment

For local development use `http://localhost:3000` as the homepage URL and `http://localhost:3000/api/auth/callback/github` as the callback URL.

---

## Railway Deployment

Verum is designed to run as a single Railway service.

1. Fork the repository to your GitHub account
2. Create a new Railway project and connect the fork
3. Add a **PostgreSQL** plugin — Railway injects `DATABASE_URL` automatically
4. Set the remaining environment variables in Railway's variable editor:
   - `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`
   - `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`
5. Deploy — Railway builds the Dockerfile and starts the service on port 8080

Railway injects `PORT=8080` automatically. The health check at `GET /health` is used by Railway to confirm the service is ready.

---

## Database Migrations

Migrations run automatically when the Python worker starts. If you need to run them manually:

```bash
cd apps/api
alembic upgrade head
```

To create a new migration after a schema change:

```bash
cd apps/api
alembic revision --autogenerate -m "describe your change"
```

---

## Health Check

`GET /health` returns HTTP 200 with no authentication required:

```json
{"status": "ok", "version": "0.0.0", "db": "connected"}
```

Use this endpoint for uptime monitoring and load balancer health probes.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Dashboard unreachable after deploy | `HOSTNAME` not set to `0.0.0.0` | Ensure `ENV HOSTNAME=0.0.0.0` is in the Dockerfile (already present by default) |
| `/health` returns 307 redirect | Auth middleware blocking the route | Verify `middleware.ts` matcher excludes `/health` |
| Python worker not processing jobs | Worker failed to start | Check container logs for startup errors; ensure `DATABASE_URL` is reachable from the container |
| Embeddings fail with auth error | Wrong or missing Voyage key | Verify `VOYAGE_API_KEY` starts with `pa-` and has active credits |
| LLM Judge scores never appear | Anthropic key missing or invalid | Verify `ANTHROPIC_API_KEY` is set and the account has API access |
| `alembic upgrade head` fails | Database not reachable | Confirm `DATABASE_URL` is correct and the database accepts connections |

---

> Not affiliated with Verum AI Platform (verumai.com).
