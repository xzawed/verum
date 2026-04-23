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
| `VERUM_API_KEY` | Deployment UUID — the same value you pass as `deploymentId` in code |

```bash
export VERUM_API_URL=http://localhost:3000
export VERUM_API_KEY=<your-deployment-uuid>
```

## Client Class

```typescript
import { Client } from "@verum/sdk";

const client = new Client({
  apiUrl: "http://localhost:3000", // optional if env var is set
  apiKey: "<deployment-uuid>",     // optional if env var is set
  cacheTtl: 60,
});
```

### Constructor Options

| Option | Type | Default | Description |
|---|---|---|---|
| `apiUrl` | `string \| undefined` | `undefined` | Verum API base URL. Falls back to `VERUM_API_URL` env var. |
| `apiKey` | `string \| undefined` | `undefined` | API key / deployment UUID. Falls back to `VERUM_API_KEY` env var. |
| `cacheTtl` | `number` | `60` | Seconds to cache the deployment config locally before re-fetching. |

## Method Reference

### `chat`

Routes a message list through Verum's traffic split logic. If a deployment is active, the system prompt may be replaced with the selected variant.

```typescript
const result = await client.chat(
  [{ role: "user", content: "Hello" }],
  {
    deploymentId: "<uuid>",
    provider: "openai",
    model: "gpt-4o",
  }
);
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `messages` | `Array<{ role: string; content: string }>` | Yes | OpenAI-style message array. |
| `options.deploymentId` | `string \| undefined` | No | UUID of the active deployment. Omit to bypass routing. |
| `options.provider` | `string` | No (default `"openai"`) | LLM provider identifier. |
| `options.model` | `string` | Yes | Model name (e.g. `"gpt-4o"`). |
| `options[key]` | `unknown` | No | Additional arguments forwarded to the provider. |

**Returns** `Promise<ChatResult>`:

| Key | Type | Description |
|---|---|---|
| `messages` | `Array<{ role: string; content: string }>` | Possibly modified message array to pass to your LLM SDK. |
| `routed_to` | `string` | Variant name that was selected (e.g. `"cot"`, `"baseline"`). |
| `deployment_id` | `string \| null` | Echo of the deployment UUID, or `null` if bypassed. |

When `deploymentId` is omitted, messages pass through unchanged and `routed_to` is `"baseline"`.

---

### `retrieve`

Fetches the top-k relevant knowledge chunks from a named collection stored in pgvector.

```typescript
const chunks = await client.retrieve(
  "What does the Tower card mean?",
  {
    collectionName: "arcana-tarot-knowledge",
    topK: 5,
  }
);
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | Yes | Natural-language query to embed and search. |
| `options.collectionName` | `string` | Yes | Name of the pgvector collection to search. |
| `options.topK` | `number` | No (default `5`) | Number of chunks to return. |

**Returns** `Promise<Chunk[]>` — each object contains at least a `content` string key with the chunk text, plus optional metadata fields.

---

### `record`

Records a completed LLM call as a trace. Call this immediately after your LLM SDK returns.

```typescript
const traceId = await client.record({
  deploymentId: "<uuid>",
  variant: "cot",
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
await client.feedback(traceId, 1);
```

| Parameter | Type | Description |
|---|---|---|
| `traceId` | `string` | UUID returned by `record`. |
| `score` | `1 \| -1` | `1` for positive feedback, `-1` for negative feedback. |

**Returns** `Promise<void>`.

---

## Full Integration Example (Node.js)

```typescript
import { Client } from "@verum/sdk";
import OpenAI from "openai";

const verum = new Client();
const openai = new OpenAI();

const DEPLOYMENT_ID = process.env.VERUM_API_KEY!;

export async function handleUserMessage(userInput: string): Promise<string> {
  // 1. Route through Verum (selects prompt variant based on traffic split)
  const routed = await verum.chat(
    [{ role: "user", content: userInput }],
    {
      deploymentId: DEPLOYMENT_ID,
      provider: "openai",
      model: "gpt-4o",
    }
  );
  // routed = { messages: [...], routed_to: "cot", deployment_id: "uuid" }

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
    deploymentId: routed.deployment_id!,
    variant: routed.routed_to,
    model: "gpt-4o",
    inputTokens: resp.usage?.prompt_tokens ?? 0,
    outputTokens: resp.usage?.completion_tokens ?? 0,
    latencyMs,
  });

  // 4. Collect user feedback (optional, call after user rates response)
  await verum.feedback(traceId, 1);

  return reply;
}
```

## Next.js API Route Example

```typescript
// app/api/chat/route.ts
import { NextRequest, NextResponse } from "next/server";
import { Client } from "@verum/sdk";
import OpenAI from "openai";

const verum = new Client();
const openai = new OpenAI();

export async function POST(req: NextRequest) {
  const { message } = await req.json();
  const DEPLOYMENT_ID = process.env.VERUM_API_KEY!;

  const routed = await verum.chat(
    [{ role: "user", content: message }],
    { deploymentId: DEPLOYMENT_ID, provider: "openai", model: "gpt-4o" }
  );

  const start = Date.now();
  const resp = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: routed.messages,
  });
  const latencyMs = Date.now() - start;
  const reply = resp.choices[0].message.content ?? "";

  const traceId = await verum.record({
    deploymentId: routed.deployment_id!,
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
  const chunks = await verum.retrieve(userInput, {
    collectionName: "arcana-tarot-knowledge",
    topK: 5,
  });
  const context = chunks.map((c) => c.content).join("\n");

  const routed = await verum.chat(
    [
      { role: "system", content: `Context:\n${context}` },
      { role: "user", content: userInput },
    ],
    {
      deploymentId: process.env.VERUM_API_KEY!,
      provider: "openai",
      model: "gpt-4o",
    }
  );
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
    deploymentId: routed.deployment_id!,
    variant: routed.routed_to,
    model: "gpt-4o",
    inputTokens: 0,
    outputTokens: 0,
    latencyMs: Date.now() - start,
    error: errorStr,
  });
}
```

> **Note**: TypeScript uses camelCase parameter names (`deploymentId`, `inputTokens`, `collectionName`, `topK`) while the Python SDK uses snake_case equivalents (`deployment_id`, `input_tokens`, `collection_name`, `top_k`). The underlying REST API and behaviour are identical.
