<div align="center">

# Verum

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/xzawed/verum/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/verum/actions/workflows/ci.yml)
[![Codecov](https://img.shields.io/codecov/c/github/xzawed/verum?logo=codecov&logoColor=white)](https://codecov.io/gh/xzawed/verum)
[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=xzawed_verum&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=xzawed_verum)
[![Phase](https://img.shields.io/badge/Phase-4B%20Complete%20%E2%80%94%20EXPERIMENT%20%2B%20EVOLVE-brightgreen)](docs/ROADMAP.md)
[![Last Commit](https://img.shields.io/github/last-commit/xzawed/verum?logo=git&logoColor=white)](https://github.com/xzawed/verum/commits/main)
[![GitHub stars](https://img.shields.io/github/stars/xzawed/verum?style=social)](https://github.com/xzawed/verum/stargazers)

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](apps/api)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white)](apps/dashboard)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white)](apps/dashboard/tsconfig.json)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg?logo=ruff)](https://github.com/astral-sh/ruff)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20+%20pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Deployed on Railway](https://img.shields.io/badge/Deployed%20on-Railway-blueviolet?logo=railway&logoColor=white)](https://railway.app)

**Connect your repo. Verum learns how your AI actually behaves,  
then auto-builds and auto-evolves everything around it.**

[Quick Start](#-quick-start) · [Integration](#-integration--arcanainsight) · [FAQ](#-faq) · [Roadmap](docs/ROADMAP.md) · [Architecture](docs/ARCHITECTURE.md) · [Loop Reference](docs/LOOP.md)

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
| 🔬 ANALYZE | ✅ Done | AST-based LLM call detection (JS/TS); Python deferred to Phase 1.5 |
| 🧠 INFER | ✅ Done | Claude Sonnet 4.6 classifies domain, tone, user type |
| 🌾 HARVEST | ✅ Done | Domain-aware web crawl → chunked embeddings in pgvector |
| 🔍 RETRIEVE | ✅ Done | Hybrid vector + full-text search over harvested knowledge *(support stage — invoked by DEPLOY/SDK, not a loop step)* |
| ✨ GENERATE | ✅ Done | Prompt variants, RAG config, eval dataset — auto-chained after HARVEST |
| 🚀 DEPLOY | ✅ Done | SDK-based canary deployment with traffic splitting + rollback |
| 👁️ OBSERVE | ✅ Done | Trace + span ingestion, cost/latency metrics, LLM-as-Judge scoring |
| 🧪 EXPERIMENT | ✅ Done | Sequential pairwise Bayesian A/B across 5 prompt variants |
| 🔄 EVOLVE | ✅ Done | Auto-promote winners, archive losers — no manual intervention |

---

## ⚡ Quick Start

### Step 1 — Self-host

```bash
git clone https://github.com/xzawed/verum
cd verum
docker compose up
# Dashboard: http://localhost:3000
# Health:    http://localhost:3000/health
```

### Step 2 — Sign in with GitHub OAuth

Open `http://localhost:3000/login` and click "Sign in with GitHub".  
Requires `AUTH_GITHUB_ID` and `AUTH_GITHUB_SECRET` in your environment (see `.env.example`).

### Step 3 — Register a repo → auto-analysis

On the `/repos` page, click "Register" on any of your GitHub repos.  
From this point, **`ANALYZE → INFER → HARVEST → GENERATE` run automatically.**

You can watch each stage's progress in real-time on the dashboard.

### Step 4 — Review & approve GENERATE results

On the `/repos/<id>` page, inspect the 5 prompt variants, RAG config, and eval dataset that Verum generated, then click "Approve".  
**DEPLOY is gated until you approve** — no unintended auto-deployment.

### Step 5 — Deploy → SDK integration

Approving issues an API key alongside a `deployments` row. Add the SDK to your service:

```bash
pip install verum            # Python SDK
npm install @verum/sdk       # TypeScript SDK
```

```python
import verum

client = verum.Client(
    api_url=os.environ["VERUM_API_URL"],
    api_key=os.environ["VERUM_API_KEY"],
)

result = await client.chat(
    messages=[...],
    deployment_id=os.environ["VERUM_DEPLOYMENT_ID"],
    provider="openai",
    model="gpt-4o-mini",
)
# pass result["messages"] to your LLM SDK as usual
```

### Step 6 — Auto-evolution begins

From here it's automatic:
- Traffic splits across 5 variants (EXPERIMENT)
- Bayesian winner auto-promoted once confidence threshold is reached (EVOLVE)
- Scoring combines user feedback, cost, latency, and LLM-as-Judge

---

## 🔌 Integration — ArcanaInsight

A real-world example of integrating Verum into a tarot reading service ([examples/arcana-integration/](examples/arcana-integration/)).

### Before — static prompt + direct OpenAI call

```python
# examples/arcana-integration/before.py
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_PROMPT = """You are a mystical tarot card reader.
Using the Celtic Cross spread, you read the questioner's past, present, and future.
Write your reading in a mystical and insightful tone, yet warm and empathetic."""  # hardcoded

def read_tarot(question, cards):
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{question} / {cards}"},
        ],
    ).choices[0].message.content
```

Problems:
- Prompt improvements require manual work
- No observability (latency, cost, satisfaction untracked)
- A/B testing infrastructure requires separate implementation

### After — one-line swap to Verum

```python
# examples/arcana-integration/after.py
import verum

client = verum.Client(
    api_url=os.environ["VERUM_API_URL"],
    api_key=os.environ["VERUM_API_KEY"],
)
DEPLOYMENT_ID = os.environ["VERUM_DEPLOYMENT_ID"]

async def read_tarot(question, cards):
    result = await client.chat(
        messages=[
            {"role": "system", "content": _FALLBACK_SYSTEM},  # used only when Verum is unreachable
            {"role": "user", "content": f"{question} / {cards}"},
        ],
        deployment_id=DEPLOYMENT_ID,
        provider="openai",
        model="gpt-4o-mini",
    )
    # result["routed_to"]: "baseline" or "variant/<name>"
    return result["messages"][-1]["content"]
```

What you get automatically:
- ✅ Verum dashboard manages 5 system prompt variants
- ✅ Every call auto-traced (latency, cost, model, feedback)
- ✅ A/B test runs automatically across variants
- ✅ Winning prompt auto-promoted on Bayesian convergence

Full code: [examples/arcana-integration/after.py](examples/arcana-integration/after.py)

---

## ❓ FAQ

### Q1. Does Verum modify my repo or create PRs?

**No.** Verum never changes your code.

- The ANALYZE stage does a `git clone --depth 1` into a temp directory, performs *read-only* static analysis, and deletes the clone on exit ([cloner.py](apps/api/src/loop/analyze/cloner.py)).
- There is **no** `git push`, PR creation, or write-scoped GitHub token anywhere in the codebase.
- You add the SDK to your own service yourself (one-line import + Client instantiation).

### Q2. Does "DEPLOY" automatically deploy my service to production?

**No.** Verum's "DEPLOY" means:
1. INSERT a row into the `deployments` table
2. Issue an API key (`vrm_...`)
3. Activate traffic-split configuration

Your service's SDK polls this deployment row at runtime. You continue deploying your own service however you normally do (Vercel, AWS, your own server, etc.).

### Q3. Which stage transitions are automatic vs. manual?

| Transition | Automatic | Notes |
|---|---|---|
| Repo registered → ANALYZE | ✅ Auto | Starts immediately on registration |
| ANALYZE → INFER | ✅ Auto | Worker enqueues next job on completion |
| INFER → HARVEST | ✅ Auto | Domain inferred → crawl sources auto-approved |
| HARVEST → GENERATE | ✅ Auto | Embeddings done → prompt generation auto-starts |
| GENERATE → DEPLOY | ❌ **User approval required** | Click "Approve" on the dashboard |
| OBSERVE → EXPERIMENT → EVOLVE | ✅ Auto | Runs automatically as traffic accumulates |

### Q4. What does it cost?

Verum itself is **free and open-source (MIT)**. Costs come from the external APIs you call:
- **INFER + GENERATE**: Anthropic Claude API (Sonnet 4.6)
- **HARVEST**: Voyage AI embeddings API (`voyage-3.5`, 1024-dim)
- **Your LLM calls**: Your own OpenAI / Anthropic / Grok spend (Verum adds no markup)
- **Infrastructure**: Your own server for self-hosted; a subscription for Verum Cloud (coming soon)

### Q5. Can I use a vector DB other than pgvector?

**No.** Per ADR-001, only pgvector is supported ([DECISIONS.md](docs/DECISIONS.md)).  
Reason: single-datastore principle and the `docker compose up` self-hosting constraint.

### Q6. Does Verum support LangChain or LlamaIndex?

**No.** Per ADR-002, neither library is allowed as a dependency.  
Verum is an *alternative* to and *layer above* them — adding a dependency would undermine its identity. Only low-level libraries (`openai`, `anthropic`, `httpx`) are used directly.

### Q7. When will Python AST analysis be available?

Planned for Phase 1.5 (F-1.3). Currently only JS/TS tree-sitter-based detection is live.

### Q8. Does Verum work for domains other than tarot?

Yes. The INFER stage classifies the domain automatically, and HARVEST applies a domain-appropriate crawling strategy. 20 initial domain categories are supported (tarot/divination, code review, legal Q&A, medical, etc.). For new domains, INFER maps to the closest category and the HARVEST sources are surfaced for user review and editing before crawling begins.

---

## 🆚 How Verum Differs

| Tool | What it does | What Verum adds |
|---|---|---|
| Langfuse / LangSmith | Observe LLM calls | Auto-generates and evolves prompts + RAG from observations |
| RAGAS | Evaluate RAG | Auto-builds the eval dataset and runs it in CI |
| PromptLayer | Version prompts | AI writes the prompts and picks winners via A/B |
| CodeRabbit / SCAManager | Code review | Uses code analysis to optimize the AI service itself |

**In one sentence**: Other tools help humans operate LLM systems. Verum helps LLM systems operate themselves.

---

## 🏗️ Tech Stack

**Backend** — Python 3.13, asyncio, SQLAlchemy 2, Alembic, PostgreSQL 16 + pgvector  
**Frontend** — Next.js 16, React 19, TypeScript strict, Auth.js v5, Drizzle ORM  
**AI** — Claude Sonnet 4.6 (INFER + GENERATE), Voyage AI `voyage-3.5` (embeddings, 1024-dim)  
**Infra** — Railway, Docker (single image: Node PID1 + Python worker subprocess)

---

## 📄 License

MIT — see [LICENSE](LICENSE).

Every feature is open source. The only difference between self-hosted and Verum Cloud is who runs the infrastructure — there is no feature paywall.
