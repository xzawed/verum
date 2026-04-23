# Verum — Quickstart

Connect a GitHub repo and watch Verum analyze your AI service, generate optimized prompts and RAG, and start evolving them automatically — in under 30 minutes.

> **Note:** Verum Cloud (verum.dev) is not yet live. Use the self-hosted path below.

---

## Prerequisites

- A GitHub account with a repo containing LLM calls (OpenAI, Anthropic, or Grok SDK)
- Docker + Docker Compose
- `ANTHROPIC_API_KEY` — used by INFER, GENERATE, and OBSERVE stages
- `VOYAGE_API_KEY` — used for embeddings in the HARVEST stage

---

## 1. Start Verum (self-hosted)

```bash
git clone https://github.com/xzawed/verum
cd verum
cp .env.example .env        # fill in ANTHROPIC_API_KEY and VOYAGE_API_KEY
docker compose up
```

Dashboard: [http://localhost:3000](http://localhost:3000)
Health check: [http://localhost:3000/health](http://localhost:3000/health)

---

## 2. Connect Your Repo

1. Open [http://localhost:3000](http://localhost:3000) and sign in with GitHub.
2. Click **Connect Repo** and select your repository.
3. Grant the requested read access — Verum never writes to your repo.

The loop starts immediately.

---

## 3. Watch the Loop Run

| Stage | What happens | Typical duration |
|---|---|---|
| **ANALYZE** | Detects LLM call sites, extracts prompt strings and model params | < 60 s |
| **INFER** | Classifies domain, tone, and user type (e.g. `{"domain": "tarot_divination", "tone": "mystical"}`) | < 30 s |
| **HARVEST** | Crawls domain knowledge sources, chunks, and stores embeddings in pgvector | 2–5 min |
| **GENERATE** | Produces 5 prompt variants, a RAG config, and 30 eval pairs | < 60 s |

Once GENERATE finishes, the dashboard shows the generated assets. Review them, then click **Approve & Deploy**.

> **Note:** DEPLOY creates a canary at 10% traffic. Your existing calls are not affected until you wrap them with the SDK (step 4).

Copy the `DEPLOYMENT_ID` shown on the deploy confirmation screen.

---

## 4. Install the SDK and Wrap Your LLM Call

```bash
pip install verum
```

Set two environment variables in your service:

```
VERUM_API_URL=http://localhost:3000
VERUM_API_KEY=<your-deployment-id>
```

Replace your LLM call with the Verum-routed version:

```python
import os
import time
import openai
import verum

client = verum.Client()  # reads VERUM_API_URL + VERUM_API_KEY from env
openai_client = openai.OpenAI()

async def call_llm(user_input: str) -> str:
    # Route the request through Verum (picks a prompt variant)
    routed = await client.chat(
        messages=[{"role": "user", "content": user_input}],
        deployment_id=os.environ["DEPLOYMENT_ID"],
        provider="openai",
        model="gpt-4o",
    )

    # Call your LLM as usual with the routed messages
    t0 = time.monotonic()
    resp = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=routed["messages"],
    )
    latency_ms = (time.monotonic() - t0) * 1000

    # Record the trace so Verum can score and compare variants
    trace_id = await client.record(
        deployment_id=routed["deployment_id"],
        variant=routed["routed_to"],
        model="gpt-4o",
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        latency_ms=latency_ms,
    )

    # Optional: send user feedback (thumbs up/down)
    # await client.feedback(trace_id, score=1)   # 1 = positive, -1 = negative

    return resp.choices[0].message.content
```

---

## 5. OBSERVE → EXPERIMENT → EVOLVE (automatic)

Once traces start arriving:

- **OBSERVE** — LLM-as-Judge scores each response within 60 seconds.
- **EXPERIMENT** — Every 5 minutes, Bayesian A/B testing compares the 5 variants. Convergence typically requires ~100 calls per variant.
- **EVOLVE** — When a winner is statistically confirmed, it is promoted automatically. No manual action needed.

You can watch progress live on the **Experiments** tab in the dashboard.

---

## What Happens Next

| Resource | Description |
|---|---|
| `docs/LOOP.md` | Deep dive into each of the 8 loop stages |
| `docs/ARCHITECTURE.md` | System design and component boundaries |
| SDK reference | `packages/sdk-python/README.md` |
| Self-hosting guide | `docs/SELF_HOSTING.md` |

For questions or issues, open a GitHub issue at [github.com/xzawed/verum](https://github.com/xzawed/verum).
