# Verum Python SDK

The Verum Python SDK wraps your existing LLM calls to route traffic through Verum's prompt variant system, record traces, and collect user feedback — closing the OBSERVE and EXPERIMENT stages of The Verum Loop.

## Installation

```bash
pip install verum
```

Python 3.13+ required.

## Non-Invasive Integration (Recommended)

The recommended integration uses a single `import` that monkey-patches the OpenAI SDK in-place. Your existing code requires **no other changes**.

### Phase 0 — Observe Only (Zero code changes)

Set environment variables only. No code modification required:

```bash
pip install 'verum[instrument]'
```

```env
OTEL_EXPORTER_OTLP_ENDPOINT=https://your-verum-instance/api/v1/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer YOUR_VERUM_API_KEY
VERUM_DEPLOYMENT_ID=your-deployment-uuid
```

At application startup (e.g. in `main.py` before any other imports):

```python
import verum.openai  # enables OTLP auto-instrumentation
```

### Phase 1 — Bidirectional (A/B routing + traces)

```python
import verum.openai  # ← only change

from openai import OpenAI

client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
    extra_headers={"x-verum-deployment": "your-deployment-uuid"},
)
# response is a standard OpenAI ChatCompletion object — unchanged
```

### Safety Guarantees

- **Fail-open**: If Verum is unreachable, the original call proceeds unchanged
- **200ms hard timeout**: Config fetches abort after 200ms; never blocks your LLM call
- **Circuit breaker**: After 5 failures, Verum is bypassed for 300s automatically
- **24h stale cache**: Last known good config served even during Verum outages

