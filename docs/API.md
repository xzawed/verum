# Verum — API Reference

All endpoints are served by the Next.js application. The base URL for all `/api/v1/...` paths is the root of your Verum instance (e.g., `https://verum.dev`).

---

## Overview

### Authentication Modes

Verum uses two distinct authentication schemes depending on the caller.

**Browser / Dashboard (Auth.js v5 JWT session)**

Requests originating from the Verum dashboard are authenticated via GitHub OAuth. Auth.js sets an HTTP-only session cookie after the OAuth flow completes. All browser-facing endpoints require a valid session; unauthenticated requests receive `401`.

```bash
# Example — browser auth (cookie set automatically after GitHub OAuth)
curl https://verum.dev/api/v1/analyze \
  -H "Cookie: next-auth.session-token=<jwt>" \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "<uuid>"}'
```

**SDK / Programmatic (API Key)**

SDK endpoints authenticate via the `X-Verum-API-Key` header. The API key is a cryptographic token (32 random bytes, URL-safe base64) generated when a deployment is created. It is shown once in the dashboard after deployment creation. Requests with a missing or invalid key receive `401`.

```bash
# Example — SDK auth
curl -X POST https://verum.dev/api/v1/traces \
  -H "X-Verum-API-Key: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{"variant": "baseline", "model": "gpt-4o", ...}'
```

---

## Browser Endpoints

All endpoints in this section require an Auth.js v5 JWT session. Ownership is enforced — a user can only access resources they created.

> **Note:** Repository management (connecting/disconnecting repos) is handled through the Verum dashboard UI via GitHub OAuth, not via REST API endpoints.

---

### Analyze — Loop Stage 1

#### `POST /api/v1/analyze`

Enqueue an ANALYZE job for a connected repository. The ANALYZE → INFER → HARVEST pipeline starts automatically on completion.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `repo_id` | string | yes | ID of a connected repo |

**Response `202`**

```json
{ "job_id": "job_xyz789" }
```

---

#### `GET /api/v1/analyze/[id]`

Poll the status of an analysis by its analysis ID.

**Response `200`**

```json
{
  "id": "uuid",
  "status": "completed",
  "call_sites": [...],
  "prompt_templates": [...],
  "model_configs": [...]
}
```

`status` values: `pending` | `running` | `completed` | `failed`

---

### Infer — Loop Stage 2

#### `POST /api/v1/infer`

Enqueue an INFER job from a completed analysis.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `analysis_id` | string | yes | ID of a completed analysis |

**Response `202`**

```json
{ "job_id": "job_xyz790" }
```

---

#### `GET /api/v1/infer/[id]`

Poll the status of an inference by its inference ID.

**Response `200`**

```json
{
  "id": "uuid",
  "status": "completed",
  "domain": "divination/tarot",
  "tone": "mystical",
  "language": "ko",
  "user_type": "consumer",
  "confidence": 0.92
}
```

---

#### `PATCH /api/v1/infer/[id]/confirm`

Confirm or override the inferred domain/tone, then trigger the HARVEST stage.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `domain` | string | no | Override inferred domain |
| `tone` | string | no | Override inferred tone |

**Response `200`**

```json
{
  "inference": {
    "domain": "divination/tarot",
    "tone": "mystical",
    "language": "ko",
    "user_type": "consumer"
  }
}
```

---

### Generate — Loop Stage 4

#### `POST /api/v1/generate`

Enqueue a GENERATE job to produce prompt variants, RAG config, and eval pairs from a confirmed inference.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `inference_id` | string | yes | ID of a confirmed inference |

**Response `202`**

```json
{ "job_id": "job_xyz792" }
```

---

#### `GET /api/v1/generate/[id]`

Poll the status of a generation by its generation ID.

**Response `200`**

```json
{
  "id": "uuid",
  "status": "completed",
  "metric_profile": {...},
  "prompt_variants": [...],
  "rag_config": {...},
  "eval_pairs": [...],
  "approved": false
}
```

---

#### `PATCH /api/v1/generate/[id]/approve`

Approve the generated assets, making them available for deployment.

**Response `200`**

```json
{
  "generation": {
    "id": "uuid",
    "status": "approved"
  }
}
```

---

### Deploy — Loop Stage 5

#### `POST /api/v1/deploy`

