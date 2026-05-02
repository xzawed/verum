<div align="center">

<p align="right"><a href="README.ko.md">🇰🇷 한국어</a></p>

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
| 🔬 ANALYZE | ✅ Done | AST-based LLM call detection (JS/TS + Python; all 5 patterns — openai, anthropic, xai_grok, google.generativeai, azure) |
| 🧠 INFER | ✅ Done | Claude Sonnet 4.6 classifies domain, tone, user type |
| 🌾 HARVEST | ✅ Done | Domain-aware web crawl → chunked embeddings in pgvector |
| 🔍 RETRIEVE | ✅ Done | Vector similarity search (cosine) over harvested knowledge *(support stage — invoked by DEPLOY/SDK, not a loop step)* |
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

Click "Approve" to unlock deployment, then click "Deploy" to issue an API key and activate a `deployments` row. Add the SDK to your service:

```bash
# Install from the monorepo (SDKs not yet published to PyPI/npm)
pip install -e ./packages/sdk-python       # Python SDK
npm install ./packages/sdk-typescript      # TypeScript SDK
```

```python
# 1. Add one import at the top of your entrypoint (non-invasive — no other code changes)
import verum.openai  # patches OpenAI client silently

from openai import OpenAI
import os

client = OpenAI()

# 2. Add x-verum-deployment header to your existing OpenAI calls
resp = client.chat.completions.create(
    model="grok-2-1212",
    messages=[{"role": "user", "content": "Tell me about the Moon card"}],
    extra_headers={"x-verum-deployment": os.environ["VERUM_DEPLOYMENT_ID"]},
)
print(resp.choices[0].message.content)
```

**Fail-open guarantee**: If Verum is unreachable for any reason, the call proceeds to the LLM exactly as if Verum were not there. A 5-layer safety net (200ms hard timeout → circuit breaker → 60s fresh cache → 24h stale cache → fail-open) ensures Verum never blocks or errors your service.

### Step 6 — Auto-evolution begins

From here it's automatic:
- Sequential Bayesian A/B testing across prompt variants (EXPERIMENT)
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

### After — 1-line integration

```python
# examples/arcana-integration/after.py
import verum.openai  # ← the only addition; patches OpenAI client automatically

from openai import OpenAI
import os

client = OpenAI()

def read_tarot(question, cards):
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": f"{question} / {cards}"},
        ],
        extra_headers={"x-verum-deployment": os.environ["VERUM_DEPLOYMENT_ID"]},
    )
    return resp.choices[0].message.content
```

The diff between "before" and "after" is exactly two changes: one `import verum.openai` line at the top, and `extra_headers` added to the existing call. Everything else — the OpenAI client, call signature, and response type — stays identical.

What you get automatically:
- ✅ Verum dashboard manages 5 system prompt variants
- ✅ Every call auto-traced via OTLP (latency, cost, model, feedback)
- ✅ A/B test runs automatically across variants
- ✅ Winning prompt auto-promoted on Bayesian convergence
- ✅ If Verum is unreachable, your service continues 100% normally (fail-open)

Full code: [examples/arcana-integration/after.py](examples/arcana-integration/after.py)

---

## ❓ FAQ

### Q1. Does Verum modify my repo or create PRs?

**Verum never modifies your application code.** The ANALYZE stage does a `git clone --depth 1` into a temp directory, performs *read-only* static analysis, and deletes the clone on exit ([cloner.py](apps/api/src/loop/analyze/cloner.py)). No `git push`, no file changes to your repository.

**Optional exception:** The dashboard offers an "SDK Integration PR" feature (`/api/repos/[id]/sdk-pr`) that can open a GitHub pull request adding the Verum SDK dependency (e.g. a line in `requirements.txt` and one `import` at your entrypoint). This is strictly opt-in — Verum only opens the PR if you click the button and grant write access. The PR adds *only* the SDK wiring; your application logic and prompts are never touched.

### Q2. Does "DEPLOY" automatically deploy my service to production?

**No.** Verum's "DEPLOY" means:
1. INSERT a row into the `deployments` table
2. Issue an API key (`vk_...`)
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

### Q7. Does Verum analyze Python code as well as JavaScript/TypeScript?

Yes. Python AST-based LLM call detection shipped in PR #79 (F-1.3). Verum detects calls to `openai`, `anthropic`, `xai_grok`, `google.generativeai`, and Azure OpenAI in both Python and JS/TS codebases.

### Q8. Does Verum work for domains other than tarot?

Yes. The INFER stage classifies the domain automatically, and HARVEST applies a domain-appropriate crawling strategy. 20 initial domain categories are supported (tarot/divination, code review, legal Q&A, medical, etc.). For new domains, INFER maps to the closest category and the HARVEST sources are surfaced for user review and editing before crawling begins.
