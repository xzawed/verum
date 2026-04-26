# packages/sdk-typescript

The Verum TypeScript SDK — `npm install @verum/sdk`.

## Quick Start

```typescript
// Install
npm install @verum/sdk

// 1-line integration
import "@verum/sdk/openai";  // patches OpenAI client — no other changes required

import OpenAI from "openai";

const client = new OpenAI();
const resp = await client.chat.completions.create({
  model: "gpt-4o",
  messages: [{ role: "user", content: "..." }],
  extra_headers: { "x-verum-deployment": process.env.VERUM_DEPLOYMENT_ID! },
});
```

That's it. Verum intercepts the call, records the trace, and applies any active prompt variant or RAG context — all without modifying your existing OpenAI code.

**Fail-open guarantee**: If Verum is unreachable, your LLM calls proceed normally — Verum never blocks production traffic.

## How it works

`import "@verum/sdk/openai"` monkey-patches the OpenAI client at import time. Every subsequent `chat.completions.create()` call is wrapped with a 5-layer safety net:

1. **Circuit breaker** — opens after 5 consecutive Verum failures
2. **Timeout** — Verum side-channel has a hard 200 ms budget
3. **Async fire-and-forget** — trace export never adds latency to your response
4. **Fallback passthrough** — any exception inside Verum is caught and swallowed
5. **Feature flag** — set `VERUM_DISABLED=true` to bypass Verum entirely

## Configuration

```typescript
// Via environment variables
process.env.VERUM_API_KEY = "...";         // required
process.env.VERUM_DEPLOYMENT_ID = "...";  // required — identifies the call site
process.env.VERUM_ENDPOINT = "https://..."; // optional, defaults to verum.dev
```

Or pass via `extra_headers` per-call as shown above.

## User feedback

```typescript
import { feedback } from "@verum/sdk";

await feedback({ traceId: resp.id, score: 1 });   // thumbs up
await feedback({ traceId: resp.id, score: -1 });  // thumbs down
```

## RAG retrieval

```typescript
import { retrieve } from "@verum/sdk";

const chunks = await retrieve({
  query: "...",
  collection: "arcana-tarot-knowledge",
  topK: 5,
});
```

---

## Legacy / v0 API (deprecated)

> **Deprecated.** The wrapper API below is kept for backward compatibility but will be removed in v1.0. Migrate to the `import "@verum/sdk/openai"` pattern above.

```typescript
import { Verum } from "@verum/sdk";

const verum = new Verum({ apiKey: "...", projectId: "..." });

const response = await verum.chat({
  model: "grok-2-1212",
  messages: [...],
  deploymentId: "...",
});
```

See [docs/ARCHITECTURE.md §6](../../docs/ARCHITECTURE.md#6-sdk-surface) for the full SDK surface.
