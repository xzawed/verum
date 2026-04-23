# Contributing to Verum

Thank you for your interest in Verum. This guide covers everything you need to make a contribution.

> **Core principle:** Every feature in Verum belongs to one of the 8 loop stages. If you cannot identify which stage your change belongs to, it may be out of scope.

---

## Development Setup

### Prerequisites

- Docker + Docker Compose
- Python 3.13+
- Node.js 20+
- pnpm 9+

### Quick start

```bash
git clone https://github.com/xzawed/verum
cd verum

# Copy environment file and fill in your keys
cp .env.example .env

# Start all services (PostgreSQL, Python worker, Next.js dashboard)
docker compose up

# Dashboard: http://localhost:3000
# Health:    http://localhost:3000/health
```

### Running tests locally

```bash
# Python (requires running PostgreSQL)
cd apps/api
pytest tests -v

# TypeScript type check
cd apps/dashboard && npx tsc --noEmit
cd packages/sdk-typescript && npx tsc --noEmit

# Full lint suite
make lint       # pylint + ruff + bandit + mypy + eslint
make type-check # mypy + tsc --noEmit
```

---

## Commit Message Format

Verum uses [Conventional Commits](https://www.conventionalcommits.org/) with **loop stage as scope**:

```
<type>(<stage>): <description>

feat(analyze):     add Go language support to AST detector
fix(judge):        use AsyncAnthropic client to avoid event loop block
feat(harvest):     implement Playwright fallback for JS-rendered pages
docs(generate):    update METHODOLOGY.md with new eval_pairs count
refactor(observe): extract cost calculation to shared utility
test(experiment):  add Bayesian stopping criterion unit tests
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

**Scopes:** `analyze`, `infer`, `harvest`, `generate`, `deploy`, `observe`, `experiment`, `evolve`, `sdk-python`, `sdk-typescript`, `dashboard`, `worker`, `db`, `infra`

Use `docs` scope (no stage) for cross-cutting documentation changes.

---

## Pull Request Rules

### Before opening a PR

- [ ] Tests pass: `make test`
- [ ] Lint passes: `make lint` + `make type-check`
- [ ] Loop stage identified (commit scope + PR template checkbox)
- [ ] ROADMAP F-ID referenced if applicable
- [ ] ArcanaInsight still works (run `make loop-analyze REPO=https://github.com/xzawed/ArcanaInsight`)

### If your PR changes a prompt, model, or scoring formula

**This is mandatory:** Include a diff to `docs/METHODOLOGY.md` in the same PR.

The rule: *the commit that changes the code and the commit that updates METHODOLOGY.md must be in the same PR*. Never split them.

### If your PR makes a significant architectural decision

Add an entry to `docs/DECISIONS.md` (index) and the full ADR text to `docs/ARCHITECTURE.md §7`. Use the existing ADR-00X format.

---

## Hard Rules (Do Not Violate)

These are non-negotiable. PRs that violate them will be closed without review.

| Rule | Reason |
|---|---|
| No LangChain or LlamaIndex in any package | Verum is their alternative; adding them breaks the core identity |
| No external vector DB (Pinecone, Weaviate, Qdrant, Chroma, etc.) | PostgreSQL + pgvector is the unified storage layer |
| `apps/api/src/loop/` must always have exactly 8 stage subdirectories | Any restructuring requires updating CLAUDE.md first |
| No hardcoded embedding dimensions | Store per-collection in `harvest_sources.embedding_dim` |
| GENERATE outputs are proposals, not automatic deployments | Users must approve before production traffic is affected |
| ANALYZE must work without running the target service | Static analysis only; service execution is OBSERVE territory |

---

## Testing Guidelines

- **Phase 0–1**: fast prototyping permitted, coverage target flexible
- **Phase 2+**: 80% coverage target for new loop stage code (`apps/api/src/loop/`)
- Test structure: `apps/api/tests/{stage}/test_{feature}.py`
- Integration tests that require a real database use the PostgreSQL fixture in `conftest.py` — do not mock the database

---

## Documentation

- **METHODOLOGY.md**: update in the same PR as any prompt/formula change (see above)
- **STATUS.md**: update at the end of each phase or when the file map changes
- **ROADMAP.md**: updated by maintainer (xzawed) only
- **CHANGELOG.md**: add an entry for every PR that ships user-visible behavior

---

## What Verum Is Not

To save time, here is what falls outside Verum's scope:

- A prompt management UI (we generate prompts automatically — users don't write them)
- A general-purpose RAG framework
- A replacement for Langfuse/LangSmith tracing (we observe in order to evolve, not just to monitor)
- A hosted LLM proxy (Verum routes traffic between variants, not between providers)

If your feature idea doesn't fit the 8-stage loop, it's likely out of scope. Open a discussion issue first.

---

## Contact

For security issues, see [SECURITY.md](SECURITY.md).  
For questions, open a [Question issue](https://github.com/xzawed/verum/issues/new?template=question.md).
