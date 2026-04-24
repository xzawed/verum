# Integration Test Environment

This document describes the Verum integration test environment — a local Docker Compose stack that runs the full 8-stage Verum Loop (ANALYZE → EVOLVE) without touching any live services.

## Quick Start

```bash
# Start all services and run full test suite
make integration-up && make integration-test && make integration-down

# Smoke test only (30s)
make integration-smoke

# Keep stack running after tests for debugging
make integration-debug

# Stream service logs
make integration-logs

# Tear down everything (removes volumes)
make integration-down
```

## Architecture

The integration stack is defined in `docker-compose.integration.yml` and consists of 6 services:

```
test-runner ──▶ verum-app :8080 ◀──▶ db (pgvector) :5432
                     │
                     ▼
              mock-providers :9000
              (/anthropic, /voyage, /openai, /github, /wiki)
              (/control/calls, /control/fault, /control/reset)

git-http :80   (nginx + git-http-backend serving fixture bare repo)

fake-arcana    (SDK workload runner — 210 simulated LLM traces)
               ← waits for /integration-state/deployment_info.json
```

**Key design constraints:**
- `Dockerfile` is identical to Railway production — no test-only image
- `apps/api/src/loop/**` business logic is not modified
- All external API calls are intercepted by `mock-providers`
- Git clone uses the local `git-http` service (not GitHub)

## Env-Gated Hooks

Five (+ two P1) production hooks activated only when integration env vars are set:

| File | Variable | Default | Integration value |
|------|----------|---------|-------------------|
| `apps/api/src/loop/analyze/cloner.py` | `VERUM_ALLOW_INSECURE_CLONE_HOSTS` | `""` (github.com only) | `"git-http"` |
| `apps/api/src/worker/runner.py` | `VERUM_EXPERIMENT_INTERVAL_SECONDS` | `300` | `10` |
| `apps/dashboard/src/lib/github/repos.ts` | `GITHUB_API_BASE` | `api.github.com` | `mock-providers:9000/github` |
| `apps/dashboard/src/lib/github/pr-creator.ts` | `GITHUB_API_BASE` | `api.github.com` | `mock-providers:9000/github` |
| `apps/dashboard/src/auth.config.ts` | `GITHUB_OAUTH_BASE` | `github.com` | `mock-providers:9000/github` |
| `apps/api/src/worker/handlers/deploy.py` | `VERUM_DEPLOY_VARIANT_FRACTION` | `0.10` | `0.5` |
| `apps/api/src/worker/handlers/deploy.py` | `VERUM_TEST_MODE` | `""` | `"1"` (exposes `api_key` in job result) |

**None of these vars are set in Railway.** They only activate in the integration stack.

## Fixture Repo

`tests/fixtures/sample-repo/` is a minimal "ArcanaInsight" tarot service:

| File | LLM calls | Purpose |
|------|-----------|---------|
| `src/reading.ts` | 2 × OpenAI SDK | TypeScript SDK detection |
| `src/journal.ts` | 1 × raw fetch | URL pattern matching |
| `app/daily.py` | 1 × Anthropic SDK | Python SDK detection |

Expected ANALYZE output: `call_sites_count >= 4`, INFER `domain = "divination/tarot"`.

## Mock Provider API

The mock server at `:9000` supports:

### Anthropic (`/anthropic/v1/messages`)
- Matches requests by `sha256(system[:400] + last_user[:800] + model)[:16]` key
- Falls back to `_match_system_contains` field in fixture JSON
- Fixtures: `tests/integration/mock-providers/fixtures/anthropic/`

### Voyage (`/voyage/v1/embeddings`)
- Returns deterministic 1024-dim L2-normalized vectors seeded by text hash
- No fixture file needed

### OpenAI (`/openai/v1/embeddings`, `/openai/v1/chat/completions`)
- Embeddings: 1536-dim deterministic vectors
- Chat: returns fixed tarot response

### GitHub (`/github/...`)
- OAuth token, user info, repo list, Git Trees API (for SDK PR creation)
- Configured to serve `verum-test/arcana-mini` as the test repo

### Control endpoints
- `GET /control/calls` — returns all intercepted API calls
- `POST /control/fault` — inject faults: `{"endpoint": "anthropic", "kind": "http500", "count": 2}`
- `POST /control/reset` — clear fault state and call log

## Test Stages

| File | Timeout | What it tests |
|------|---------|--------------|
| `test_00_bootstrap.py` | 30s | Health, DB, auth bypass, empty call log |
| `test_10_analyze_to_infer.py` | 90s | Repo register → ANALYZE → INFER |
| `test_20_harvest_and_generate.py` | 120s | HARVEST chunks → GENERATE variants |
| `test_30_deploy_and_sdk.py` | 300s | DEPLOY + fake-arcana 210 traces |
| `test_40_judge_and_experiment.py` | 240s | JUDGE drain + experiment convergence |
| `test_50_evolve_closure.py` | 60s | EVOLVE + timeline artifact |

## Artifacts

After a run, `artifacts/integration/` contains:

- `timeline.md` — per-stage timing table from `verum_jobs`
- `snapshot/` — JSONL snapshots of 10 key tables (from failed tests)
- `service-logs.txt` — Docker Compose logs (CI only, on failure)

## CI

The integration suite runs:
- **Nightly** at 08:00 UTC (17:00 KST) via cron
- **On demand** via `workflow_dispatch`
- **On push** to `apps/api/src/loop/**`, `Dockerfile`, `tests/integration/**`

Status: informational only (not blocking PRs). Will be promoted to PR-blocking after 2 weeks of stable nightly runs.

## Troubleshooting

### `make integration-up` hangs

Check that Docker has enough resources. The stack needs ≥2 GB RAM.

```bash
docker compose -f docker-compose.integration.yml ps
docker compose -f docker-compose.integration.yml logs verum-app --tail=50
```

### `test_10` fails with "ANALYZE job timed out"

The git-http service may not have initialized the bare repo. Check:
```bash
docker compose -f docker-compose.integration.yml logs git-http
```

### `test_40` fails with "EVOLVE job was not enqueued"

The experiment loop runs every 10s. Check:
1. `VERUM_EXPERIMENT_INTERVAL_SECONDS` is set to `10` in the compose file
2. Both variants have ≥100 traces with `judge_score IS NOT NULL`
3. The experiment row exists: `SELECT * FROM experiments WHERE status = 'running'`

### Trace quota errors in fake-arcana logs

The free trace quota (default 1000) may be exhausted. Check:
```bash
docker compose -f docker-compose.integration.yml logs fake-arcana
```
The integration DB is ephemeral, so this won't happen unless you re-run without `make integration-down`.

## Adding New Fixtures

To add a new Anthropic mock response:

1. Capture the real request's system prompt and last user message
2. Compute the fixture key: `python3 -c "import hashlib; print(hashlib.sha256((system[:400]+last_user[:800]+model).encode()).hexdigest()[:16])"`
3. Create `tests/integration/mock-providers/fixtures/anthropic/<name>.json`
4. Set `"id"` to the hex key, or use `"_match_system_contains": "keyword"` for substring matching

## Security Notes

- `VERUM_TEST_MODE=1` exposes the plaintext `api_key` in `verum_jobs.result`
- This is intentional and safe because integration DB is ephemeral and never connects to production
- The `AUTH_SECRET` value used in integration is a well-known constant — never use it in production
