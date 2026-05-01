# Verum TypeScript SDK

The Verum TypeScript SDK wraps your existing LLM calls to route traffic through Verum's prompt variant system, record traces, and collect user feedback — closing the OBSERVE and EXPERIMENT stages of The Verum Loop.

## Installation

```bash
npm install @verum/sdk
# or
yarn add @verum/sdk
```

Node.js 18+ required.

## Non-Invasive Integration (Recommended)

The recommended integration uses a single `import` that monkey-patches the OpenAI SDK in-place. Your existing code requires **no other changes**.

### Tier 0 — Zero Code Changes

`@verum/sdk` exports an `auto` entry point (`@verum/sdk/auto`) that checks environment variables and conditionally patches OpenAI and Anthropic clients. Load it via `NODE_OPTIONS` — no code changes to your application.

**Setup:**

```bash
npm install @verum/sdk
```

Set environment variables:

```env
VERUM_API_URL=https://your-verum-instance
VERUM_API_KEY=your-key
NODE_OPTIONS=--require @verum/sdk/auto
```

Or inline when starting your service:

```bash
NODE_OPTIONS="--require @verum/sdk/auto" \
VERUM_API_URL="https://your-verum-instance" \
VERUM_API_KEY="your-key" \
node your-service.js
```

All OpenAI and Anthropic clients are patched at Node.js startup — before any application module runs.

**To disable auto-patching:**

```bash
export VERUM_DISABLED=1
```

`VERUM_DISABLED=true` and `VERUM_DISABLED=yes` also work.

**Notes:**

- If `openai` or `anthropic` packages are not installed, the patch for that provider is silently skipped — no error is raised
- `VERUM_API_URL` and `VERUM_API_KEY` must both be set; if either is absent, auto-patching is skipped
- For Docker-based deployments, add `NODE_OPTIONS` to the container's environment alongside the other `VERUM_*` variables

---

### Tier 1 — Observe Only (one-line import)

Set environment variables and add a single import at application startup. No other code modification required:

```env
OTEL_EXPORTER_OTLP_ENDPOINT=https://your-verum-instance/api/v1/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer YOUR_VERUM_API_KEY
VERUM_DEPLOYMENT_ID=your-deployment-uuid
```

At application startup (e.g. in your entry file before any other imports):

```typescript
import "@verum/sdk/openai"; // enables auto-instrumentation
```

### Tier 2 — Bidirectional (A/B routing + traces)

```typescript
import "@verum/sdk/openai"; // ← only change
import OpenAI from "openai";

const client = new OpenAI();

const resp = await client.chat.completions.create({
  model: "grok-2-1212",
  messages: [{ role: "user", content: "Hello" }],
  // @ts-ignore — extra_headers is valid in openai SDK but types may lag
  extra_headers: { "x-verum-deployment": process.env.VERUM_DEPLOYMENT_ID },
});
// resp is a standard OpenAI ChatCompletion object — unchanged
```

The patch intercepts `client.chat.completions.create` at the prototype level. The `x-verum-deployment` header is read by the patch and stripped before the request is forwarded to OpenAI, so it never reaches the upstream API.

### 5-Layer Safety Net

The auto-instrument patch is designed to be completely invisible when Verum is unavailable. The following guarantees apply unconditionally:

| Layer | Behaviour |
|---|---|
| **1. 200ms hard timeout** | Config fetches abort after 200ms. Your LLM call always proceeds with the original messages on timeout. |
| **2. Circuit breaker** | After 5 consecutive failures, Verum is bypassed for 300s automatically. No further fetch attempts during cooldown. |
| **3. Fresh cache** | Deployment config is cached for 60s (default). Cache TTL is configurable via environment or options. |
| **4. Stale-while-revalidate** | The last known good config is served for up to 24h even after the fresh TTL expires, so a Verum outage does not affect your service. |
| **5. Fail-open** | Any unhandled error — network failure, unexpected exception, invalid response — causes the original messages to pass through completely unchanged. |

