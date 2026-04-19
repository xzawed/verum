# packages/sdk-python

The Verum Python SDK — `pip install verum`.

**Status:** Phase 0 stub. The high-level API (`verum.chat()`, `verum.retrieve()`, `verum.feedback()`) ships in Phase 3 (F-3.8).

## Planned API

```python
import verum

verum.configure(api_key="...", project_id="...")

# Wrap any LLM call — OBSERVE instruments it automatically
response = await verum.chat(
    model="grok-2-1212",
    messages=[...],
    deployment_id="...",
)

# Retrieve from HARVEST knowledge base
chunks = await verum.retrieve(
    query="...",
    collection="arcana-tarot-knowledge",
    top_k=5,
)

# Record user feedback (feeds EXPERIMENT)
await verum.feedback(trace_id="...", score=1)
```

See [docs/ARCHITECTURE.md §6](../../docs/ARCHITECTURE.md#6-sdk-surface) for the full SDK surface.