See [ADR-016](ARCHITECTURE.md#adr-016-no-llm-proxy--direct-call-only) (no gateway) and [ADR-017](ARCHITECTURE.md#adr-017-fail-open-sdk--5-layer-safety-net) (fail-open) for the design rationale.

---

## Legacy API (v0)

> **Note:** `verum.Client` is the v0 API. It raises `DeprecationWarning` in v1.x and will be removed in v2.0.
> See [MIGRATION_v0_to_v1.md](MIGRATION_v0_to_v1.md) for the migration guide.

## Quick Setup

Set the following environment variables before running your application:

| Variable | Description |
|---|---|
| `VERUM_API_URL` | Base URL of your Verum instance (e.g. `http://localhost:3000` or your production URL) |
| `VERUM_API_KEY` | Deployment UUID — the same value you pass as `deployment_id` in code |

```bash
export VERUM_API_URL=http://localhost:3000
export VERUM_API_KEY=<your-deployment-uuid>
```

## Client Class

```python
import verum

client = verum.Client(
    api_url="http://localhost:3000",  # optional if env var is set
    api_key="<deployment-uuid>",      # optional if env var is set
    cache_ttl=60.0,
)
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_url` | `str \| None` | `None` | Verum API base URL. Falls back to `VERUM_API_URL` env var. |
| `api_key` | `str \| None` | `None` | API key / deployment UUID. Falls back to `VERUM_API_KEY` env var. |
| `cache_ttl` | `float` | `60.0` | Seconds to cache the deployment config locally before re-fetching. |

## Method Reference

### `chat`

Routes a message list through Verum's traffic split logic. If a deployment is active, the system prompt may be replaced with the selected variant.

```python
result = await client.chat(
    messages=[{"role": "user", "content": "Hello"}],
    deployment_id="<uuid>",
    provider="openai",
    model="gpt-4o",
)
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `messages` | `list[dict[str, Any]]` | Yes | OpenAI-style message list. |
| `deployment_id` | `str \| None` | No | UUID of the active deployment. Pass `None` to bypass routing. |
| `provider` | `str` | No (default `"openai"`) | LLM provider identifier. |
| `model` | `str` | Yes | Model name (e.g. `"gpt-4o"`). |
| `**kwargs` | `Any` | No | Additional arguments forwarded to the provider. |

**Returns** `dict[str, Any]`:

| Key | Type | Description |
|---|---|---|
| `messages` | `list` | Possibly modified message list to pass to your LLM SDK. |
| `routed_to` | `str` | Variant name that was selected (e.g. `"cot"`, `"baseline"`). |
| `deployment_id` | `str \| None` | Echo of the deployment UUID, or `None` if bypassed. |

When `deployment_id` is `None`, messages pass through unchanged and `routed_to` is `"baseline"`.

---

### `retrieve`

Fetches the top-k relevant knowledge chunks from a named collection stored in pgvector.

```python
chunks = await client.retrieve(
    query="What does the Tower card mean?",
    collection_name="arcana-tarot-knowledge",
    top_k=5,
)
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | `str` | Yes | Natural-language query to embed and search. |
| `collection_name` | `str` | Yes | Name of the pgvector collection to search. |
| `top_k` | `int` | No (default `5`) | Number of chunks to return. |

**Returns** `list[dict[str, Any]]` — each dict contains at least a `"content"` key with the chunk text.

---

### `record`

Records a completed LLM call as a trace. Call this immediately after your LLM SDK returns.

```python
trace_id = await client.record(
    deployment_id="<uuid>",
    variant="cot",
    model="gpt-4o",
    input_tokens=120,
    output_tokens=45,
    latency_ms=830,
    error=None,
)
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `deployment_id` | `str` | Yes | Deployment UUID for this trace. |
| `variant` | `str` | Yes | Variant name returned by `chat` (`routed_to`). |
| `model` | `str` | Yes | Model that was called. |
| `input_tokens` | `int` | Yes | Prompt token count from the LLM response. |
| `output_tokens` | `int` | Yes | Completion token count from the LLM response. |
| `latency_ms` | `int` | Yes | Wall-clock latency in milliseconds. |
| `error` | `str \| None` | No | Error message string if the LLM call failed, otherwise `None`. |

**Returns** `str` — a UUID string identifying this trace, used with `feedback`.

---

### `feedback`

Attaches a user satisfaction score to a previously recorded trace.

```python
await client.feedback(trace_id, score=1)
```

| Parameter | Type | Description |
|---|---|---|
| `trace_id` | `str` | UUID returned by `record`. |
| `score` | `int` | `1` for positive feedback, `-1` for negative feedback. |

**Returns** `None`.

---

## Full Integration Example

```python
import asyncio
import time
import os
import verum
from openai import AsyncOpenAI

client = verum.Client()
openai_client = AsyncOpenAI()

DEPLOYMENT_ID = os.environ["VERUM_API_KEY"]

async def handle_user_message(user_input: str) -> str:
    # 1. Route through Verum (selects prompt variant based on traffic split)
    routed = await client.chat(
        messages=[{"role": "user", "content": user_input}],
        deployment_id=DEPLOYMENT_ID,
        provider="openai",
        model="gpt-4o",
    )
    # routed = {"messages": [...], "routed_to": "cot", "deployment_id": "uuid"}

    # 2. Call your LLM with the (possibly modified) messages
    t0 = time.monotonic()
    resp = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=routed["messages"],
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    reply = resp.choices[0].message.content

    # 3. Record the trace
    trace_id = await client.record(
        deployment_id=routed["deployment_id"],
        variant=routed["routed_to"],
        model="gpt-4o",
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        latency_ms=latency_ms,
    )

    # 4. Collect user feedback (optional, call after user rates response)
    await client.feedback(trace_id, score=1)

    return reply
```

## RAG Integration Example

Use `retrieve` to inject relevant knowledge chunks into the system context before routing.

```python
async def handle_with_rag(user_input: str) -> str:
    # Retrieve relevant knowledge chunks
    chunks = await client.retrieve(
        query=user_input,
        collection_name="arcana-tarot-knowledge",
        top_k=5,
    )
    context = "\n".join(c["content"] for c in chunks)

    routed = await client.chat(
        messages=[
            {"role": "system", "content": f"Context:\n{context}"},
            {"role": "user", "content": user_input},
        ],
        deployment_id=DEPLOYMENT_ID,
        provider="openai",
        model="gpt-4o",
    )
    # ... rest of flow same as the full example above
```

## Error Handling

All methods are `async` and raise standard Python exceptions on network or server errors. Wrap calls in `try/except` and pass the error string to `record` when an LLM call fails:

```python
try:
    resp = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=routed["messages"],
    )
    error_str = None
except Exception as exc:
    error_str = str(exc)
    raise
finally:
    await client.record(
        deployment_id=routed["deployment_id"],
        variant=routed["routed_to"],
        model="gpt-4o",
        input_tokens=0,
        output_tokens=0,
        latency_ms=int((time.monotonic() - t0) * 1000),
        error=error_str,
    )
```

Recording errors lets Verum's EXPERIMENT stage account for failure rates when comparing variants.
