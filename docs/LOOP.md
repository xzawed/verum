---
type: loop
authority: tier-2
canonical-for: [stage-algorithms, stage-io, loop-invariants, completion-criteria]
last-updated: 2026-04-22
status: active
---

# Verum Loop — Stage Reference

> **Claude instructions:** This is the sole canonical reference for the 8-stage loop algorithms.
> CLAUDE.md owns the loop *definition and rationale*; this file owns the *implementation detail*.
> Every `apps/api/src/loop/<stage>/` module is the code implementation of a section here.
> When adding logic to a stage module, its behavior must be describable with the I/O contracts below.
> Authority: CLAUDE.md > this file > all other docs.

---

## 1. Loop Overview

```
  ┌─────────────────────────────────────────────────────────────┐
  │                                                             │
  │   [1] ANALYZE         Repo 정적 분석으로 LLM 호출 패턴 추출  │
  │         ↓                                                   │
  │   [2] INFER           서비스 도메인·목적·스타일을 추론       │
  │         ↓                                                   │
  │   [3] HARVEST         도메인 관련 외부 지식을 자동 수집      │
  │         ↓                                                   │
  │   [4] GENERATE        프롬프트·RAG·평가셋·대시보드 자동 생성 │
  │         ↓                                                   │
  │   [5] DEPLOY          생성물을 서비스에 SDK/API로 주입       │
  │         ↓                                                   │
  │   [6] OBSERVE         실제 운영 중 호출·결과를 추적          │
  │         ↓                                                   │
  │   [7] EXPERIMENT      A/B 테스트로 여러 버전 비교 실행       │
  │         ↓                                                   │
  │   [8] EVOLVE          승자 버전 선택 → 패배 버전 폐기        │
  │         ↓                                                   │
  └──────── [1]로 복귀. 계속 학습하고 계속 개선 ────────────────┘
```

Each stage produces a structured output that becomes the next stage's input. The loop is designed to be closed: EVOLVE feeds updated knowledge back into ANALYZE's context for the next cycle.

---

## 2. Loop Invariants

These rules hold across every stage. A PR that violates an invariant must be rejected.

1. **Static first**: ANALYZE must not require the target service to be running. Runtime-only analysis belongs in OBSERVE, not ANALYZE.
2. **Human in the loop at gates**: DEPLOY may not push to a connected service's production without explicit user approval. GENERATE outputs are always proposals, never auto-applied.
3. **Single-source schemas**: Stage I/O contracts are defined as Pydantic models in `apps/api/src/loop/<stage>/`. No stage may accept or emit raw `dict` at its boundaries.
4. **pgvector only**: All vector storage (HARVEST chunks, GENERATE embeddings) goes into PostgreSQL via pgvector. No external vector DB.
5. **Loop membership**: Every new feature must answer "which stage does this belong to?" before merging. Cross-cutting concerns (auth, logging) are infrastructure, not loop stages.

---

## 3. Stage [1] ANALYZE

