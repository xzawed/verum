# apps/api

FastAPI backend — the engine that runs The Verum Loop.

**Status:** Phase 0 stub. Only `/health` is implemented.

## Structure

```
src/
├── main.py          # FastAPI app entry point + /health
├── loop/            # The Verum Loop stages (ADR-008: sacred structure)
│   ├── analyze/     # [1] Static repo analysis
│   ├── infer/       # [2] Service intent inference
│   ├── harvest/     # [3] Domain knowledge crawling
│   ├── generate/    # [4] Asset auto-generation
│   ├── deploy/      # [5] SDK injection
│   ├── observe/     # [6] Runtime tracing
│   ├── experiment/  # [7] A/B testing
│   └── evolve/      # [8] Winner promotion
├── integrations/    # GitHub OAuth, webhook handlers
└── db/              # SQLAlchemy models, session factory
```

## Running locally

```bash
# From repo root
make api-dev

# Or directly
cd apps/api
uvicorn src.main:app --reload
```

## See also

- [docs/ARCHITECTURE.md §3](../../docs/ARCHITECTURE.md#3-stage-to-module-map) — stage-to-module map
- [docs/LOOP.md](../../docs/LOOP.md) — stage algorithm reference
