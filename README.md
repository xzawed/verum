<div align="center">

# Verum

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/xzawed/verum/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/verum/actions/workflows/ci.yml)
[![Phase](https://img.shields.io/badge/Phase-4B%20Complete%20%E2%80%94%20EXPERIMENT%20%2B%20EVOLVE-brightgreen)](docs/ROADMAP.md)
[![Deployed on Railway](https://img.shields.io/badge/Deployed%20on-Railway-blueviolet?logo=railway&logoColor=white)](https://railway.app)
[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](apps/api)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white)](apps/dashboard)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20+%20pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)

**Connect your repo. Verum learns how your AI actually behaves,  
then auto-builds and auto-evolves everything around it.**

[Roadmap](docs/ROADMAP.md) · [Architecture](docs/ARCHITECTURE.md) · [Loop Reference](docs/LOOP.md)

> Not affiliated with Verum AI Platform (verumai.com).

</div>

---

## 🔁 The Loop

Verum runs an 8-stage pipeline from static analysis to autonomous evolution — no manual prompting required.

```
🔬 ANALYZE  →  🧠 INFER  →  🌾 HARVEST  →  ✨ GENERATE
     ↑                                              ↓
🔄 EVOLVE   ←  🧪 EXPERIMENT  ←  👁️ OBSERVE  ←  🚀 DEPLOY
```

Register a GitHub repo once. The loop runs automatically.

---

## ✅ What's Live

| Stage | Status | Description |
|---|---|---|
| 🔬 ANALYZE | ✅ Done | AST-based LLM call detection across Python + JS/TS repos |
| 🧠 INFER | ✅ Done | Claude Sonnet 4.6 classifies domain, tone, user type |
| 🌾 HARVEST | ✅ Done | Domain-aware web crawl → chunked embeddings in pgvector |
| 🔍 RETRIEVE | ✅ Done | Hybrid vector + full-text search over harvested knowledge |
| ✨ GENERATE | ✅ Done | Prompt variants, RAG config, eval dataset — auto-chained after HARVEST |
| 🚀 DEPLOY | ✅ Done | SDK-based canary deployment with traffic splitting + rollback |
| 👁️ OBSERVE | ✅ Done | Trace + span ingestion, cost/latency metrics, LLM-as-Judge scoring |
| 🧪 EXPERIMENT | ✅ Done | Sequential pairwise Bayesian A/B across 5 prompt variants |
| 🔄 EVOLVE | ✅ Done | Auto-promote winners, archive losers — no manual intervention |

---

## ⚡ Self-Hosted Preview

```bash
git clone https://github.com/xzawed/verum
cd verum
docker compose up
# Dashboard: http://localhost:3000
# Health:    http://localhost:3000/health
```

---

## 🆚 How Verum Differs

| Tool | What it does | What Verum adds |
|---|---|---|
| Langfuse / LangSmith | Observe LLM calls | Auto-generates and evolves prompts + RAG from observations |
| RAGAS | Evaluate RAG | Auto-builds the eval dataset and runs it in CI |
| PromptLayer | Version prompts | AI writes the prompts and picks winners via A/B |

---

## 🏗️ Tech Stack

**Backend** — Python 3.13, asyncio, SQLAlchemy 2, Alembic, PostgreSQL 16 + pgvector  
**Frontend** — Next.js 16, React 19, TypeScript strict, Auth.js v5, Drizzle ORM  
**AI** — Claude Sonnet 4.6 (INFER + GENERATE), Voyage AI `voyage-3.5` (embeddings, 1024-dim)  
**Infra** — Railway, Docker (single image: Node PID1 + Python worker subprocess)

---

## 📄 License

MIT — see [LICENSE](LICENSE).

All features are open-source. The only difference between self-hosted and the Verum cloud is who operates the infrastructure.