**Module:** `apps/api/src/loop/analyze/`
**Ships in:** [Phase 1](ROADMAP.md#phase-1-analyze-week-3-5)
**Status:** ✅ Implemented

### Purpose

Statically parse a connected Git repository to extract all LLM call sites, prompt strings, model parameters, and input/output variable patterns — without executing the service.

### Inputs

| Field | Type | Description |
|---|---|---|
| `repo_url` | `str` | GitHub repository URL |
| `branch` | `str` | Target branch (default: `main`) |
| `github_token` | `str` | OAuth token for private repos |

### Outputs — `AnalysisResult`

| Field | Type | Description |
|---|---|---|
| `repo_id` | `UUID` | Stable identifier for this repo |
| `call_sites` | `list[LLMCallSite]` | Each detected LLM invocation |
| `prompt_templates` | `list[PromptTemplate]` | Extracted prompt strings/templates |
| `model_configs` | `list[ModelConfig]` | model, temperature, max_tokens per site |
| `language_breakdown` | `dict[str, int]` | `{"python": 42, "typescript": 18}` |
| `analyzed_at` | `datetime` | UTC timestamp |

**`LLMCallSite`:**

| Field | Type | Description |
|---|---|---|
| `file_path` | `str` | Relative path in repo |
| `line` | `int` | Line number |
| `sdk` | `str` | `"openai"` / `"anthropic"` / `"grok"` / `"google-generativeai"` |
| `function` | `str` | e.g. `"chat.completions.create"` |
| `prompt_ref` | `str \| None` | ID of related `PromptTemplate` if extractable |

### Algorithm

1. Clone repo to isolated temp directory (shallow clone, depth=1 unless `depth` specified).
2. Detect primary languages by file extension counts.
3. For Python files: walk AST with `ast` module, detect import of `openai`, `anthropic`, `xai_grok`, `google.generativeai`; trace call chains to find `.create()` / `.generate()` / `.invoke()`.
4. For TypeScript/JavaScript files: use `tree-sitter` with the TypeScript grammar; apply same pattern matching.
5. For each detected call site: attempt to resolve the prompt argument. If it is a string literal or f-string, extract it as a `PromptTemplate`. If it is a variable, record the variable name and mark `prompt_ref` as unresolved.
6. Record model name, temperature, max_tokens, stop sequences if present.
7. Persist `AnalysisResult` to `analyses` table; persist each `PromptTemplate` to `prompt_templates` table.
8. Delete temp clone.

### Failure Modes

| Condition | Behavior |
|---|---|
| Repo clone fails (auth / not found) | Raise `RepoCloneError`; surface to dashboard with remediation link |
| No supported language detected | Raise `UnsupportedLanguageError`; inform user |
| No LLM call sites found | Return empty `call_sites`; warn user via dashboard |
| Prompt is dynamically constructed | Record call site; mark `prompt_ref = None`; do not fail |

### Completion Criteria

**Given** a connected GitHub repo containing at least one `openai` or `anthropic` SDK call,
**when** ANALYZE runs,
**then** `call_sites` is non-empty, each entry has a valid `file_path` and `line`, and the result is persisted to the `analyses` table.

### ArcanaInsight Dogfood Example

ArcanaInsight uses `xai_grok` SDK in Python. ANALYZE must detect calls like:
```python
client.chat.completions.create(model="grok-2-1212", messages=[...])
```
Expected output: `sdk = "grok"`, call site at the correct file/line, prompt extracted if string literal.

---

## 4. Stage [2] INFER

**Module:** `apps/api/src/loop/infer/`
**Ships in:** [Phase 2](ROADMAP.md#phase-2-infer--harvest-week-6-9)
**Status:** ✅ Implemented

### Purpose

Feed the ANALYZE output (extracted prompts, README, type definitions) to an LLM and receive a structured `ServiceInference` — domain, tone, language, user type — that drives HARVEST's crawling strategy.

### Inputs

| Field | Type | Description |
|---|---|---|
| `analysis_id` | `UUID` | ID of a completed `AnalysisResult` |
| `extra_context` | `str \| None` | User-supplied description override |

### Outputs — `ServiceInference`

| Field | Type | Description |
|---|---|---|
| `inference_id` | `UUID` | Stable identifier |
| `domain` | `str` | e.g. `"divination/tarot"`, `"code_review"`, `"legal_qa"` |
| `subdomain` | `str \| None` | e.g. `"celtic_spread"` within tarot |
| `tone` | `str` | `"mystical"` / `"professional"` / `"casual"` / `"technical"` |
| `language` | `str` | BCP-47 language code (`"ko"`, `"en"`) |
| `user_type` | `str` | `"consumer"` / `"developer"` / `"enterprise"` |
| `confidence` | `float` | 0.0–1.0; low confidence triggers user confirmation prompt |
| `raw_llm_response` | `str` | Full LLM output for debugging |

### Algorithm

1. Load `AnalysisResult` by `analysis_id`.
2. Build context: top-5 longest prompt templates + repo README (first 2,000 chars) + any TypeScript interface definitions.
3. Call Claude Sonnet 4.6+ with a structured output instruction: return JSON matching `ServiceInference` schema.
4. Validate response with Pydantic; retry once if validation fails.
5. If `confidence < 0.6`, flag for user confirmation before proceeding to HARVEST.
6. Persist `ServiceInference` to `inferences` table.

### Failure Modes

| Condition | Behavior |
|---|---|
| LLM returns malformed JSON | Retry once; if still invalid, raise `InferenceParseError` |
| Confidence < 0.6 | Do not auto-proceed to HARVEST; surface confirmation UI |
| No prompts in analysis | Raise `InsufficientContextError`; ask user to provide description |

### Completion Criteria

**Given** a completed `AnalysisResult` with ≥1 prompt template,
**when** INFER runs,
**then** `ServiceInference` is persisted with non-null `domain` and `confidence ≥ 0.4`.

### ArcanaInsight Dogfood Example

Expected `ServiceInference` for ArcanaInsight:
```json
{"domain": "divination/tarot", "tone": "mystical", "language": "ko", "user_type": "consumer", "confidence": 0.92}
```

---

## 5. Stage [3] HARVEST

**Module:** `apps/api/src/loop/harvest/`
**Ships in:** [Phase 2](ROADMAP.md#phase-2-infer--harvest-week-6-9)
**Status:** ✅ Implemented (recursive + semantic chunking; `playwright` opt-in)

### Purpose

Given a `ServiceInference`, automatically propose and (after user approval) execute a domain-specific crawling strategy to collect external knowledge. Chunk, embed, and store results in pgvector.

### Inputs

| Field | Type | Description |
|---|---|---|
| `inference_id` | `UUID` | ID of a completed `ServiceInference` |
| `approved_sources` | `list[str]` | URLs/source identifiers approved by user |

### Outputs — `HarvestResult`

| Field | Type | Description |
|---|---|---|
| `harvest_id` | `UUID` | Stable identifier |
| `source_count` | `int` | Number of sources crawled |
| `chunk_count` | `int` | Total knowledge chunks stored |
| `collection_name` | `str` | pgvector collection identifier |
| `embedding_model` | `str` | Model used (e.g. `"text-embedding-3-small"`) |
| `embedding_dim` | `int` | Dimension stored in `collections.embedding_dim` — never hardcoded |

### Algorithm

1. Load `ServiceInference`.
2. **Source proposal**: call an LLM to generate a list of 5–10 authoritative sources for the domain. Examples:
   - `divination/tarot` → tarot interpretation sites, Wikipedia tarot category
   - `code_review` → StackOverflow tagged questions, ESLint docs
   - `legal_qa` → 국가법령정보센터, 법원 판례 데이터베이스
3. Present proposed sources to user via dashboard for approval. Do not crawl until approved.
4. **Crawl**: for each approved source, use `httpx` for static HTML. If `use_playwright=True` is set in the job payload AND the `httpx` result is sparse (<200 chars), fall back to `playwright` (Chromium headless). `playwright` is a soft import — if not installed, crawl continues with the `httpx` result only.
5. **Extract**: use `trafilatura` to extract clean text from HTML.
6. **Chunk**: apply Recursive chunking (default) or Semantic chunking (sentence-boundary split, selectable via `chunking_strategy` job payload). Proposition chunking: Phase 3+.
7. **Embed**: call embedding API; store dimension in `collections.embedding_dim`. Never hardcode dimension.
8. **Store**: bulk-insert into `knowledge_chunks` table with `pgvector` column and `tsvector` column for hybrid search.
9. Persist `HarvestResult` to `harvest_sources` table.

### Failure Modes

| Condition | Behavior |
|---|---|
| Source returns 4xx/5xx | Log and skip; report in HarvestResult |
| Playwright timeout | Retry once; skip if still failing |
| Embedding API error | Pause batch; surface error; allow resume |
| Zero chunks after crawl | Warn user; do not fail hard |

### Completion Criteria

**Given** a `ServiceInference` with `confidence ≥ 0.6` and ≥1 user-approved source,
**when** HARVEST runs,
**then** `chunk_count ≥ 100` and all chunks are retrievable via `POST /v1/retrieve`.

### ArcanaInsight Dogfood Example

Phase 2 target: 1,000+ chunks from tarot knowledge sources. The `collection_name` will be `arcana-tarot-knowledge`. Chunks must include card meanings, spread interpretations, and symbolism.

---

## 6. Stage [4] GENERATE

**Module:** `apps/api/src/loop/generate/`
**Ships in:** [Phase 3](ROADMAP.md#phase-3-generate--deploy-week-10-13)
**Status:** ✅ Implemented

### Purpose

Using the HARVEST knowledge base and ANALYZE prompt templates as seeds, automatically generate: prompt variants, RAG index configurations, and evaluation datasets.

### Inputs

| Field | Type | Description |
|---|---|---|
| `inference_id` | `UUID` | ID of a completed `ServiceInference` (with HARVEST done) |
| `generation_id` | `UUID` | Pre-created pending generation row ID |

### Outputs — `GenerateResult`

| Field | Type | Description |
|---|---|---|
| `inference_id` | `UUID` | Source inference |
| `prompt_variants` | `list[PromptVariant]` | 5 variants: original, cot, few_shot, role_play, concise |
| `rag_config` | `RagConfig` | Recommended retrieval configuration |
| `eval_pairs` | `list[EvalPair]` | 20 realistic query/answer pairs |

### Algorithm

1. Load `Inference` row (domain, tone, language, user_type, summary) by `inference_id`.
2. Load `prompt_templates` from the related `analyses` row (JSONB).
3. Fetch up to 5 sample chunks from `chunks` table for context.
4. **Call 1 — Prompt Variants**: Claude Sonnet 4.6 generates 5 variants (original, Chain-of-Thought, few_shot, role_play, concise) from the longest detected base prompt.
5. **Call 2 — RAG Config**: Claude recommends chunking strategy (recursive/semantic), chunk_size, chunk_overlap, top_k, hybrid_alpha based on domain + sample chunks.
6. **Call 3 — Eval Pairs**: Claude generates 20 diverse query/answer pairs for this domain and service summary.
7. Persist results: update `generations` row to status=`"done"`, bulk-insert into `prompt_variants`, `rag_configs`, `eval_pairs`.
8. All outputs are proposals. No auto-deployment.

### Failure Modes

| Condition | Behavior |
|---|---|
| LLM generates fewer than 3 prompt variants | Surface warning; allow user to trigger re-generation |
| Eval pairs quality too low (LLM self-assessed) | Retry once with higher temperature |

### Completion Criteria

**Given** a completed HARVEST with ≥1 chunk in the `chunks` table,
**when** GENERATE runs,
**then** `prompt_variants` contains 5 items and `eval_pairs` contains ≥20 pairs, persisted in `generations` with status=`"done"`.

### ArcanaInsight Dogfood Example

For ArcanaInsight tarot: 5 prompt variants for the tarot reading persona (original + CoT "step-by-step card interpretation" + few-shot with card examples + role-play "ancient oracle" + concise "one-sentence guidance"), RAG config recommending `semantic` chunking with `top_k=5` from the tarot knowledge base, 20 eval pairs covering single-card draws, multi-card spreads, reversed card interpretations, and edge cases.

---

## 7. Stage [5] DEPLOY

**Module:** `apps/api/src/loop/deploy/`
**Ships in:** [Phase 3](ROADMAP.md#phase-3-generate--deploy-week-10-13)
**Status:** ✅ Implemented

### Purpose

Inject user-approved `GeneratedAssets` into the connected service via the Verum SDK, with traffic-split controls that start safe (shadow or 10% canary) before scaling.

### Inputs

| Field | Type | Description |
|---|---|---|
| `asset_id` | `UUID` | Approved `GeneratedAssets` ID |
| `deployment_config` | `DeploymentConfig` | Traffic split, rollout strategy |

### Outputs — `Deployment`

| Field | Type | Description |
|---|---|---|
| `deployment_id` | `UUID` | Stable identifier |
| `status` | `str` | `"shadow"` / `"canary"` / `"full"` / `"rolled_back"` |
| `traffic_split` | `dict[str, float]` | `{"baseline": 0.9, "variant_a": 0.1}` |
| `deployed_at` | `datetime` | UTC timestamp |

### Algorithm

1. Verify `asset_id` has `status = "approved"` by user.
2. Register deployment in `deployments` table with initial `status = "canary"` and `traffic_split = {"baseline": 0.9, "variant": 0.1}`.
3. SDK-side: `verum.chat()` reads current `traffic_split` from API on each call; routes accordingly.
4. Expose dashboard controls: increase canary %, promote to full, rollback.
5. Auto-rollback if error rate exceeds 5× baseline within first 100 calls.

### Failure Modes

| Condition | Behavior |
|---|---|
| Asset not approved | Raise `AssetNotApprovedError`; block deployment |
| SDK version mismatch | Surface upgrade prompt; do not block if minor version |
| Auto-rollback triggered | Set `status = "rolled_back"`; notify user; keep baseline |

### Completion Criteria

**Given** an approved `GeneratedAssets`,
**when** DEPLOY runs,
**then** `Deployment` is persisted with `status = "canary"`, and the connected service's `verum.chat()` calls route to the new variant for the configured traffic percentage.

### ArcanaInsight Dogfood Example

ArcanaInsight's tarot endpoint wraps its Grok call with `verum.chat()`. DEPLOY creates a canary with 10% of traffic routed to the Chain-of-Thought variant. The baseline remains the original prompt.

---

## 8. Stage [6] OBSERVE

**Module:** `apps/api/src/loop/observe/`
**Ships in:** [Phase 4](ROADMAP.md#phase-4-observe--experiment--evolve-week-14-18)
**Status:** ✅ Implemented (Phase 4-A, 2026-04-23)

### Purpose

Collect OpenTelemetry-compatible traces and spans from all `verum.chat()` calls via `client.record()`. Record cost, latency, user feedback, and async LLM-as-Judge quality scores.

### Inputs

Continuous stream from the Verum SDK via `POST /api/v1/traces` (X-Verum-API-Key auth).

### Outputs

Persisted `traces`, `spans`, `judge_prompts` rows; aggregated metrics via `GET /api/v1/metrics`.

### Key Metrics Collected

| Metric | Source |
|---|---|
| Input/output token count | `client.record()` payload |
| Latency (ms) | `client.record()` payload |
| Cost (USD) | `model_pricing` table × token count |
| Model and deployment variant | `client.record()` payload |
| User feedback (👍/👎) | `client.feedback()` → `POST /api/v1/feedback` |
| LLM-as-Judge score (0–1) | Async `judge` job → `handle_judge` |

### Key Files

| File | Purpose |
|---|---|
| `apps/api/src/loop/observe/models.py` | `TraceRecord`, `SpanRecord`, `DailyMetric` Pydantic models |
| `apps/api/src/loop/observe/repository.py` | `insert_trace`, `update_judge_score`, `get_daily_metrics` |
| `apps/api/src/db/models/traces.py` | SQLAlchemy `Trace` ORM model |
| `apps/api/src/worker/handlers/judge.py` | LLM-as-Judge async handler (`AsyncAnthropic`, 2 retries) |
| `apps/dashboard/src/app/api/v1/traces/route.ts` | POST ingest + GET list |
| `apps/dashboard/src/app/api/v1/traces/[id]/route.ts` | GET detail |
| `apps/dashboard/src/app/api/v1/metrics/route.ts` | GET daily aggregation |
| `apps/dashboard/src/app/api/v1/feedback/route.ts` | POST user feedback |
| `apps/dashboard/src/app/repos/[id]/ObserveSection.tsx` | Dashboard UI |
| `apps/dashboard/src/components/SpanWaterfall.tsx` | Trace detail slide-over |

### Completion Criteria

**Given** `client.record()` is called by a connected service,
**when** OBSERVE is active,
**then** a `Trace` with ≥1 `Span` is persisted within 5 seconds, `judge_score` is populated within 60 seconds, and the dashboard shows the trace in the OBSERVE section.

### Implementation Notes

- **Cost calculation**: `model_pricing` 테이블에서 모델명으로 조회. 미등록 모델은 cost=0으로 저장 (절대 오류 발생 안 함)
- **Judge idempotency**: `handle_judge`는 `judge_score`가 이미 있으면 스킵
- **INTERVAL parameterization**: `get_daily_metrics`에서 f-string 대신 `(INTERVAL '1 day' * :days)` 사용
- **Ownership enforcement**: 모든 브라우저 GET 엔드포인트는 `deployments → repos.owner_user_id` JOIN으로 소유권 검증
- **insertTrace atomicity**: `db.transaction()`으로 trace + span + judge job 원자적 삽입

---

## 9. Stage [7] EXPERIMENT

**Module:** `apps/api/src/loop/experiment/`
**Ships in:** [Phase 4](ROADMAP.md#phase-4-observe--experiment--evolve-week-14-18)
**Status:** 🔲 Not yet implemented

### Purpose

Automatically compare multiple deployed variants (prompts, RAG configs, model versions) using statistical significance testing. Report winner candidates to EVOLVE.

### Inputs

| Field | Type | Description |
|---|---|---|
| `deployment_ids` | `list[UUID]` | Active deployments to compare |
| `evaluation_metric` | `str` | Primary metric: `"satisfaction"` / `"ragas_faithfulness"` / `"cost_per_call"` |
| `stopping_rule` | `str` | `"bayesian"` (default) / `"fixed_horizon"` |

### Outputs — `ExperimentResult`

| Field | Type | Description |
|---|---|---|
| `experiment_id` | `UUID` | Stable identifier |
| `winner_deployment_id` | `UUID \| None` | None if no significant winner yet |
| `confidence` | `float` | Bayesian posterior probability |
| `sample_counts` | `dict[str, int]` | Calls per variant |
| `metric_summary` | `dict[str, float]` | Mean metric per variant |

### Algorithm

1. Poll OBSERVE metrics for all `deployment_ids` every 15 minutes.
2. Apply Bayesian A/B stopping criterion (default): compute posterior probability that variant A outperforms variant B.
3. If `confidence ≥ 0.95`, mark `winner_deployment_id` and surface to EVOLVE.
4. If `confidence < 0.95` after 1,000 calls per variant, surface inconclusive result; ask user how to proceed.

### Completion Criteria

**Given** ≥2 active deployments with ≥100 calls each,
**when** EXPERIMENT runs,
**then** an `ExperimentResult` is produced with `confidence` ≥ 0.0 and `sample_counts` accurately reflecting actual call volumes.

---

## 10. Stage [8] EVOLVE

**Module:** `apps/api/src/loop/evolve/`
**Ships in:** [Phase 4](ROADMAP.md#phase-4-observe--experiment--evolve-week-14-18)
**Status:** 🔲 Not yet implemented

### Purpose

Promote the winning variant to `status = "full"`, archive losing variants, update the canonical prompt/RAG config in `generated_assets`, and trigger the next loop cycle.

### Inputs

| Field | Type | Description |
|---|---|---|
| `experiment_id` | `UUID` | Completed `ExperimentResult` with a winner |

### Outputs — `Evolution`

| Field | Type | Description |
|---|---|---|
| `evolution_id` | `UUID` | Stable identifier |
| `promoted_deployment_id` | `UUID` | The winner, now at 100% traffic |
| `archived_deployment_ids` | `list[UUID]` | Losers, set to `"archived"` |
| `next_cycle_triggered` | `bool` | Whether ANALYZE was re-queued |

### Algorithm

1. Verify `ExperimentResult.confidence ≥ 0.95` and `winner_deployment_id` is set.
2. Set winner's `Deployment.status = "full"`, `traffic_split = {"winner": 1.0}`.
3. Set all losers' `Deployment.status = "archived"`.
4. Copy winning `PromptVariant` into the service's canonical slot in `generated_assets`.
5. Optionally enqueue a new ANALYZE job for the next cycle.
6. Persist `Evolution` to `evolutions` table.

### Completion Criteria

**Given** a completed `ExperimentResult` with `confidence ≥ 0.95`,
**when** EVOLVE runs,
**then** the winner deployment reaches 100% traffic, losers are archived, and the winning prompt is the new canonical.

### ArcanaInsight Dogfood Example

If the Chain-of-Thought variant wins with confidence 0.97, EVOLVE promotes it, archives the original, and ArcanaInsight's tarot reads now always use the Chain-of-Thought prompt — with no manual intervention from xzawed.

---

## 11. Job Queue and Worker Reliability

All loop stages are executed by the Python worker child process via the `verum_jobs` PostgreSQL table. This section describes the reliability guarantees.

### Job Queue (`verum_jobs`)

| Column | Description |
|---|---|
| `id` | UUID PK |
| `type` | `"analyze"` / `"infer"` / `"harvest"` / `"generate"` |
| `payload` | JSONB — stage-specific input |
| `status` | `"pending"` / `"running"` / `"done"` / `"error"` |
| `error` | Error message if status=`"error"` |
| `created_at` | UTC timestamp |

Jobs are dequeued with `SELECT ... FOR UPDATE SKIP LOCKED` to guarantee at-most-once delivery under concurrent workers.

### Worker Heartbeat (`worker_heartbeat`)

The Python worker writes a heartbeat row every 30 seconds. The dashboard polls `worker_heartbeat` and surfaces a warning if the last heartbeat is older than 90 seconds. This detects silent worker crashes without requiring process-level monitoring.

### Stage Chaining

Stages are chained automatically by the worker handlers:
- ANALYZE → INFER: triggered on `analyze` job completion
- INFER → HARVEST: triggered on `infer` job completion (confidence ≥ 0.4)
- HARVEST → GENERATE: triggered on `harvest` job completion

Each stage enqueues the next via `INSERT INTO verum_jobs` inside the same transaction as its own result write. If the result write fails, the next job is not enqueued.

---

## 12. Stage Interfaces (Pydantic Contracts)

Authoritative Pydantic model definitions live in each stage module. This section is a reference summary.

```python
# apps/api/src/loop/analyze/models.py
class LLMCallSite(BaseModel):
    file_path: str
    line: int
    sdk: str
    function: str
    prompt_ref: str | None = None

class AnalysisResult(BaseModel):
    repo_id: UUID
    call_sites: list[LLMCallSite]
    prompt_templates: list[PromptTemplate]
    model_configs: list[ModelConfig]
    language_breakdown: dict[str, int]
    analyzed_at: datetime

# apps/api/src/loop/infer/models.py
class ServiceInference(BaseModel):
    inference_id: UUID
    domain: str
    subdomain: str | None = None
    tone: str
    language: str
    user_type: str
    confidence: float
    raw_llm_response: str

# apps/api/src/loop/harvest/models.py
class HarvestResult(BaseModel):
    harvest_id: UUID
    source_count: int
    chunk_count: int
    collection_name: str
    embedding_model: str
    embedding_dim: int  # loaded from collections.embedding_dim, never hardcoded
```

```python
# apps/api/src/loop/generate/models.py
VARIANT_TYPES = ["original", "cot", "few_shot", "role_play", "concise"]

class PromptVariant(BaseModel):
    variant_type: str  # one of VARIANT_TYPES
    content: str       # full prompt with {variable} placeholders
    variables: list[str] = []

class RagConfig(BaseModel):
    chunking_strategy: str = "recursive"  # "recursive" | "semantic"
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5
    hybrid_alpha: float = 0.7

class EvalPair(BaseModel):
    query: str
    expected_answer: str
    context_needed: bool = True

class GenerateResult(BaseModel):
    inference_id: UUID
    prompt_variants: list[PromptVariant]
    rag_config: RagConfig
    eval_pairs: list[EvalPair]
```

Full Pydantic models for DEPLOY, OBSERVE, EXPERIMENT, EVOLVE follow the same pattern in their respective module directories.

---

_Maintainer: xzawed | Last updated: 2026-04-22_
