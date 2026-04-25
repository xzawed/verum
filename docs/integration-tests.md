# Integrating Verum Into Your Service

This guide walks you from zero to a fully connected Verum integration. There are two phases — start with whichever fits your timeline.

> **Fail-open guarantee**: Both phases ensure your LLM calls are never blocked or delayed by Verum. If Verum is unreachable, your service continues 100% normally.

---

## Phase 0 — Observe Only (zero code changes)

Set two environment variables and restart your service. That's it.

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://verum-production.up.railway.app/api/v1/otlp"
export OTEL_EXPORTER_OTLP_HEADERS="x-verum-api-key=<your-api-key>"
```

Verum receives OpenTelemetry spans emitted by any OpenInference-compatible library
(e.g. `openinference-instrumentation-openai`). No SDK install required; no code changes.

**What you get:**
- LLM call traces in the Verum dashboard (latency, token usage, cost)
- Domain inference (INFER stage runs automatically once enough traces are collected)
- Knowledge harvest triggered after INFER completes (HARVEST stage)

---

## Phase 1 — Bidirectional (A/B routing + prompt injection)

Add one import. Verum patches the OpenAI client so routing and prompt injection happen transparently on every call that carries the `x-verum-deployment` header.

### Python

```bash
pip install verum
```

```python
import verum.openai  # ← add this line; no other changes required

from openai import OpenAI
import os

client = OpenAI()

resp = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "..."}],
    extra_headers={"x-verum-deployment": os.environ["VERUM_DEPLOYMENT_ID"]},
)
# resp is a standard ChatCompletion — no API surface change
```

### TypeScript / Node.js

```bash
npm install @verum/sdk
```

```typescript
import "@verum/sdk/openai";  // ← add this line; no other changes required
import OpenAI from "openai";

const client = new OpenAI();

const resp = await client.chat.completions.create({
  model: "gpt-4o",
  messages: [{ role: "user", content: "..." }],
  extra_headers: { "x-verum-deployment": process.env.VERUM_DEPLOYMENT_ID! },
});
// resp is a standard ChatCompletion — no API surface change
```

### Required environment variables

| Variable | Description |
|---|---|
| `VERUM_API_URL` | Verum API base URL (e.g. `https://verum-production.up.railway.app`) |
| `VERUM_API_KEY` | Your API key |
| `VERUM_DEPLOYMENT_ID` | Deployment UUID from the Verum dashboard |

### What you get (in addition to Phase 0)

- **Prompt injection**: Verum substitutes the system prompt with the winning variant for the configured traffic split
- **A/B testing**: Traffic split is controlled from the dashboard — `traffic_split` defaults to `0%` so nothing changes until you explicitly enable it
- **Automatic OTLP export**: Spans are exported without a separate Phase 0 setup

---

## 5-Layer Safety Net

The Phase 1 SDK never blocks your LLM call. In order:

| Layer | Trigger | Behaviour |
|---|---|---|
| Hard timeout | Verum API takes > 200ms | Original messages pass through unchanged |
| Circuit breaker | 5 consecutive failures | Skips Verum for 300s, then resets |
| Fresh cache | Config fetched ≤ 60s ago | Serves from memory; no network call |
| Stale cache | Config fetched > 60s ago but ≤ 24h | Serves stale config; re-fetches in background |
| Fail-open | Any unhandled error | Original messages pass through unchanged |

---

## Migration from v0 (`verum.Client`)

If you are on the old `verum.Client.chat()` API, see [MIGRATION_v0_to_v1.md](MIGRATION_v0_to_v1.md) for a step-by-step upgrade guide.

---

## Integration Test Environment

For local end-to-end testing of the full Verum Loop stack, see [INTEGRATION_TESTS.md](INTEGRATION_TESTS.md).