See [ADR-016](ARCHITECTURE.md#adr-016-no-llm-proxy--direct-call-only) (no gateway) and [ADR-017](ARCHITECTURE.md#adr-017-fail-open-sdk--5-layer-safety-net) (fail-open) for the design rationale.

---

## Environment Variables

| Variable | Description |
|---|---|
| `VERUM_API_URL` | Base URL of your Verum instance (e.g. `http://localhost:3000` or your production URL) |
| `VERUM_API_KEY` | Cryptographic API key — issued when a deployment is created and shown once in the dashboard |
| `VERUM_DEPLOYMENT_ID` | Deployment UUID — passed via `extra_headers` or read from env when not provided inline |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Optional. For Phase 0 OTLP-only mode, point to your Verum instance's OTLP receiver |

```bash
export VERUM_API_URL=http://localhost:3000
export VERUM_API_KEY=<your-api-key>
export VERUM_DEPLOYMENT_ID=<your-deployment-uuid>
```

---

## RAG Integration Example

Use `retrieve` to inject relevant knowledge chunks into the system context before routing.

```typescript
import "@verum/sdk/openai";
import { VerumClient } from "@verum/sdk";
import OpenAI from "openai";

const verum = new VerumClient();
const openai = new OpenAI();

export async function handleWithRag(userInput: string): Promise<string> {
  // Retrieve relevant knowledge chunks
  const chunks = await verum.retrieve({
    query: userInput,
    collectionName: "arcana-tarot-knowledge",
    topK: 5,
  });
  const context = chunks.map((c) => c.content).join("\n");

  const resp = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [
      { role: "system", content: `Context:\n${context}` },
      { role: "user", content: userInput },
    ],
    // @ts-ignore
    extra_headers: { "x-verum-deployment": process.env.VERUM_DEPLOYMENT_ID },
  });
  return resp.choices[0].message.content ?? "";
}
```

---

## Error Handling

The auto-instrument patch never throws. If any error occurs during config resolution, the original messages pass through and the LLM call proceeds normally.

If you use the legacy `VerumClient` API directly, all methods return Promises and throw standard errors on network or server failures. Wrap LLM calls in `try/catch` and pass the error string to `record` so that Verum's EXPERIMENT stage can account for error rates when comparing variants.

```typescript
let errorStr: string | null = null;
const start = Date.now();

try {
  const resp = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: routed.messages,
  });
  // handle success...
} catch (err) {
  errorStr = err instanceof Error ? err.message : String(err);
  throw err;
} finally {
  await verum.record({
    deploymentId: DEPLOYMENT_ID,
    variant: routed.routed_to,
    model: "gpt-4o",
    inputTokens: 0,
    outputTokens: 0,
    latencyMs: Date.now() - start,
    error: errorStr,
  });
}
```

---

## Legacy / v0 API

> ⚠️ **Deprecated.** `VerumClient` is deprecated as of v1.0. Migrate to `import "@verum/sdk/openai"`. See [MIGRATION_v0_to_v1.md](MIGRATION_v0_to_v1.md).

The `VerumClient` class is preserved for backwards compatibility. It provides explicit `chat`, `retrieve`, `record`, and `feedback` methods that require manual instrumentation of every LLM call site.

### Client Class

```typescript
import { VerumClient } from "@verum/sdk";

const client = new VerumClient({
  apiUrl: "http://localhost:3000", // optional if env var is set
  apiKey: "<your-api-key>",        // optional if env var is set
  cacheTtlMs: 60_000,              // milliseconds; default 60 000 (1 minute)
  timeoutMs: 10_000,               // milliseconds; default 10 000 (10 seconds)
});
```

### Constructor Options

| Option | Type | Default | Description |
|---|---|---|---|
| `apiUrl` | `string \| undefined` | `undefined` | Verum API base URL. Falls back to `VERUM_API_URL` env var. |
| `apiKey` | `string \| undefined` | `undefined` | Cryptographic API key. Falls back to `VERUM_API_KEY` env var. |
| `cacheTtlMs` | `number` | `60_000` | Milliseconds to cache the deployment config locally before re-fetching. |
| `timeoutMs` | `number` | `10_000` | Milliseconds before a Verum API call is aborted. |

### Method Reference

#### `chat`

Routes a message list through Verum's traffic split logic. If a deployment is active, the system prompt may be replaced with the selected variant. The method returns a modified message array — pass it directly to your LLM SDK.

```typescript
const result = await client.chat({
  messages: [{ role: "user", content: "Hello" }],
  deploymentId: "<uuid>",
  provider: "openai",
  model: "gpt-4o",
});
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `messages` | `Array<{ role: string; content: string }>` | Yes | OpenAI-style message array. |
| `deploymentId` | `string \| undefined` | No | UUID of the active deployment. Omit to bypass routing. |
| `provider` | `string` | No (default `"openai"`) | LLM provider identifier. |
| `model` | `string` | Yes | Model name (e.g. `"gpt-4o"`). |

**Returns** `Promise<ChatResult>`:

| Key | Type | Description |
|---|---|---|
| `messages` | `Array<{ role: string; content: string }>` | Possibly modified message array to pass to your LLM SDK. |
| `routed_to` | `"variant" \| "baseline"` | Which variant was selected. |
| `deployment_id` | `string \| null` | Echo of the deployment UUID, or `null` if bypassed. |

When `deploymentId` is omitted, messages pass through unchanged and `routed_to` is `"baseline"`.

---

#### `retrieve`

Fetches the top-k relevant knowledge chunks from a named collection stored in pgvector.

```typescript
const chunks = await client.retrieve({
  query: "What does the Tower card mean?",
  collectionName: "arcana-tarot-knowledge",
  topK: 5,
});
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | Yes | Natural-language query to embed and search. |
| `collectionName` | `string` | Yes | Name of the pgvector collection to search. |
| `topK` | `number` | No (default `5`) | Number of chunks to return. |

**Returns** `Promise<Chunk[]>` — each object contains at least a `content` string key with the chunk text, plus optional metadata fields.

---

#### `record`

Records a completed LLM call as a trace. Call this immediately after your LLM SDK returns.

```typescript
const traceId = await client.record({
  deploymentId: "<uuid>",
  variant: "variant",
  model: "gpt-4o",
  inputTokens: 120,
  outputTokens: 45,
  latencyMs: 830,
  error: null,
});
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `deploymentId` | `string` | Yes | Deployment UUID for this trace. |
| `variant` | `string` | Yes | Variant name returned by `chat` (`routed_to`). |
| `model` | `string` | Yes | Model that was called. |
| `inputTokens` | `number` | Yes | Prompt token count from the LLM response. |
| `outputTokens` | `number` | Yes | Completion token count from the LLM response. |
| `latencyMs` | `number` | Yes | Wall-clock latency in milliseconds. |
| `error` | `string \| null` | No | Error message string if the LLM call failed, otherwise `null`. |

**Returns** `Promise<string>` — a UUID string identifying this trace, used with `feedback`.

---

#### `feedback`

Attaches a user satisfaction score to a previously recorded trace.

```typescript
await client.feedback({ traceId, score: 1 });
```

| Parameter | Type | Description |
|---|---|---|
| `traceId` | `string` | UUID returned by `record`. |
| `score` | `1 \| -1` | `1` for positive feedback, `-1` for negative feedback. |

**Returns** `Promise<void>`.

---

### Full Integration Example (Node.js)

```typescript
import { VerumClient } from "@verum/sdk";
import OpenAI from "openai";

const verum = new VerumClient();
const openai = new OpenAI();

const DEPLOYMENT_ID = process.env.VERUM_DEPLOYMENT_ID!;

export async function handleUserMessage(userInput: string): Promise<string> {
  // 1. Route through Verum (selects prompt variant based on traffic split)
  const routed = await verum.chat({
    messages: [{ role: "user", content: userInput }],
    deploymentId: DEPLOYMENT_ID,
    provider: "openai",
    model: "gpt-4o",
  });
  // routed = { messages: [...], routed_to: "variant", deployment_id: "uuid" }

  // 2. Call your LLM with the (possibly modified) messages
  const start = Date.now();
  const resp = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: routed.messages,
  });
  const latencyMs = Date.now() - start;
  const reply = resp.choices[0].message.content ?? "";

  // 3. Record the trace
  const traceId = await verum.record({
    deploymentId: DEPLOYMENT_ID,
    variant: routed.routed_to,
    model: "gpt-4o",
    inputTokens: resp.usage?.prompt_tokens ?? 0,
    outputTokens: resp.usage?.completion_tokens ?? 0,
    latencyMs,
  });

  // 4. Collect user feedback (optional, call after user rates response)
  await verum.feedback({ traceId, score: 1 });

  return reply;
}
```

### Next.js API Route Example

```typescript
// app/api/chat/route.ts
import { NextRequest, NextResponse } from "next/server";
import { VerumClient } from "@verum/sdk";
import OpenAI from "openai";

