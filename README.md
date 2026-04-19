# Verum

> *Connect your repo. Verum learns how your AI actually behaves, then auto-builds and auto-evolves everything around it — prompts, RAG, evals, observability.*

> **Not affiliated with Verum AI Platform (verumai.com).**

---

## What Verum Does

Verum is an open-source platform that auto-analyzes and auto-optimizes AI services.

Connect a GitHub repo → Verum statically analyzes your LLM calls → understands your service's domain → automatically builds prompts, RAG pipelines, and evaluation sets → deploys them with A/B testing → evolves the winners without manual intervention.

```
[1] ANALYZE  →  [2] INFER  →  [3] HARVEST  →  [4] GENERATE
      ↑                                               ↓
[8] EVOLVE   ←  [7] EXPERIMENT  ←  [6] OBSERVE  ←  [5] DEPLOY
```

This loop runs continuously. Your AI service gets better without you writing a single prompt.

---

## How Verum Differs

| Tool | What it does | What Verum adds |
|---|---|---|
| Langfuse / LangSmith | Observe LLM calls | Auto-generates and evolves prompts + RAG from observations |
| RAGAS | Evaluate RAG | Auto-builds the evaluation dataset and runs it in CI |
| PromptLayer | Version prompts | AI writes the prompts and picks winners via A/B |

---

## Quickstart

> Coming in [Phase 5](docs/ROADMAP.md#phase-5-launch-week-19-24).

Self-hosted preview (Phase 0):

```bash
git clone https://github.com/xzawed/verum
cd verum
docker compose up
curl http://localhost:8000/health
```

---

## Repository Layout

See [docs/ARCHITECTURE.md §2](docs/ARCHITECTURE.md#2-repository-layout) for the full annotated file tree.

Key directories:

| Path | Purpose |
|---|---|
| `apps/api/src/loop/` | The 8-stage loop implementation (sacred — see ADR-008) |
| `apps/dashboard/` | Next.js 16 observability + control dashboard |
| `packages/sdk-python/` | `pip install verum` |
| `packages/sdk-typescript/` | `npm install @verum/sdk` |
| `examples/arcana-integration/` | First dogfood: ArcanaInsight integration |
| `docs/` | Architecture, roadmap, loop reference, ADRs |

---

## Documentation

| Document | Purpose |
|---|---|
| [docs/INDEX.md](docs/INDEX.md) | Navigation hub — read second, after CLAUDE.md |
| [docs/LOOP.md](docs/LOOP.md) | Stage algorithms, I/O contracts, completion criteria |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Schemas, API surface, SDK surface, ADRs |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 6-month roadmap with F-IDs |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | Vocabulary reference |

---

## License

MIT — see [LICENSE](LICENSE).

All features are open-source. The only difference between self-hosted and the Verum cloud is who operates the infrastructure.