Enqueue a DEPLOY job from an approved generation. After the job completes, poll `GET /api/v1/deploy/[id]` to retrieve the deployment details and API key.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `generation_id` | string | yes | ID of an approved generation |

**Response `202`**

```json
{ "job_id": "job_xyz793" }
```

---

#### `GET /api/v1/deploy/[id]`

Retrieve a deployment by its ID. After a successful DEPLOY job, the `api_key` field contains the cryptographic token to use with the SDK.

**Response `200`**

```json
{
  "id": "uuid",
  "status": "canary",
  "traffic_split": { "baseline": 0.9, "variant": 0.1 },
  "experiment_status": "idle",
  "current_baseline_variant": "original",
  "created_at": "2026-04-23T09:00:00Z"
}
```

> **Note:** The `api_key` plain-text token is stored only in the dashboard at deployment creation time (never returned via API after that point). Copy it from the dashboard UI immediately after deployment.

---

#### `GET /api/v1/deploy/[id]/config`

Fetch the current deployment config for SDK routing. Authenticated with `X-Verum-API-Key` — returns only the config for the deployment that matches the API key.

**Auth:** `X-Verum-API-Key` (SDK key auth)

**Response `200`**

```json
{
  "deployment_id": "uuid",
  "status": "canary",
  "traffic_split": 0.1,
  "variant_prompt": "Think step by step before answering. ..."
}
```

---

#### `POST /api/v1/deploy/[id]/traffic`

Adjust the traffic split between prompt variants in a live deployment.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `traffic_split` | object | yes | `{ "variant": fraction }` where fraction is 0.0–1.0 |

**Request example**

```json
{ "traffic_split": { "variant": 0.2 } }
```

**Response `200`**

```json
{ "deployment": { "id": "uuid", "traffic_split": {...} } }
```

---

#### `POST /api/v1/deploy/[id]/rollback`

Roll back a deployment to 0% variant traffic (full baseline).

**Response `200`**

```json
{ "deployment": { "id": "uuid", "traffic_split": {...} } }
```

---

### Observe — Loop Stage 6

#### `GET /api/v1/traces`

List traces for a deployment with pagination.

**Auth:** Auth.js session (browser)

**Query parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `deployment_id` | string | yes | Filter by deployment |
| `page` | integer | no | Page number (default: 1) |
| `limit` | integer | no | Results per page (default: 20, max: 200) |

**Response `200`**

```json
{
  "traces": [
    {
      "id": "uuid",
      "deployment_id": "uuid",
      "variant": "baseline",
      "model": "gpt-4o",
      "input_tokens": 512,
      "output_tokens": 256,
      "cost_usd": "0.005800",
      "latency_ms": 1340,
      "judge_score": 0.87,
      "created_at": "2026-04-23T09:00:00Z"
    }
  ],
  "total": 1423
}
```

---

#### `GET /api/v1/traces/[id]`

Retrieve a single trace with all spans and LLM-as-Judge evaluation.

**Response `200`**

```json
{
  "id": "uuid",
  "variant": "baseline",
  "judge_score": 0.87,
  "judge_raw_response": "{\"reason\": \"Response was accurate.\"}",
  "latency_ms": 1340,
  "cost_usd": "0.005800",
  "model": "gpt-4o",
  "input_tokens": 512,
  "output_tokens": 256,
  "error": null,
  "created_at": "2026-04-23T09:00:00Z"
}
```

---

#### `GET /api/v1/metrics`

Retrieve aggregated daily metrics for a deployment.

**Query parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `deployment_id` | string | yes | Target deployment |
| `days` | integer | no | Lookback window in days (default: 7) |

**Response `200`**

```json
{
  "daily": [
    {
      "date": "2026-04-23",
      "variant": "baseline",
      "call_count": 342,
      "avg_cost_usd": 0.0061,
      "avg_latency_ms": 1280,
      "avg_judge_score": 0.84
    }
  ]
}
```

---

### Experiment — Loop Stage 7

#### `GET /api/v1/experiments`

List experiments for a deployment.

**Query parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `deployment_id` | string | yes | Target deployment |

**Response `200`**

