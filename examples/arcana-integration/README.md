# ArcanaInsight × Verum Integration Example

> **Note (2026-04-26):** The *actual* ArcanaInsight service uses **Phase 0** (OTLP env-only,
> zero code changes) by deliberate policy. `after.py` in this directory is a **Phase 1
> reference example** for other services that choose bidirectional integration.
> Phase 0 is equally valid — it enables full OBSERVE/EXPERIMENT/EVOLVE without touching
> the production codebase.

This example shows how a service using Grok 2 (via OpenAI-compatible API) can integrate
Verum in **Phase 1 bidirectional mode**. It is the reference implementation for the
**[5] DEPLOY** stage of The Verum Loop.

## The integration is literally 3 lines

```diff
+import verum.openai  # patches openai.Client transparently
+
 from openai import OpenAI

 client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

 response = client.chat.completions.create(
     model="grok-2-1212",
     messages=[...],
     temperature=0.8,
+    extra_headers={"x-verum-deployment": os.environ["VERUM_DEPLOYMENT_ID"]},
 )
```

That is the entire integration. No new client class, no wrapper function, no async
refactor. The `openai.Client` you already have keeps working exactly as before.

## How it works

`import verum.openai` monkey-patches the OpenAI SDK's HTTP layer. When the
`x-verum-deployment` header is present, Verum intercepts the request, applies the
active prompt variant for that deployment, and forwards the request to the LLM provider.
The response object returned to your code is identical to a normal OpenAI response.

Tracing is automatic via OTLP — every call with the header is recorded as a span in the
Verum backend. There is no `record()` call and no `trace_id` to manage in your code.

**Fail-open guarantee**: if Verum is unreachable (network error, service down), the SDK
falls back to the original request with the original messages. The LLM call proceeds
normally. Verum being unavailable never breaks your service.

## Prerequisites

Complete these steps in the Verum dashboard before running the integration:

1. **ANALYZE** — connect the ArcanaInsight repo; confirm all `chat.completions.create`
   call sites are detected
2. **INFER** — verify the domain is classified as `divination/tarot`
3. **HARVEST** — confirm ≥ 1,000 tarot knowledge chunks collected
4. **GENERATE** — approve at least one prompt variant (CoT or Few-shot)
5. **DEPLOY** — create a deployment; copy the `VERUM_DEPLOYMENT_ID`

## Installation

```bash
pip install verum
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `VERUM_API_URL` | Yes | Verum backend URL, e.g. `https://verum-production.up.railway.app` |
| `VERUM_API_KEY` | Yes | API key from the Verum dashboard |
| `VERUM_DEPLOYMENT_ID` | Yes | Deployment ID (prefix `dep_`) from the DEPLOY step |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | Override the OTLP endpoint for traces (Phase 0: Verum sends its own) |

Copy the template and fill in your values:

```bash
cp .env.example .env
```

## Before vs after

### before.py — original ArcanaInsight implementation

```python
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_PROMPT = """당신은 신비로운 타로 카드 리더입니다. ..."""


def read_tarot(question: str, cards: list[str]) -> str:
    response = client.chat.completions.create(
        model="grok-2-1212",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"질문: {question}\n뽑힌 카드: {', '.join(cards)}"},
        ],
        temperature=0.8,
    )
    return response.choices[0].message.content or ""
```

Problems with this approach:
- Improving the prompt requires editing code and redeploying
- No way to compare which prompt variant performs better
- Cost, latency, and quality metrics require separate instrumentation

### after.py — with Verum

```python
import os

import verum.openai  # noqa: F401 — side-effect import

from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_PROMPT = """당신은 신비로운 타로 카드 리더입니다. ..."""


def read_tarot(question: str, cards: list[str]) -> str:
    response = client.chat.completions.create(
        model="grok-2-1212",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"질문: {question}\n뽑힌 카드: {', '.join(cards)}"},
        ],
        temperature=0.8,
        extra_headers={"x-verum-deployment": os.environ["VERUM_DEPLOYMENT_ID"]},
    )
    return response.choices[0].message.content or ""
```

What changes after integration:
- Verum substitutes the active prompt variant (CoT, Few-shot, etc.) on each call
- Traffic is split automatically across variants — no code change needed to run A/B tests
- Every call is traced: model, latency, token cost, input/output
- Prompt improvements are applied from the dashboard; no redeployment required

## Verifying the integration

After deploying with the new code, open the Verum dashboard → **Deployments** and check:

| Item | Expected |
|---|---|
| Traces appearing | One span per `read_tarot()` call |
| Active variant | The variant selected by Verum (baseline or a generated variant) |
| Latency overhead | P95 < 10 ms added vs direct LLM call |

## What happens next (EVOLVE)

Once enough traffic accumulates, Verum runs the EXPERIMENT and EVOLVE stages
automatically:

1. Each variant accumulates calls until the Bayesian stopping criterion is met
   (confidence ≥ 0.95 or ≥ 100 calls per variant)
2. The winning variant is promoted to the default prompt for this deployment
3. A new candidate variant is generated and the cycle repeats

No code changes, no redeployments. This is the closed loop that is the point of Verum.

## Files in this directory

| File | Description |
|---|---|
| `before.py` | Original ArcanaInsight implementation without Verum |
| `after.py` | Same file after Verum integration |
| `.env.example` | Environment variable template |

## Related roadmap items

- F-3.8: Python SDK non-invasive integration (OTLP Phase 0)
- F-3.10: This example (ArcanaInsight first dogfood)
- F-4.11: First automatic prompt evolution cycle on production traffic