const verum = new VerumClient();
const openai = new OpenAI();

const DEPLOYMENT_ID = process.env.VERUM_DEPLOYMENT_ID!;

export async function POST(req: NextRequest) {
  const { message } = await req.json();

  const routed = await verum.chat({
    messages: [{ role: "user", content: message }],
    deploymentId: DEPLOYMENT_ID,
    provider: "openai",
    model: "gpt-4o",
  });

  const start = Date.now();
  const resp = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: routed.messages,
  });
  const latencyMs = Date.now() - start;
  const reply = resp.choices[0].message.content ?? "";

  const traceId = await verum.record({
    deploymentId: DEPLOYMENT_ID,
    variant: routed.routed_to,
    model: "gpt-4o",
    inputTokens: resp.usage?.prompt_tokens ?? 0,
    outputTokens: resp.usage?.completion_tokens ?? 0,
    latencyMs,
  });

  return NextResponse.json({ reply, traceId });
}
```

---

> **Note**: TypeScript uses camelCase parameter names (`deploymentId`, `inputTokens`, `collectionName`, `topK`, `cacheTtlMs`, `timeoutMs`) while the Python SDK uses snake_case equivalents (`deployment_id`, `input_tokens`, `collection_name`, `top_k`, `cache_ttl`, `timeout_ms`). The underlying REST API and behaviour are identical.