```json
{
  "experiments": [
    {
      "id": "uuid",
      "deployment_id": "uuid",
      "baseline_variant": "original",
      "challenger_variant": "cot",
      "status": "running",
      "winner_variant": null,
      "confidence": null,
      "baseline_n": 480,
      "challenger_n": 120,
      "baseline_wins": 210,
      "challenger_wins": 98,
      "started_at": "2026-04-20T00:00:00Z",
      "converged_at": null
    }
  ]
}
```

`status` values: `running` | `converged` | `abandoned`

---

#### `GET /api/v1/experiments/[id]`

Retrieve a single experiment.

**Response `200`**

```json
{
  "id": "uuid",
  "deployment_id": "uuid",
  "baseline_variant": "original",
  "challenger_variant": "cot",
  "status": "converged",
  "winner_variant": "cot",
  "confidence": 0.97,
  "baseline_n": 1200,
  "challenger_n": 300,
  "baseline_wins": 480,
  "challenger_wins": 198,
  "started_at": "2026-04-20T00:00:00Z",
  "converged_at": "2026-04-23T14:30:00Z"
}
```

---

### Quota

#### `GET /api/v1/quota`

Retrieve the authenticated user's current usage quota for the billing period.

**Response `200`**

```json
{
  "plan": "free",
  "period": "2026-04-01",
  "limits": {
    "traces": 1000,
    "chunks": 10000,
    "repos": 3
  },
  "used": {
    "traces": 248,
    "chunks": 3120,
    "repos": 1
  }
}
```

Override free-tier limits via environment variables: `VERUM_FREE_TRACES`, `VERUM_FREE_CHUNKS`, `VERUM_FREE_REPOS`.

---

## SDK Endpoints

All endpoints in this section authenticate via the `X-Verum-API-Key` header. The value is the cryptographic API key issued at deployment creation time.

### `POST /api/v1/traces`

Record a single LLM call trace from the SDK.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `deployment_id` | string | yes | Deployment that handled this call |
| `variant` | string | yes | Prompt variant used (`"baseline"` or `"variant"`) |
| `model` | string | yes | Model identifier |
| `input_tokens` | integer | yes | Token count for the prompt |
| `output_tokens` | integer | yes | Token count for the completion |
| `latency_ms` | integer | yes | End-to-end latency in milliseconds |
| `error` | string | no | Error message if the call failed |

**Response `201`**

```json
{ "trace_id": "uuid" }
```

**Response `429`** — quota exceeded (free tier limit reached):

```json
"quota exceeded"
```

---

### `POST /api/v1/feedback`

Submit a user feedback signal (thumbs up/down) for a recorded trace.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trace_id` | string | yes | ID of the trace being rated |
| `score` | number | yes | `1` for positive, `-1` for negative |

**Response `200`**

```json
{ "ok": true }
```

---

### `POST /api/v1/retrieve-sdk`

Semantic search over harvested knowledge chunks. Used internally by the `retrieve()` SDK method.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | Natural-language query string |
| `collection_name` | string | no | Ignored currently; searches all chunks for the deployment's inference |
| `top_k` | integer | no | Number of results to return (default: 5, max: 20) |

**Response `200`**

```json
{
  "chunks": [
    {
      "content": "The High Priestess represents intuition and mystery...",
      "score": 0.94,
      "metadata": { "source": "https://en.wikipedia.org/wiki/Tarot" }
    }
  ]
}
```

> **Note:** This endpoint embeds the query using `text-embedding-3-small` and performs pgvector cosine similarity search. Requires `OPENAI_API_KEY` to be set.

---

## Health

### `GET /health`

No authentication required. Returns the current health status of the Verum instance.

**Response `200`**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "db": "connected"
}
```

This endpoint is excluded from the Auth.js middleware matcher so that Railway and other orchestrators can probe it without a session cookie.

---

## Error Codes

All error responses use `application/json` with a consistent shape.

| HTTP Status | Meaning | Response body |
|-------------|---------|---------------|
| `400` | Missing or invalid request body field | Plain text description |
| `401` | Missing or invalid credentials | Plain text `"unauthorized"` |
| `403` | Authenticated but not the owner of the resource | Plain text `"forbidden"` |
| `404` | Resource does not exist | Plain text `"not found"` |
| `409` | Conflict (e.g., generation not yet approved) | Plain text description |
| `429` | Free-tier quota exceeded | Plain text `"quota exceeded"` |
| `500` | Unexpected server error | Plain text or JSON |
