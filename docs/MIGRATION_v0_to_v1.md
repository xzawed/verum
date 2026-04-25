# Migration: verum.Client → import verum.openai

## v0 API (deprecated)

```python
import verum

client = verum.Client(api_url=..., api_key=...)
result = await client.chat(messages, deployment_id=DEPLOYMENT_ID, model="gpt-4o")
# result["messages"] contains modified messages — you must pass them to OpenAI yourself
```

## v1 API (recommended)

```python
import verum.openai  # ← replaces all of the above

from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    extra_headers={"x-verum-deployment": os.environ["VERUM_DEPLOYMENT_ID"]},
)
# response is a standard OpenAI ChatCompletion — use as before
```

## Key differences

| | v0 (`verum.Client`) | v1 (`import verum.openai`) |
|---|---|---|
| Actual LLM call | You must call OpenAI yourself after `client.chat()` | Handled automatically inside the patched `create()` |
| Fail-open | Raises exception if Verum is down | Passthrough, never blocks |
| Response type | `dict` with Verum fields | Standard `ChatCompletion` |
| Async required | Must `await client.chat()` | Works sync and async |
| Circuit breaker | No | Yes — 5 failures → 300s bypass |
| 24h stale cache | No | Yes — last known config served during outages |
| Manual `record()` call | Required | Automatic via OTLP export |

## Step-by-step migration

### 1. Install the instrumentation extra

```bash
pip install 'verum[instrument]'
```

### 2. Set environment variables

Replace `VERUM_API_KEY` (deployment UUID) with the new variable names:

```env
# Before (v0)
VERUM_API_URL=https://your-verum-instance
VERUM_API_KEY=<deployment-uuid>

# After (v1)
OTEL_EXPORTER_OTLP_ENDPOINT=https://your-verum-instance/api/v1/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer YOUR_VERUM_API_KEY
VERUM_DEPLOYMENT_ID=<deployment-uuid>
```

### 3. Replace the import and remove boilerplate

```python
# Before (v0)
import verum
client = verum.Client()

async def handle(user_input: str) -> str:
    routed = await client.chat(
        messages=[{"role": "user", "content": user_input}],
        deployment_id=DEPLOYMENT_ID,
        model="gpt-4o",
    )
    t0 = time.monotonic()
    resp = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=routed["messages"],
    )
    await client.record(
        deployment_id=routed["deployment_id"],
        variant=routed["routed_to"],
        model="gpt-4o",
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        latency_ms=int((time.monotonic() - t0) * 1000),
    )
    return resp.choices[0].message.content
```

```python
# After (v1)
import verum.openai  # ← add this at the top of your entrypoint file

async def handle(user_input: str) -> str:
    resp = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": user_input}],
        extra_headers={"x-verum-deployment": os.environ["VERUM_DEPLOYMENT_ID"]},
    )
    return resp.choices[0].message.content
```

Tracing, variant routing, and cost recording happen automatically. The `client.record()` call is no longer needed.

### 4. Feedback (optional)

If you were collecting user feedback with `client.feedback(trace_id, score)`, the `trace_id` is now available from the response span context:

```python
import verum.openai
from verum.openai import get_last_trace_id

resp = client.chat.completions.create(...)
trace_id = get_last_trace_id()  # returns trace ID of the most recent call

# later, when user rates the response:
await verum_client.feedback(trace_id, score=1)
```

## Deprecation timeline

| Version | Status |
|---|---|
| v1.x | `verum.Client.chat()` emits `DeprecationWarning` |
| v2.0 | `verum.Client` removed entirely |

## See also

- [SDK_PYTHON.md](SDK_PYTHON.md) — full v1 API reference
- [ADR-016](ARCHITECTURE.md#adr-016-no-llm-proxy--direct-call-only) — why no gateway proxy
- [ADR-017](ARCHITECTURE.md#adr-017-fail-open-sdk--5-layer-safety-net) — fail-open 5-layer safety net
