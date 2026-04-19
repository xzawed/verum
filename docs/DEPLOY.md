# Deployment Verification

## Pre-push checklist

Before pushing any change that touches `apps/api/Dockerfile`, `apps/api/alembic/`,
`apps/api/src/db/`, or `apps/api/src/main.py`, run:

```bash
make verify-deploy
```

Expected output:
```
--- [1/4] Starting test Postgres (port 5433) ---
--- [2/4] Running alembic with Railway-style URL ---
INFO  [alembic.env] alembic: host=localhost ssl=off
INFO  [alembic.runtime.migration] Running upgrade ...
--- [3/4] Testing /health endpoint ---
{"status": "ok", "version": "0.0.0", "db": "disconnected"}
--- [4/4] Cleanup ---
=== verify-deploy PASSED ===
```

## What verify-deploy tests

1. **Railway-style URL conversion** — starts Postgres locally, passes `DATABASE_URL=postgres://verum:...` (same format Railway injects), and confirms alembic parses and connects correctly.
2. **All migrations apply cleanly** — `alembic upgrade head` succeeds from a clean schema.
3. **API starts successfully** — uvicorn starts and `/health` returns 200.

## Known limitations on this dev machine

- `docker build` of the production Dockerfile fails locally due to a DNS issue resolving `deb.debian.org` inside the builder container (apt-get for `git`). The image builds correctly on Railway (proper DNS). Workaround: run `verify-deploy` using local Python rather than a Docker container.
- Local Python is 3.14, but Railway uses 3.13 (from the Dockerfile). SQLAlchemy's ORM model scanning has a Python 3.14 incompatibility (`typing.Union.__getitem__`). This means `alembic upgrade head` fails locally **if and only if** SQLAlchemy model imports are triggered. If alembic fails locally for this reason, it is **not** a Railway issue.

## Railway-specific: SSL requirement

Railway's managed Postgres (accessed via `*.proxy.rlwy.net`) requires SSL. asyncpg does not enable SSL by default.

`apps/api/alembic/env.py` and `apps/api/src/db/session.py` both auto-detect remote hosts and pass `connect_args={"ssl": "require"}` to `create_async_engine`. Local/Docker hosts (`localhost`, `127.0.0.1`, `db`, `db-test`) get no SSL flag.

To verify the SSL detection:
```bash
python -c "
from urllib.parse import urlparse
LOCAL = {'localhost', '127.0.0.1', 'db', 'db-test', ''}
for url in [
    'postgresql+asyncpg://user:pw@localhost:5432/db',
    'postgresql+asyncpg://user:pw@db:5432/db',
    'postgresql+asyncpg://user:pw@autorack.proxy.rlwy.net:12345/railway',
]:
    host = urlparse(url).hostname or ''
    print(f'{host}: ssl={\"require\" if host not in LOCAL else \"off\"}')
"
```

## After a Railway deploy fails

1. Open Railway dashboard → your service → Deployments tab → click the failed deploy.
2. Scroll to the **bottom** of the build log (the exception class and message are there — not the traceback top).
3. Common exceptions and fixes:
   - `asyncpg.exceptions.InvalidPasswordError` → check Railway service variables tab; ensure `DATABASE_URL` is set and the PG plugin is linked.
   - `ssl.SSLError` or `asyncpg.InterfaceError: SSL` → SSL detection is not triggering; verify `env.py` is deployed.
   - `ConnectionRefusedError` → `DATABASE_URL` is pointing to localhost (env var not injected); re-link the Postgres plugin to the API service in Railway.
   - `sqlalchemy.exc.ProgrammingError: pgvector` → `CREATE EXTENSION vector` requires superuser; run `CREATE EXTENSION IF NOT EXISTS vector;` manually in Railway's Postgres console.
