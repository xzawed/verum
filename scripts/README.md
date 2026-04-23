# Verum Scripts

## `seed_demo.py` — Demo Seed Script

Creates a realistic ArcanaInsight demo dataset in the Verum PostgreSQL database,
demonstrating the full Verum Loop in action with a converged A/B experiment.

### What it inserts

| Stage | Records |
|-------|---------|
| ANALYZE | 1 analysis (8 call sites, 5 prompt templates, TypeScript 72% / Python 28%) |
| INFER | 1 inference (`tarot_divination`, Korean, confidence=0.94) |
| HARVEST | 3 sources (Wikipedia, tarot-hermit.com, biddytarot.com) × 10 chunks = 30 chunks |
| GENERATE | 1 generation (5 prompt variants, RAG config, 20 eval pairs) |
| DEPLOY | 1 deployment (canary, `cot` variant at 100% traffic) |
| EXPERIMENT | 2 converged experiments (cot beat original @ 0.97, cot beat few_shot @ 0.96) |
| OBSERVE | 420 traces + 420 spans + 20 judge_prompts |
| model_pricing | 6 standard model rows (idempotent) |

The script is **idempotent** — safe to run multiple times.
All inserts use `ON CONFLICT DO NOTHING`.

### Prerequisites

- `DATABASE_URL` environment variable pointing to the Verum PostgreSQL instance
- Python packages: `sqlalchemy[asyncio]`, `asyncpg`

```bash
pip install "sqlalchemy[asyncio]" asyncpg
```

### Usage

```bash
# From the repo root
export DATABASE_URL="postgresql://user:pass@localhost:5432/verum"
cd apps/api && python ../../scripts/seed_demo.py
```

Or with a Railway DATABASE_URL (the script auto-converts `postgres://` prefixes):

```bash
DATABASE_URL="$(railway variables get DATABASE_URL)" \
  python scripts/seed_demo.py
```

### Resetting demo data

To remove all demo data without affecting other records:

```sql
-- Run in order to respect foreign key constraints
DELETE FROM judge_prompts
  WHERE trace_id IN (SELECT id FROM traces WHERE deployment_id IN (
    SELECT id FROM deployments WHERE generation_id IN (
      SELECT id FROM generations WHERE inference_id IN (
        SELECT id FROM inferences WHERE repo_id IN (
          SELECT id FROM repos WHERE owner_user_id = (
            SELECT id FROM users WHERE github_login = 'demo'
          )
        )
      )
    )
  ));

DELETE FROM spans       WHERE trace_id IN (SELECT id FROM traces WHERE deployment_id IN (SELECT id FROM deployments WHERE generation_id IN (SELECT id FROM generations WHERE inference_id IN (SELECT id FROM inferences WHERE repo_id IN (SELECT id FROM repos WHERE owner_user_id = (SELECT id FROM users WHERE github_login = 'demo'))))));
DELETE FROM traces      WHERE deployment_id IN (SELECT id FROM deployments WHERE generation_id IN (SELECT id FROM generations WHERE inference_id IN (SELECT id FROM inferences WHERE repo_id IN (SELECT id FROM repos WHERE owner_user_id = (SELECT id FROM users WHERE github_login = 'demo')))));
DELETE FROM experiments WHERE deployment_id IN (SELECT id FROM deployments WHERE generation_id IN (SELECT id FROM generations WHERE inference_id IN (SELECT id FROM inferences WHERE repo_id IN (SELECT id FROM repos WHERE owner_user_id = (SELECT id FROM users WHERE github_login = 'demo')))));
DELETE FROM deployments WHERE generation_id IN (SELECT id FROM generations WHERE inference_id IN (SELECT id FROM inferences WHERE repo_id IN (SELECT id FROM repos WHERE owner_user_id = (SELECT id FROM users WHERE github_login = 'demo'))));
DELETE FROM generations WHERE inference_id IN (SELECT id FROM inferences WHERE repo_id IN (SELECT id FROM repos WHERE owner_user_id = (SELECT id FROM users WHERE github_login = 'demo')));
DELETE FROM chunks      WHERE inference_id IN (SELECT id FROM inferences WHERE repo_id IN (SELECT id FROM repos WHERE owner_user_id = (SELECT id FROM users WHERE github_login = 'demo')));
DELETE FROM harvest_sources WHERE inference_id IN (SELECT id FROM inferences WHERE repo_id IN (SELECT id FROM repos WHERE owner_user_id = (SELECT id FROM users WHERE github_login = 'demo')));
DELETE FROM inferences  WHERE repo_id IN (SELECT id FROM repos WHERE owner_user_id = (SELECT id FROM users WHERE github_login = 'demo'));
DELETE FROM analyses    WHERE repo_id IN (SELECT id FROM repos WHERE owner_user_id = (SELECT id FROM users WHERE github_login = 'demo'));
DELETE FROM repos       WHERE owner_user_id = (SELECT id FROM users WHERE github_login = 'demo');
DELETE FROM users       WHERE github_login = 'demo';
```
