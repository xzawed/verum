# packages/sdk-python

The Verum Python SDK — `pip install verum`.

## Quick Start

```python
# Install
pip install verum

# 1-line integration
import verum.openai  # patches OpenAI client — no other changes required

from openai import OpenAI
import os

client = OpenAI()
resp = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "..."}],
    extra_headers={"x-verum-deployment": os.environ["VERUM_DEPLOYMENT_ID"]},
)
```

That's it. Verum intercepts the call, records the trace, and applies any active prompt variant or RAG context — all without modifying your existing OpenAI code.

**Fail-open guarantee**: If Verum is unreachable, your LLM calls proceed normally — Verum never blocks production traffic.

## How it works

`import verum.openai` monkey-patches the OpenAI client at import time. Every subsequent `chat.completions.create()` call is wrapped with a 5-layer safety net:

1. **Circuit breaker** — opens after 3 consecutive Verum failures
2. **Timeout** — Verum side-channel has a hard 200 ms budget
3. **Async fire-and-forget** — trace export never adds latency to your response
4. **Fallback passthrough** — any exception inside Verum is caught and swallowed
5. **Feature flag** — set `VERUM_DISABLED=true` to bypass Verum entirely

## Configuration

```python
import os

os.environ["VERUM_API_KEY"] = "..."          # required
os.environ["VERUM_DEPLOYMENT_ID"] = "..."    # required — identifies the call site
os.environ["VERUM_ENDPOINT"] = "https://..."  # optional, defaults to verum.dev
```

Or pass via `extra_headers` per-call as shown above.

## User feedback

```python
import verum

await verum.feedback(trace_id=resp.id, score=1)   # thumbs up
await verum.feedback(trace_id=resp.id, score=-1)  # thumbs down
```

## RAG retrieval

```python
chunks = await verum.retrieve(
    query="...",
    collection="arcana-tarot-knowledge",
    top_k=5,
)
```

---

## Legacy / v0 API (deprecated)

> **Deprecated.** The wrapper API below is kept for backward compatibility but will be removed in v1.0. Migrate to the `import verum.openai` pattern above.

```python
import verum

verum.configure(api_key="...", project_id="...")

response = await verum.chat(
    model="grok-2-1212",
    messages=[...],
    deployment_id="...",
)
```

See [docs/ARCHITECTURE.md §6](../../docs/ARCHITECTURE.md#6-sdk-surface) for the full SDK surface.
