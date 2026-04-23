# Verum TypeScript SDK

The Verum TypeScript SDK wraps your existing LLM calls to route traffic through Verum's prompt variant system, record traces, and collect user feedback — closing the OBSERVE and EXPERIMENT stages of The Verum Loop.

## Installation

```bash
npm install @verum/sdk
# or
yarn add @verum/sdk
```

Node.js 18+ required.

## Quick Setup

Set the following environment variables before running your application:

| Variable | Description |
|---|---|
| `VERUM_API_URL` | Base URL of your Verum instance (e.g. `http://localhost:3000` or your production URL) |
| `VERUM_API_KEY` | Cryptographic API key — issued when a deployment is created and shown once in the dashboard |

```bash
export VERUM_API_URL=http://localhost:3000
export VERUM_API_KEY=<your-api-key>
```

## Client Class

```typescript
import { VerumClient } from "@verum/sdk";

const client = new VerumClient({
  apiUrl: "http://localhost:3000", // optional if env var is set
  apiKey: "<your-api-key>",        // optional if env var is set
  cacheTtlMs: 60_000,              // milliseconds; default 60 000 (1 minute)
});
```

### Constructor Options

| Option | Type | Default | Description |
|---|---|---|---|
| `apiUrl` | `string \| undefined` | `undefined` | Verum API base URL. Falls back to `VERUM_API_URL` env var. |
| `apiKey` | `string \| undefined` | `undefined` | Cryptographic API key. Falls back to `VERUM_API_KEY` env var. |
| `cacheTtlMs` | `number` | `60_000` | Milliseconds to cache the deployment config locally before re-fetching. |

## Method Reference

### `chat`

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

### `retrieve`

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

### `record`

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

### `feedback`

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

## Full Integration Example (Node.js)

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

## Next.js API Route Example

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

## RAG Integration Example

Use `retrieve` to inject relevant knowledge chunks into the system context before routing.

```typescript
export async function handleWithRag(userInput: string): Promise<string> {
  // Retrieve relevant knowledge chunks
  const chunks = await verum.retrieve({
    query: userInput,
    collectionName: "arcana-tarot-knowledge",
    topK: 5,
  });
  const context = chunks.map((c) => c.content).join("\n");

  const routed = await verum.chat({
    messages: [
      { role: "system", content: `Context:\n${context}` },
      { role: "user", content: userInput },
    ],
    deploymentId: DEPLOYMENT_ID,
    provider: "openai",
    model: "gpt-4o",
  });
  // ... rest of flow same as the full example above
}
```

## Error Handling

All methods return Promises and throw standard errors on network or server failures. Wrap LLM calls in `try/catch` and pass the error string to `record` when a call fails so that Verum's EXPERIMENT stage can account for error rates when comparing variants.

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

> **Note**: TypeScript uses camelCase parameter names (`deploymentId`, `inputTokens`, `collectionName`, `topK`, `cacheTtlMs`) while the Python SDK uses snake_case equivalents (`deployment_id`, `input_tokens`, `collection_name`, `top_k`, `cache_ttl_ms`). The underlying REST API and behaviour are identical.
