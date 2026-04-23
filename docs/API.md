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
curl https://verum.dev/api/v1/repos \
  -H "Cookie: next-auth.session-token=<jwt>"
```

**SDK / Programmatic (API Key)**

SDK endpoints authenticate via the `X-Verum-API-Key` header. The value is the deployment UUID returned by `POST /api/v1/deploy`. Requests with a missing or invalid key receive `401`.

```bash
# Example — SDK auth
curl -X POST https://verum.dev/api/v1/chat \
  -H "X-Verum-API-Key: <deployment-uuid>" \
  -H "Content-Type: application/json" \
  -d '{"messages": [...], "provider": "openai", "model": "gpt-4o"}'
```

---

## Browser Endpoints

All endpoints in this section require an Auth.js v5 JWT session. Ownership is enforced — a user can only access resources they created.

### Repos

#### `GET /api/v1/repos`

List all repositories connected by the authenticated user.

**Response `200`**

```json
{
  "repos": [
    {
      "id": "repo_abc123",
      "repo_url": "https://github.com/xzawed/ArcanaInsight",
      "status": "ready",
      "created_at": "2026-04-01T12:00:00Z"
    }
  ]
}
```

---

#### `POST /api/v1/repos`

Connect a new repository.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `repo_url` | string | yes | Full GitHub repository URL |
| `github_token` | string | yes | OAuth access token with `repo` scope |

**Response `201`**

```json
{
  "repo": {
    "id": "repo_abc123",
    "repo_url": "https://github.com/xzawed/ArcanaInsight",
    "status": "pending",
    "created_at": "2026-04-01T12:00:00Z"
  }
}
```

---

#### `DELETE /api/v1/repos/[id]`

Disconnect and delete a repository and all associated data.

**Response `200`**

```json
{ "ok": true }
```

---

### Analyze — Loop Stage 1

#### `POST /api/v1/analyze`

Enqueue an ANALYZE job for a connected repository.

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

Poll the status of an analysis job.

**Response `200`**

```json
{
  "status": "completed",
  "result": {
    "call_sites": [...],
    "prompt_templates": [...],
    "models_detected": ["gpt-4o", "claude-3-5-sonnet"]
  }
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

Poll the status of an inference job.

**Response `200`**

```json
{
  "status": "completed",
  "inference": {
    "domain": "divination/tarot",
    "tone": "mystical",
    "language": "ko",
    "user_type": "consumer"
  }
}
```

---

#### `PATCH /api/v1/infer/[id]/confirm`

Confirm or override the inferred domain/tone before proceeding to HARVEST.

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

### Harvest — Loop Stage 3

#### `POST /api/v1/harvest/propose`

Generate a list of recommended knowledge sources for a confirmed inference.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `inference_id` | string | yes | ID of a confirmed inference |

**Response `200`**

```json
{
  "sources": [
    "https://en.wikipedia.org/wiki/Tarot",
    "https://www.biddytarot.com/tarot-card-meanings/"
  ]
}
```

---

#### `POST /api/v1/harvest/start`

Enqueue a HARVEST job with the user-approved source list.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `inference_id` | string | yes | ID of the confirmed inference |
| `approved_sources` | string[] | yes | Sources selected from the proposal |

**Response `202`**

```json
{ "job_id": "job_xyz791" }
```

---

#### `POST /api/v1/retrieve`

Semantic search over harvested knowledge chunks.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | Query string |
| `collection_name` | string | yes | pgvector collection to search |
| `top_k` | integer | no | Number of results to return (default: 5) |

**Response `200`**

```json
{
  "chunks": [
    {
      "id": "chunk_001",
      "text": "The High Priestess represents intuition...",
      "score": 0.94,
      "source": "https://en.wikipedia.org/wiki/Tarot"
    }
  ]
}
```

---

### Generate — Loop Stage 4

#### `POST /api/v1/generate`

Enqueue a GENERATE job to produce prompt variants, RAG config, and eval sets.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `inference_id` | string | yes | ID of the confirmed inference |

**Response `202`**

```json
{
  "job_id": "job_xyz792",
  "generation_id": "gen_abc456"
}
```

---

#### `GET /api/v1/generate/[id]`

Poll the status of a generation job.

**Response `200`**

```json
{
  "status": "completed",
  "generation": {
    "id": "gen_abc456",
    "prompt_variants": [...],
    "rag_config": {...},
    "eval_set": [...],
    "approved": false
  }
}
```

---

#### `PATCH /api/v1/generate/[id]/approve`

Approve the generated assets, making them available for deployment.

**Response `200`**

```json
{
  "generation": {
    "id": "gen_abc456",
    "approved": true
  }
}
```

---

### Deploy — Loop Stage 5

#### `POST /api/v1/deploy`

Create a deployment from an approved generation. Returns the deployment UUID used as the SDK API key.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `generation_id` | string | yes | ID of an approved generation |

**Response `201`**

```json
{ "deployment_id": "dep_uuid_here" }
```

---

#### `POST /api/v1/deploy/[id]/traffic`

Adjust the traffic split between prompt variants in a live deployment.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `traffic_split` | object | yes | Map of `variant_name → fraction (0.0–1.0)`. Values must sum to 1.0. |

**Request example**

```json
{
  "traffic_split": {
    "baseline": 0.8,
    "challenger_cot": 0.2
  }
}
```

**Response `200`**

```json
{ "deployment": { "id": "dep_uuid_here", "traffic_split": {...} } }
```

---

#### `POST /api/v1/deploy/[id]/rollback`

Roll back a deployment to its previous traffic split configuration.

**Response `200`**

```json
{ "deployment": { "id": "dep_uuid_here", "traffic_split": {...} } }
```

---

### Observe — Loop Stage 6

#### `GET /api/v1/traces`

List traces for a deployment with pagination.

**Query parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `deployment_id` | string | yes | Filter by deployment |
| `page` | integer | no | Page number (default: 1) |
| `limit` | integer | no | Results per page (default: 50, max: 200) |

**Response `200`**

```json
{
  "traces": [
    {
      "id": "trace_001",
      "deployment_id": "dep_uuid_here",
      "variant": "baseline",
      "model": "gpt-4o",
      "input_tokens": 512,
      "output_tokens": 256,
      "cost_usd": 0.0058,
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
  "trace": { ... },
  "spans": [ ... ],
  "judge": {
    "score": 0.87,
    "rationale": "Response was accurate and on-topic."
  }
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
      "id": "exp_001",
      "deployment_id": "dep_uuid_here",
      "baseline_variant": "baseline",
      "challenger_variant": "challenger_cot",
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
  ],
  "current_experiment": "exp_001"
}
```

`status` values: `running` | `converged` | `abandoned`

---

#### `GET /api/v1/experiments/[id]`

Retrieve a single experiment.

**Response `200`**

```json
{
  "experiment": {
    "id": "exp_001",
    "deployment_id": "dep_uuid_here",
    "baseline_variant": "baseline",
    "challenger_variant": "challenger_cot",
    "status": "converged",
    "winner_variant": "challenger_cot",
    "confidence": 0.97,
    "baseline_n": 1200,
    "challenger_n": 300,
    "baseline_wins": 480,
    "challenger_wins": 198,
    "started_at": "2026-04-20T00:00:00Z",
    "converged_at": "2026-04-23T14:30:00Z"
  }
}
```

---

## SDK Endpoints

All endpoints in this section authenticate via the `X-Verum-API-Key` header. The value is the deployment UUID returned by `POST /api/v1/deploy`.

### `POST /api/v1/chat`

Route a chat request through the active deployment. Verum selects the prompt variant according to the current traffic split.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `messages` | object[] | yes | OpenAI-compatible messages array |
| `provider` | string | yes | LLM provider (`openai`, `anthropic`, `grok`) |
| `model` | string | yes | Model identifier (e.g., `gpt-4o`) |

**Response `200`**

```json
{
  "messages": [...],
  "routed_to": "challenger_cot",
  "deployment_id": "dep_uuid_here"
}
```

---

### `POST /api/v1/traces`

Record a single LLM call trace from the SDK.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `deployment_id` | string | yes | Deployment that handled this call |
| `variant` | string | yes | Prompt variant used |
| `model` | string | yes | Model identifier |
| `input_tokens` | integer | yes | Token count for the prompt |
| `output_tokens` | integer | yes | Token count for the completion |
| `latency_ms` | integer | yes | End-to-end latency in milliseconds |
| `error` | string | no | Error message if the call failed |

**Response `201`**

```json
{ "trace_id": "trace_001" }
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
| `401` | Missing or invalid credentials | `{"error": "Unauthorized"}` |
| `403` | Authenticated but not the owner of the resource | `{"error": "Forbidden"}` |
| `404` | Resource does not exist | `{"error": "Not found"}` |
| `422` | Request body failed validation | `{"error": "...", "details": {...}}` |
| `500` | Unexpected server error | `{"error": "Internal server error"}` |

### Examples

```json
// 401 — no session cookie / invalid API key
{"error": "Unauthorized"}

// 403 — repo belongs to a different user
{"error": "Forbidden"}

// 404 — analysis ID does not exist
{"error": "Not found"}

// 422 — missing required field
{
  "error": "Validation failed",
  "details": {
    "repo_url": "Required"
  }
}
```
