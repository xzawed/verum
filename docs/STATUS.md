---
type: status
authority: tier-1
canonical-for: [current-implementation-state, file-map, api-index, db-schema]
last-updated: 2026-05-01
---

# Verum — Current Implementation Status

> **Claude instructions:** Read this file at the start of every session BEFORE making any code changes.
> It gives a precise picture of what is implemented, where it lives, and what comes next.
> Update this file whenever a phase or deliverable completes, or the file map changes.
> Authority: CLAUDE.md > ROADMAP.md > this file > LOOP.md

---

## Loop Stage Status

| Stage | Name | Status | Shipped in |
|-------|------|--------|-----------|
| [1] ANALYZE | Repo 정적 분석 | ✅ Done | Phase 1 |
| [2] INFER | 서비스 도메인 추론 | ✅ Done | Phase 2 |
| [3] HARVEST | 도메인 지식 크롤링 | ✅ Done | Phase 2 |
| [4] GENERATE | 프롬프트·RAG·평가셋 생성 | ✅ Done | Phase 3 |
| [5] DEPLOY | SDK 주입 + 트래픽 분할 | ✅ Done | Phase 3 |
| [6] OBSERVE | 트레이스·비용·Judge 수집 | ✅ Done | Phase 4-A |
| [7] EXPERIMENT | A/B 테스트 엔진 | ✅ Done | Phase 4-B |
| [8] EVOLVE | 승자 승격 자동화 | ✅ Done | Phase 4-B |

**Next:** F-4.11 — ArcanaInsight 자동 진화 1회 달성 (프로덕션 데이터 누적 필요, xzawed 담당)

**ArcanaInsight 통합 현황 (2026-05-01):**
- Phase 0 (OTLP env-only): ✅ 적용 완료 (기존)
- Phase 1 (Auto-instrument `import verum.openai`): ✅ PR #186 → ArcanaInsight main 머지 완료

**Integration test pipeline:** `make integration-up && make integration-test` — ANALYZE→EVOLVE full-loop via Docker Compose (prod image + mock-providers + fake-arcana). Nightly CI at 08:00 UTC. See [docs/integration-tests.md](integration-tests.md).

---

## Database Tables

### Alembic Migration 순서

| Migration | 내용 |
|-----------|------|
| `0001_phase1_analyze` | `repos`, `analyses` |
| `0002_phase2_infer_harvest` | `inferences`, `harvest_sources`, `chunks` (embedding_vec vector(1536) + ts_content) |
| `0003_voyage_embeddings` | `chunks.embedding_vec` 벡터 크기를 1536 → 1024로 변경 (Voyage AI voyage-3.5) |
| `0004_users_and_repo_owner` | `users` 테이블 + repos.owner_user_id NOT NULL FK |
| `0005_verum_jobs` | `verum_jobs`, `worker_heartbeat` |
| `0006_phase3_generate` | `generations`, `prompt_variants`, `rag_configs`, `eval_pairs` |
| `0007_rag_configs_unique` | rag_configs unique index |
| `0008_metric_profile_deployments` | `deployments` + metric_profile 컬럼 |
| `0009_phase4a_observe` | `model_pricing`, `traces`, `spans`, `judge_prompts` |
| `0010_phase4b_experiment_evolve` | `experiments` + deployments.experiment_status |
| `0011_usage_quotas` | `usage_quotas` (freemium 쿼터) |
| `0013_unique_evolve_job` | partial unique index on verum_jobs (EVOLVE 중복 방지) |
| `0014_deployment_api_keys` | `deployments.api_key_hash` — cryptographic API key 인증 |
| `0015_notify_trigger` | `verum_jobs` INSERT → `NOTIFY` 트리거 |
| `0016_drop_chunks_embedding_jsonb` | `chunks.embedding` JSONB 컬럼 제거 (`embedding_vec`만 사용) |
| `0017_add_missing_indexes` | `ix_inferences_repo_id`, `ix_inferences_analysis_id`, `ix_traces_deployment_created` |
| `0018_chunks_inference_fk` | `chunks.inference_id → inferences.id CASCADE` FK |
| `0019_lookup_indexes` | `ix_traces_deployment_variant_created`, `ix_verum_jobs_status_kind_created` |
| `0019_sdk_pr_requests` | `sdk_pr_requests` — SDK PR 자동 생성 요청 추적 테이블 |
| `0020_row_level_security` | RLS ENABLE + 정책 (repos: 4개, usage_quotas: 3개) — SSRF GUC 기반. NOT FORCED (owner 우회). |
| `0021_rls_roles` | `verum_app` 로그인 역할 생성 + DML GRANT + default privileges |
| `0022_force_row_level_security` | `FORCE ROW LEVEL SECURITY` on repos + usage_quotas. **⚠️ DATABASE_URL을 verum_app으로 변경한 후에만 실행할 것.** |
| `0023_otlp_trace_attrs` | `spans.span_attributes JSONB` — OTLP Phase 0 메타데이터 저장 |
| `0024_sdk_pr_mode` | `sdk_pr_requests.mode VARCHAR(32) DEFAULT 'observe'` + 복합 인덱스. Phase 0/1 PR 상태 분리 추적 |
| `0025_integrations` | `integrations` — Railway service 연결 추적. `platform_token_encrypted` AES-256-GCM 암호화. `injected_vars JSONB` |

> **참고:** migration 0012는 존재하지 않음 (순서 정리 과정에서 스킵됨).

### 테이블 참조

| 테이블 | 역할 | 단계 |
|--------|------|------|
| `users` | GitHub OAuth 사용자 | Auth |
| `repos` | 연결된 레포지토리 | Auth |
| `analyses` | ANALYZE 결과 JSON | [1] |
| `inferences` | INFER 도메인 JSON | [2] |
| `harvest_sources` | 크롤링 소스 URL | [3] |
| `chunks` | 지식 청크 (pgvector `embedding_vec`) | [3] |
| `verum_jobs` | 비동기 잡 큐 | Worker |
| `worker_heartbeat` | Worker liveness (id=1 row, 30s 갱신) | Worker |
| `generations` | GENERATE 실행 결과 | [4] |
| `prompt_variants` | 5개 프롬프트 변형 per generation | [4] |
| `rag_configs` | RAG 설정 per generation | [4] |
| `eval_pairs` | 쿼리/답변 평가셋 | [4] |
| `deployments` | 활성 배포 (canary/full/rolled_back) + `api_key_hash` | [5] |
| `usage_quotas` | 월별 사용량 추적 (traces/chunks/repos) | Freemium |
| `model_pricing` | 모델별 토큰 단가 (6개 모델 시드) | [6] |
| `traces` | `client.record()` 호출 1건 = 1행 | [6] |
| `spans` | LLM 호출 메트릭 per trace | [6] |
| `judge_prompts` | Judge 프롬프트 + 응답 전문 (감사용) | [6] |
| `experiments` | A/B 실험 행 (pairwise Bayesian, 4라운드) | [7] |
| `sdk_pr_requests` | SDK PR 자동 생성 요청 (`mode`: `observe`/`bidirectional`, `status`, `pr_url`, `pr_number`) | [5] |
| `integrations` | Railway service 연결 (`platform_token_encrypted`, `injected_vars`, `status`) | [5] |

---

## Worker Job Types

| kind | 핸들러 함수 | 파일 |
|------|------------|------|
| `analyze` | `handle_analyze` | `apps/api/src/worker/handlers/analyze.py` |
| `infer` | `handle_infer` | `apps/api/src/worker/handlers/infer.py` |
| `harvest` | `handle_harvest` | `apps/api/src/worker/handlers/harvest.py` |
| `retrieve` | `handle_retrieve` | `apps/api/src/worker/handlers/retrieve.py` |
| `generate` | `handle_generate` | `apps/api/src/worker/handlers/generate.py` |
| `deploy` | `handle_deploy` | `apps/api/src/worker/handlers/deploy.py` |
| `judge` | `handle_judge` | `apps/api/src/worker/handlers/judge.py` |
| `evolve` | `handle_evolve` | `apps/api/src/worker/handlers/evolve.py` |

- Job 등록: `apps/api/src/worker/runner.py` — `_HANDLERS` dict에 모두 등록됨.
- Payload 스키마 검증: `_PAYLOAD_SCHEMAS` dict → `src/worker/payloads.py` Pydantic 모델로 dispatch 전 검증.
- `evolve` 잡은 `_HANDLERS` 외에 `runner.py`의 `_experiment_loop()` (5분 주기 background task)에 의해 자동 enqueueing됨. `WHERE NOT EXISTS` + partial unique index(0013)로 중복 방지.
- **`infer` 핸들러 (PR #102):** `run_infer()` 호출 전 `await check_quota(db, owner_user_id, chunks=1)` 실행. 무료 쿼터 초과 시 `QuotaExceededError` 발생 → 잡 `failed` 처리, LLM 호출 차단.
- **`generate` 핸들러 (PR #102):** 저장 완료 후 `send_generate_complete_email(user_email, domain, repo_url)` 호출 — 사용자에게 GENERATE 완료 이메일 발송.

---

## API Endpoints

### Browser-facing (Auth.js JWT session)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스체크 (인증 없음) |
| GET | `/api/repos` | 사용자 repo 목록 |
| POST | `/api/repos` | 신규 repo 연결 |
| *(Server Action)* | *`/api/repos/[id]` delete* | Repo 삭제 (HTTP 엔드포인트 아님 — Next.js Server Action) |
| POST | `/api/repos/[id]/analyze` | Repo별 analyze 잡 큐 등록 (rate-limited, 202) |
| POST | `/api/v1/analyze` | Analyze 잡 큐 등록 |
| GET | `/api/v1/analyze/[id]` | Analyze 상태 폴링 |
| POST | `/api/v1/infer` | Infer 잡 큐 등록 |
| GET | `/api/v1/infer/[id]` | Infer 상태 폴링 |
| PATCH | `/api/v1/infer/[id]/confirm` | 도메인 확인/오버라이드 |
| POST | `/api/v1/generate` | Generate 잡 큐 등록 |
| GET | `/api/v1/generate/[id]` | Generate 상태 폴링 |
| PATCH | `/api/v1/generate/[id]/approve` | 생성 자산 승인 |
| POST | `/api/v1/deploy` | 배포 생성 |
| GET | `/api/v1/deploy/[id]` | 배포 상세 조회 (JWT session auth) |
| POST | `/api/v1/deploy/[id]/traffic` | 트래픽 비율 조정 |
| POST | `/api/v1/deploy/[id]/rollback` | 배포 롤백 |
| GET | `/api/v1/traces` | 트레이스 목록 (페이지, deployment 필터) |
| GET | `/api/v1/traces/[id]` | 트레이스 상세 + 스팬 + Judge |
| GET | `/api/v1/metrics` | 7일/30일 일별 집계 |
| GET | `/api/v1/experiments` | 배포별 실험 목록 (`?deployment_id=`) |
| GET | `/api/v1/experiments/[id]` | 실험 상세 (Bayesian 신뢰도 포함) |
| GET | `/api/v1/quota` | 사용자 현재 쿼터 상태 |
| GET | `/api/repos/[id]/status` | Repo 잡 상태 폴링 (미들웨어 제외 경로) |

### SDK-facing (X-Verum-API-Key 헤더 = cryptographic token)

> **인증 변경 (migration 0014):** API 키는 `deployments.api_key_hash`(SHA-256)로 검증하는 cryptographic token입니다. deployment UUID가 아닙니다. `validateApiKey()` → `findDeploymentByApiKey(hash)` 패턴을 사용합니다.

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/v1/traces` | `client.record()` 트레이스 수집 |
| POST | `/api/v1/feedback` | `client.feedback()` 사용자 피드백 |
| GET | `/api/v1/deploy/[id]/config` | SDK `chat()` 라우팅용 배포 설정 |
| POST | `/api/v1/retrieve-sdk` | SDK `retrieve()` pgvector 의미 검색 (OpenAI 임베딩 + api_key_hash 인증) |
| POST | `/api/v1/otlp/v1/traces` | OTLP receiver — Phase 0 auto-instrument (openinference spans, no auth required for ingest) |
| GET | `/api/v1/activation/[repoId]` | ActivationCard data — INFER/GENERATE/HARVEST summary + `deployment.trace_count` for polling (JWT session auth) |
| POST | `/api/repos/[id]/activate` | One-click deployment creation — creates `deployments` + `experiments` rows, returns one-time `api_key` (`vk_<64-hex>`), `deployment_id`, `verum_api_url` (JWT session auth) |
| GET | `/api/integrations` | 사용자 Railway integration 목록 (token 필드 제외) |
| POST | `/api/integrations` | Railway service 연결 — OTLP env vars 주입 후 `integrations` 행 생성. `railway_token` AES-256-GCM 암호화 저장 |
| POST | `/api/integrations/[id]/disconnect` | Railway service 연결 해제 — env vars 삭제 (best-effort) + `status = "disconnected"` |
| GET | `/api/integrations/railway/services` | Railway API token으로 사용 가능한 서비스 목록 조회 (`?token=`) |
| POST | `/api/v1/csp-report` | CSP violation report 수신 (204, 인증 없음) |
| POST | `/api/mcp` | MCP (Model Context Protocol) endpoint — Streamable HTTP transport. API key 인증 (`Authorization: Bearer` 또는 `X-Verum-API-Key`). 4개 도구: `get_experiments`, `get_traces`, `get_metrics`, `approve_variant` |

### SDK-facing / Opt-in Proxy (X-Verum-API-Key 헤더)

| Method | Path | 설명 |
|--------|------|------|
| ANY | `/api/proxy/[...path]` | opt-in LLM 프록시 — 요청을 대상 URL로 전달. `x-verum-target-url` 헤더 필수. rate limit (per-key 120 req/min, per-IP 200 req/min). 트레이스 비동기 기록 |

### Test-only (VERUM_TEST_MODE=1 환경만 활성화)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/test/login` | CI/E2E용 JWT 세션 쿠키 발급 (GitHub OAuth 우회). 미들웨어 matcher 제외 경로. |
| POST | `/api/test/set-config-fault` | ADR-017 통합테스트용: config 엔드포인트가 503을 반환할 횟수 설정 (`count` body 파라미터) |
| DELETE | `/api/test/set-config-fault` | 위 fault count 초기화 |

---

## Python SDK

### Non-Invasive Integration (v1 — Recommended)

Two-phase approach. See [docs/SDK_PYTHON.md](SDK_PYTHON.md) and [docs/MIGRATION_v0_to_v1.md](MIGRATION_v0_to_v1.md) for full details.

| Phase | Integration effort | What it does |
|-------|-------------------|--------------|
| Phase 0.5 — Zero-code-change | `pip install verum` + set `VERUM_API_URL` + `VERUM_API_KEY` env vars. No code changes needed. | `verum-auto.pth` placed in site-packages triggers `import verum._auto` at interpreter startup, which patches openai/anthropic automatically. Set `VERUM_DISABLED=1` to opt out. |
| Phase 0 — OTLP env-only | Set 3 env vars + `import verum.openai` at startup | Sends OTLP traces to Verum. Zero code changes beyond the import. |
| Phase 1 — Auto-instrument | Add `extra_headers={"x-verum-deployment": DEPLOYMENT_ID}` to existing calls | Full bidirectional: Verum injects prompt variant into messages before the call proceeds. |

**Safety guarantees (ADR-017):** 200ms hard timeout → circuit breaker (5 failures → 300s bypass) → 60s fresh cache → 24h stale cache → fail-open passthrough. Verum's availability never blocks LLM calls.

**No gateway (ADR-016):** `import verum.openai` monkey-patches the OpenAI SDK in-process. Verum servers are never in the hot path.

**ActivationCard:** Dashboard UI at `GET /api/v1/activation/[repoId]` shows INFER/GENERATE/HARVEST results. Once a generation exists, an **Activate** button calls `POST /api/repos/[id]/activate` and returns a one-time `api_key` (`vk_<64-hex>`) with Python and Node.js env-var tabs. After saving credentials, the card polls `trace_count` every 5 seconds and transitions to "Connected" state when the first trace arrives.

### Legacy API (v0)

파일: `packages/sdk-python/src/verum/client.py`

| 메서드 | 설명 |
|--------|------|
| `await client.chat(messages, deployment_id, provider, model)` | 변형 라우팅; `{"messages": ..., "deployment_id": ..., "variant": ...}` 반환 |
| `await client.retrieve(query, collection_name, top_k)` | pgvector 검색; 관련 청크 반환 |
| `await client.record(deployment_id, variant, model, input_tokens, output_tokens, latency_ms, error)` | 트레이스 기록; `trace_id` 반환 |
| `await client.feedback(trace_id, score)` | 사용자 피드백 (`score=1` 또는 `-1`) |

> **Deprecation:** `verum.Client.chat()` raises `DeprecationWarning` in v1.x. Migrate to `import verum.openai`. See [docs/MIGRATION_v0_to_v1.md](MIGRATION_v0_to_v1.md).

**ArcanaInsight 통합 패턴 (v0 — before.py reference):**
```python
routed = await client.chat(messages=[...], deployment_id=DEPLOYMENT_ID, provider="grok", model="grok-2-1212")
t0 = time.monotonic()
resp = grok_client.chat.completions.create(model="grok-2-1212", messages=routed["messages"])
trace_id = await client.record(
    deployment_id=routed["deployment_id"], variant=routed["variant"],
    model="grok-2-1212", input_tokens=resp.usage.prompt_tokens,
    output_tokens=resp.usage.completion_tokens,
    latency_ms=int((time.monotonic() - t0) * 1000),
)
```

---

## TypeScript SDK

파일: `packages/sdk-typescript/src/client.ts`

| 메서드 | 설명 |
|--------|------|
| `await client.chat(params)` | 변형 라우팅; `{messages, routed_to, deployment_id}` 반환 |
| `await client.retrieve(params)` | pgvector 검색; 청크 배열 반환 |
| `await client.record(params)` | 트레이스 기록; `trace_id` 반환 |
| `await client.feedback(params)` | 사용자 피드백 (`score: 1 \| -1`) |

### Zero-code-change Auto-instrument (PR #103)

`packages/sdk-typescript/src/auto.ts` — Node.js 용 zero-code-change 패치.

**사용법:** `NODE_OPTIONS="--require @verum/sdk/auto"` 환경변수 + `VERUM_API_URL` + `VERUM_API_KEY` 설정. 코드 변경 불필요.

- 신규 exports 필드: `"./auto": "./dist/auto.js"` (`packages/sdk-typescript/package.json`)
- `VERUM_DISABLED=1` (또는 `true`/`yes`)로 opt-out 가능

---

## 핵심 파일 맵

### Python Worker

| 파일 | 역할 |
|------|------|
| `apps/api/src/config.py` | 모든 런타임 상수 + `PlanLimits`/`FREE_PLAN` (env-var 오버라이드 가능) |
| `apps/api/src/worker/main.py` | asyncio entrypoint (`python3 -m src.worker.main`) |
| `apps/api/src/worker/runner.py` | LISTEN/NOTIFY 잡 루프 + 핸들러 디스패치 + payload 스키마 검증. `_reset_stale()`은 부팅/주기 실행 시 `verum_jobs` 뿐 아니라 `harvest_sources.status = 'crawling'`도 `error`로 초기화(워커 재시작 감지) |
| `apps/api/src/worker/payloads.py` | 8개 job kind별 Pydantic payload 모델 |
| `apps/api/src/worker/listener.py` | asyncpg 전용 연결로 LISTEN/NOTIFY wake event 관리. DSN에서 `+asyncpg` dialect prefix를 제거해야 asyncpg.connect()가 수락함 |
| `apps/api/src/worker/chain.py` | `enqueue_next()` — 핸들러가 다음 잡을 큐에 등록하는 공통 헬퍼 |
| `apps/api/src/db/session.py` | SQLAlchemy async engine + `AsyncSessionLocal` + `get_db_for_user(user_id)` RLS context manager |
| `apps/api/src/db/error_helpers.py` | `mark_error(db, model, row_id, msg)` — 4개 단계 공통 에러 마킹 헬퍼 |
| `apps/api/src/loop/llm_client.py` | `call_claude(model, max_tokens, system, user, temperature)` — Anthropic 클라이언트 공통 래퍼 |
| `apps/api/src/loop/utils.py` | `parse_json_response(text)` — markdown fence 파싱 + `json.loads` 예외 처리 + truncation repair fallback (`_repair_truncated_json`) |
| `apps/api/src/loop/quota.py` | `check_quota()` / `increment_quota()` / `get_or_create_quota()` — freemium 쿼터 집행 |
| `apps/api/src/loop/email.py` | `send_quota_warning_email()` stub (80% 쿼터 도달 시 트리거) |
| `apps/api/src/worker/handlers/analyze.py` | ANALYZE 잡 핸들러 (단일 트랜잭션으로 save + enqueue_next) |
| `apps/api/src/worker/handlers/judge.py` | LLM-as-Judge: AsyncAnthropic, 2회 재시도, idempotent |
| `apps/api/src/loop/observe/models.py` | TraceRecord, SpanRecord, DailyMetric Pydantic 모델 |
| `apps/api/src/loop/observe/repository.py` | `insert_trace`, `update_judge_score`, `get_daily_metrics` |
| `apps/api/src/loop/experiment/engine.py` | `compute_winner_score`, `bayesian_confidence`, `check_experiment` |
| `apps/api/src/loop/experiment/repository.py` | `get_running_experiment`, `aggregate_variant_wins`, `insert_experiment` 등 |
| `apps/api/src/loop/evolve/engine.py` | `promote_winner`, `next_challenger`, `start_next_challenger`, `complete_deployment` |
| `apps/api/src/loop/evolve/repository.py` | `update_deployment_baseline`, `update_traffic_split`, `set_experiment_status` |
| `apps/api/src/loop/deploy/repository.py` | `create_deployment()` — api_key 생성 + sha256 해시 저장, 평문은 응답에만 |
| `apps/api/src/loop/deploy/orchestrator.py` | `run_deploy()` — deployment 생성 + 트래픽 초기화 오케스트레이션 |

### Next.js Dashboard

| 파일 | 역할 |
|------|------|
| `apps/dashboard/src/lib/db/schema.ts` | Drizzle 테이블 정의 (Alembic SoT → 수동 동기화) |
| `apps/dashboard/src/lib/db/queries.ts` | 읽기 전용 쿼리 (모두 `owner_user_id` 검증). `getRepoStatus()`는 `harvestJobStatus`(verum_jobs 직접 조회)를 포함해 대시보드 HARVEST 칩이 실제 잡 완료 여부를 반영. `getLatestSdkPrRequestByMode(userId, repoId, mode)` — Phase 0/1 PR 상태 분리 조회 |
| `apps/dashboard/src/lib/db/jobs.ts` | 쓰기 작업 (잡 큐 등록, 상태 변경); INSERT 실패 시 명시적 throw. `createSdkPrRequest`는 `mode: "observe"/"bidirectional"` 필수 파라미터 |
| `apps/dashboard/src/lib/db/deploys.ts` | `findDeploymentByApiKey(hash)` — SDK 인증용 |
| `apps/dashboard/src/lib/db/quota.ts` | `getQuota(userId)` — 대시보드용 쿼터 조회 |
| `apps/dashboard/src/lib/api/handlers.ts` | `createGetByIdHandler<T>()`, `getAuthUserId()` — 라우트 보일러플레이트 제거 |
| `apps/dashboard/src/lib/api/validateApiKey.ts` | `validateApiKey(rawKey)` → SHA-256 해시 → `findDeploymentByApiKey` |
| `apps/dashboard/src/lib/rateLimit.ts` | 슬라이딩 윈도우 레이트 리미터 — Redis 우선(ioredis), in-memory 폴백. `checkRateLimitDual(userKey, userLimit, ip, ipLimit)` |
| `apps/dashboard/src/lib/rateLimitRedis.ts` | Lua 원자 슬라이딩 윈도우 Redis 구현. `checkRateLimitRedis(key, limit, windowMs)` — null 반환 시 호출자가 in-memory로 폴백 |
| `apps/dashboard/src/lib/i18n.ts` | en/ko 이중 언어 UI 문자열 맵; `t(group, key, locale?)` 함수 |
| `apps/dashboard/src/lib/docs.ts` | Markdown 렌더링 파이프라인 (remark → rehype-sanitize, XSS 방지) |
| `apps/dashboard/src/app/api/v1/retrieve-sdk/route.ts` | SDK `retrieve()` 처리 — OpenAI 임베딩 생성 + pgvector 검색 (lazy-init 패턴) |
| `apps/dashboard/src/app/api/v1/traces/route.ts` | POST (SDK 수집 + 쿼터 검증) + GET (브라우저 목록) |
| `apps/dashboard/src/app/api/v1/traces/[id]/route.ts` | GET 상세 (소유권 JOIN 검증) |
| `apps/dashboard/src/app/api/v1/metrics/route.ts` | GET 일별 집계 (소유권 검증) |
| `apps/dashboard/src/app/api/v1/feedback/route.ts` | POST 사용자 피드백 (api_key_hash 검증) |
| `apps/dashboard/src/app/api/v1/quota/route.ts` | GET 사용자 쿼터 상태 |
| `apps/dashboard/src/app/repos/[id]/ObserveSection.tsx` | OBSERVE 섹션 (메트릭 카드 + Recharts 차트 + 테이블) |
| `apps/dashboard/src/components/SpanWaterfall.tsx` | 트레이스 상세 슬라이드오버 패널 |
| `apps/dashboard/src/app/globals.css` | Tailwind v4 `@import` + box-sizing reset + body margin 0 |
| `apps/dashboard/src/app/layout.tsx` | Root App Router layout — `auth()` 세션 → `AppShell` 래퍼. 모든 인증 페이지의 공통 shell 진입점 |
| `apps/dashboard/src/components/AppShell.tsx` | `"use client"` shell — `usePathname()`으로 `/login`·`/health` 여부 판단; 해당 경로는 사이드바 없는 풀페이지, 나머지는 `Sidebar` + `<main>` 레이아웃 |
| `apps/dashboard/src/components/Sidebar.tsx` | 56px 아이콘 사이드바 — 인디고 로고 뱃지("V"), Repos·Docs 네비 아이콘(active/hover 상태), 사용자 이니셜 아바타. 현재 pathname으로 active 판단 |
| `apps/dashboard/src/app/repos/[id]/StagesView.tsx` | Loop 8단계 수평 스테퍼 (done/active/pending 시각 상태) + 실행 중 단계 카드(좌측 색상 border + 진행 바) + Quick Stats 3-grid + OBSERVE·EXPERIMENT·INTEGRATION 섹션 마운트 |
| `apps/dashboard/src/app/api/v1/experiments/route.ts` | GET 실험 목록 (배포별) |
| `apps/dashboard/src/app/api/v1/experiments/[id]/route.ts` | GET 실험 상세 |
| `apps/dashboard/src/app/repos/[id]/ExperimentSection.tsx` | EXPERIMENT 섹션 UI (5초 폴링, Bayesian 신뢰도 바) |
| `apps/dashboard/src/hooks/useAdaptivePolling.ts` | 지수 백오프 폴링 훅 — 잡 활성 중 빠른 폴링, 유휴 시 백오프. `StagesView.tsx`·`ExperimentSection.tsx`에서 사용 |
| `apps/dashboard/src/app/api/repos/[id]/status/route.ts` | Repo 잡 상태 폴링 (미들웨어 matcher `api/repos` 제외) |
| `apps/dashboard/src/app/api/test/login/route.ts` | CI/E2E JWT 세션 발급 (`VERUM_TEST_MODE=1`만 활성화). DB upsert는 best-effort (try/catch) — Postgres 없는 E2E 환경에서도 JWT 반환 |
| `apps/dashboard/src/app/api/test/set-config-fault/route.ts` | ADR-017 통합테스트용 fault injection 제어 엔드포인트 (POST: fault 횟수 설정, DELETE: 초기화) |
| `apps/dashboard/src/lib/test/configFault.ts` | 프로세스 레벨 fault 상태 (setConfigFault/resetConfigFault/consumeConfigFault). `VERUM_TEST_MODE=1`에서만 활성화. 프로덕션에서는 항상 `false` 반환. |
| `apps/dashboard/src/app/api/v1/otlp/v1/traces/route.ts` | Phase 0 OTLP HTTP receiver — openinference span 수신, 인증 불필요 |
| `apps/dashboard/src/app/api/v1/activation/[repoId]/route.ts` | ActivationCard 데이터 엔드포인트 — INFER/GENERATE/HARVEST 요약 + `deployment.trace_count` 반환 (ActivationCard 폴링용) |
| `apps/dashboard/src/app/api/repos/[id]/activate/route.ts` | POST: 원클릭 배포 생성. `deployments` + `experiments` 행 삽입, `api_key` 평문 1회 반환 (SHA-256 해시만 DB 저장 — GitHub PAT 모델). 중복 배포 시 409. |
| `apps/dashboard/src/components/repo/ActivationCard.tsx` | 5-state 배포 UI (`no-generation → ready → activated → waiting → connected`). Activate 버튼 → `POST /api/repos/[id]/activate` → Python·Node.js 탭(env vars 1회 표시) → "Done" → `trace_count` 5초 폴링 → connected |
| `apps/dashboard/src/lib/sdk-pr/transformer.ts` | PR 파일 변경 생성기 — callSites 기반으로 `.env.example`, `package.json`, `requirements.txt`, import 라인 변경 빌드 (`observe` / `bidirectional` 두 모드). Windows `\` 경로 자동 정규화 + `..`·절대경로 거부 포함. `buildPrFileChanges()` 메인 export |
| `apps/dashboard/src/lib/github/pr-creator.ts` | GitHub Git Data API 클라이언트 (blob→tree→commit→ref→PR 7단계). `res.text()` 먼저 읽어 에러 body 항상 포함; 비-JSON 응답은 `GitHubApiError(parse error)`로 래핑 |
| `apps/dashboard/src/app/api/repos/[id]/sdk-pr/route.ts` | POST: GitHub PR 자동 생성 (Phase 0 env-only / Phase 1 bidirectional). `call_sites` Zod 검증, `readFile` try/catch 격리, `github_url` `.git`·SSH URL 정규화, `fileChanges=[]` 시 200 조기 반환, `mode` 저장. GET: 최근 sdk-pr 요청 상태 조회 |
| `apps/dashboard/src/app/api/repos/[id]/sdk-pr/[requestId]/route.ts` | GET: 개별 sdk-pr 요청 상세 (requestId + owner 검증) |
| `apps/dashboard/src/lib/encrypt.ts` | AES-256-GCM `encrypt(plaintext)` / `decrypt(ciphertext)` — `ENCRYPTION_KEY` env var (64-char hex). Railway API token 저장 암호화에 사용 |
| `apps/dashboard/src/lib/railway.ts` | Railway GraphQL API 클라이언트 — `listRailwayServices`, `upsertRailwayVariables`, `deleteRailwayVariables`. GraphQL-level error 명시적 감지 (`errors` 배열 체크) |
| `apps/dashboard/src/app/api/integrations/route.ts` | GET: 사용자 Railway integration 목록 (token 제외). POST: Railway service 연결 — OTLP/NODE_OPTIONS env vars 주입 + token AES-256-GCM 암호화 저장 |
| `apps/dashboard/src/app/api/integrations/[id]/disconnect/route.ts` | POST: Railway 연결 해제 — env vars 삭제 best-effort + `status = "disconnected"` |
| `apps/dashboard/src/app/api/integrations/railway/services/route.ts` | GET: `?token=` 파라미터로 Railway API 서비스 목록 조회 |
| `apps/dashboard/src/app/api/proxy/[...path]/route.ts` | POST + GET opt-in LLM 프록시 — `x-verum-target-url` 헤더로 업스트림 결정. validateApiKey + rate limit + 비동기 trace 기록 |
| `apps/dashboard/src/app/repos/[id]/IntegrationSection.tsx` | Railway 통합 3-step 모달 UI (token → 서비스 선택 → 확인) + 연결 해제 버튼. `StagesView.tsx`에서 마운트 |

### SDK Packages

| 파일 | 역할 |
|------|------|
| `packages/sdk-python/src/verum/openai.py` | `import verum.openai` — OpenAI Python SDK monkey-patch (Phase 1 auto-instrument) |
| `packages/sdk-python/src/verum/anthropic.py` | `import verum.anthropic` — Anthropic Python SDK monkey-patch |
| `packages/sdk-python/src/verum/_auto.py` | Zero-code-change auto-patch (Phase 0.5) — checks `VERUM_API_URL`/`VERUM_API_KEY` env vars, patches openai/anthropic automatically at interpreter startup. Respects `VERUM_DISABLED`. |
| `packages/sdk-python/verum-auto.pth` | Installed to site-packages via hatchling `force-include`. Contains `import verum._auto` — triggers at Python interpreter startup automatically. |
| `packages/sdk-python/src/verum/_safe_resolver.py` | 5-layer safety net: 200ms timeout → circuit breaker → 60s cache → 24h stale cache → fail-open |
| `packages/sdk-python/src/verum/_instrument.py` | OTLP span export helper shared by openai/anthropic patches |
| `packages/sdk-python/src/verum/client.py` | Legacy `Client` class (deprecated v0 API — emits `DeprecationWarning`) |
| `packages/sdk-typescript/src/auto.ts` | Zero-code-change auto-patch (Phase 0.5) — same logic as Python `_auto.py`, loaded via `NODE_OPTIONS="--require @verum/sdk/auto"`. Exports `{}`. |
| `packages/sdk-typescript/src/openai.ts` | `import "@verum/sdk/openai"` — OpenAI TypeScript SDK monkey-patch (Phase 1) |
| `packages/sdk-typescript/src/_safe-resolver.ts` | TypeScript 5-layer safety net (mirrors Python `_safe_resolver.py`) |
| `packages/sdk-typescript/src/client.ts` | Legacy `VerumClient` class (deprecated v0 API) |

---

## 인증 규칙

| 엔드포인트 | 인증 방식 |
|------------|----------|
| SDK 엔드포인트 (`POST /api/v1/traces`, `POST /api/v1/feedback`) | `X-Verum-API-Key` 헤더 → SHA-256 해시 → `deployments.api_key_hash` 조회 |
| 브라우저 엔드포인트 (모든 GET, 대시보드 PATCH/POST) | Auth.js JWT 세션 (GitHub OAuth) |
| `/health` | 인증 없음 |
| `/api/test/login` (VERUM_TEST_MODE=1) | 인증 없음 (미들웨어 제외, 테스트 환경 전용) |
| `/api/repos/[id]/status` | 미들웨어 제외 경로 (라우트 자체에서 auth 검증) |

---

## 소유권 검증 패턴

브라우저 엔드포인트는 반드시 `owner_user_id`를 검증한다. 패턴:

- **단일 리소스**: `queries.ts`의 함수에 `userId` 파라미터 → SQL JOIN으로 `repos.owner_user_id = userId`
- **deployment 필터 목록**: 라우트에서 `getDeployment(userId, deploymentId)` 먼저 호출 → 없으면 404
- **트레이스 상세**: `getTraceDetail(userId, traceId)` — traces → deployments → repos JOIN
- **SDK 엔드포인트**: `validateApiKey(rawKey)` → `findDeploymentByApiKey(hash)` — userId는 반환값에서 추출

---

## 기술 백로그

6개 에이전트 전체 코드베이스 감사 결과: **[docs/BACKLOG.md](BACKLOG.md)** 참고.  
38개 항목 **전원 완료** (0개 미완료). 마지막 갱신 2026-04-27.

**2026-05-01 품질 감사 (6-agent: 4 전문 + 2 교차검증) 추가 수정:**
- ✅ PR #100: eval_pairs 최소 개수 guard (`_EVAL_PAIRS_MIN = 10`) + ADR-017 config fault injection 안전망 통합 테스트
- ✅ PR #101: SDK trace posting 묵음 예외 → `_logger.debug(...)` (openai.py, anthropic.py 각 4곳) + `rerunGenerate` `/repos/undefined` 리다이렉트 버그 수정
- ✅ PR #102: INFER 핸들러 쿼터 체크 + GENERATE 완료 이메일 + 대시보드 INFER 도메인 카드 UI + HARVEST 소스 버튼 정리
- ✅ PR #103: Python SDK `verum._auto` + `verum-auto.pth` (Phase 0.5 zero-code-change) + TypeScript SDK `@verum/sdk/auto` + `NODE_OPTIONS` 방식
- ✅ PR #104: ActivationCard v2 — GitHub PR 의존성 완전 제거. 원클릭 Activate → 일회성 `api_key` 발급 → Python·Node.js env-var 탭 → `trace_count` 폴링 → Connected 흐름. `POST /api/repos/[id]/activate` 신규 엔드포인트 + `GET /api/v1/activation/[repoId]` `trace_count` 필드 추가.
- ✅ PR #112: Railway 플랫폼 통합 (connect/disconnect UI + AES-256-GCM token 암호화 + OTLP/NODE_OPTIONS env var 자동 주입) + opt-in LLM 프록시 (`/api/proxy/[...path]`, validateApiKey + rate limit + 비동기 trace 기록). `integrations` 테이블 (migration 0025). `.codecov.yml`에 `.tsx` 제외 패턴 추가.

---

## 알려진 제약 / 다음 Phase로 미룬 것

| 항목 | 이유 | 예정 단계 |
|------|------|----------|
| spans에 실제 프롬프트/응답 텍스트 미저장 | 개인정보 보호; opt-in 방식으로 | Phase 5 |
| RAGAS 평가 (faithfulness, answer_relevancy) | Phase 4-B 스코프 외 명시적 제외 | Phase 5 |
| model_pricing 관리 UI | 현재 DB 직접 편집 | Phase 5 |
| 다중 배포 메트릭 비교 | Phase 5 | Phase 5 |
| 실시간 트레이스 스트리밍 (WebSocket/SSE) | Phase 5 | Phase 5 |
| avg_winner_score 실시간 집계 | ExperimentResult 모델 필드 있음, 집계 미구현 | Phase 5 |
| 30일 Abandonment 정책 | Phase 4-B 스코프 외 | Phase 5 |

---

## Drizzle Schema 동기화 규칙

Alembic이 스키마 SoT다. `drizzle-kit pull`이 동작하지 않는 환경(워크트리 등)에서는 `apps/dashboard/src/lib/db/schema.ts`에 수동으로 테이블을 추가한다. 추가 시 타입 임포트도 함께 export해야 한다.

---

## next build 호환성 규칙

`next build`는 "Collecting page data" 단계에서 각 라우트 모듈을 import한다. **모듈 스코프에서 환경 변수를 검증하거나 외부 클라이언트를 인스턴스화하면 빌드가 실패한다.** 환경 변수(DATABASE_URL, OPENAI_API_KEY 등)가 없는 Docker 빌드 환경에서는 반드시 아래 패턴을 따른다.

```typescript
// ❌ 금지 — 모듈 스코프에서 즉시 실패
const client = new OpenAI();   // OPENAI_API_KEY 없으면 throw
if (!process.env.VAR) throw new Error("...");

// ✅ 올바른 패턴 — lazy getter (첫 실제 요청 시에만 초기화)
let _client: OpenAI | null = null;
function getClient() {
  if (!_client) _client = new OpenAI();  // 런타임에만 실행
  return _client;
}
```

현재 적용 파일:
- `apps/dashboard/src/lib/db/client.ts` — `getDb()` lazy getter (DATABASE_URL); `withUserId(userId, fn)` RLS transaction helper
- `apps/dashboard/src/app/api/v1/retrieve-sdk/route.ts` — `getOpenAI()` lazy getter (OPENAI_API_KEY)
- `apps/dashboard/src/lib/rateLimitRedis.ts` — `getRedis()` lazy getter (REDIS_URL); 연결 전 첫 호출은 null 반환 → in-memory 폴백

새 라우트에서 외부 클라이언트(OpenAI, Anthropic, Redis 등)를 사용할 때는 반드시 이 패턴을 적용한다.

---

## Integration 테스트 인프라

| 파일 | 역할 |
|------|------|
| `tests/integration/conftest.py` | pytest-asyncio session/function scope fixtures; `_session_token` (session), `async_db`/`dashboard_client` (function) |
| `tests/integration/utils/wait.py` | `wait_until(fn, label, timeout)` — 폴링 헬퍼. `first_exc` + `last_exc` 양쪽 추적으로 `InFailedSQLTransactionError` cascade에 가려진 원본 오류 노출 |
| `tests/integration/mock-providers/` | FastAPI mock 스택 (Anthropic, OpenAI). `_match_system_contains` + `_match_user_contains` 두 매처 지원 |

**SQLAlchemy `text()` CAST 규칙 (ADR-013):** `text()` 쿼리에서 `:param::type` PostgreSQL 캐스트 구문 금지. SQLAlchemy가 `::` 앞을 bind param으로 처리하지 않아 asyncpg에 literal `:param` 문자열이 전달됨. 반드시 `CAST(:param AS type)` 사용.

**`analyses` 테이블 컬럼 주의:** `analyses`는 `started_at` 컬럼을 사용한다 (`created_at` 아님). `inferences`, `generations` 등 다른 테이블은 `created_at`.

## Python 테스트 인프라

| 파일 | 역할 |
|------|------|
| `apps/api/tests/conftest.py` | `mock_db` (AsyncMock), `make_execute_result(rows)`, `owner_user_id` UUID, `requires_db` skip marker, `async_db_session` (real Postgres + rollback) |

- `async_db_session` fixture: pytest-asyncio 기반, Postgres가 도달 불가능하면 자동 skip.
- `requires_db` 마커: `conftest.py`의 `requires_db = pytest.mark.skipif(not _is_db_available(), ...)`. `pyproject.toml` `[tool.pytest.ini_options]`에 마커 등록됨.
- CI `test-api` 잡은 Postgres service를 기동하므로 `requires_db` 테스트가 CI에서 자동 실행됨.
- 로컬에서 `DATABASE_URL` 없으면 `requires_db` 테스트만 skip — 나머지 mock-based 단위 테스트는 항상 실행됨.

---

## Railway 배포 운영 규칙

### SKIPPED 배포 수동 재실행

Railway는 특정 조건(merge queue race, 이전 배포 큐 잔존 등)에서 배포를 SKIPPED 처리하며 `skipReason`을 제공하지 않을 수 있다.

**증상:** PR 머지 후 Railway GitHub App check가 SKIPPED 상태로 종료됨.  
**확인:** `railway deployment list --service <SERVICE_ID>` → `STATUS: SKIPPED`  
**해결:** `railway deployment redeploy --service <SERVICE_ID> --yes`

> 서비스 ID `0eb974e1-a152-483a-9426-90bbb0e4d9bd` (verum-production). `railway status`로 확인 가능.

---

## 테스트 커버리지 현황

| 구분 | 테스트 파일 수 | 테스트 수 | 최근 갱신 |
|------|--------------|---------|----------|
| Python API (loop + worker) | 48 | 539 passing (CI: full suite with Postgres; 로컬 Postgres 미기동 시 requires_db 자동 skip) | 2026-04-26 |
| Python SDK (`packages/sdk-python`) | 11 | 119 | 2026-04-26 |
| TypeScript SDK (`packages/sdk-typescript`) | 5 | 80 | 2026-04-26 |
| Dashboard Jest | 39 suites | 342 | 2026-05-01 |
| E2E Playwright | 3 spec | ~16 | 2026-04-25 |

**SonarCloud Quality Gate:** PASSED ✅ — New Coverage **96.3%** (임계값 80%), Security Hotspots Reviewed **100%**, Duplicated Lines **2.6%** (임계값 3%).

> `requires_db` 마커가 붙은 1개 테스트는 로컬 Postgres 미기동 시 자동 skip. CI `test-api` 잡에서는 Postgres service가 기동되므로 전체 실행됨.

### SonarCloud 운영 규칙

- **`sonar.branch.name=main` 절대 하드코딩 금지 (PR #75에서 수정):** `sonarcloud-github-action`이 PR 이벤트 시 자동으로 `sonar.pullrequest.*`를 주입한다. `sonar.branch.name=main`이 있으면 이를 덮어써서 모든 PR 분석이 main 브랜치로 업로드됨 → PR-scoped Quality Gate 불동작 + main Quality Gate 실패.
- **S2631 ReDoS 대응:** `(\s|==|>=|$)` 형태의 alternation은 Sonar S2631로 플래그됨. `\b` (word boundary) 또는 character class `[...]`로 교체. `new_security_hotspots_reviewed=100%` 조건이 걸리므로 신규 정규식 추가 시 확인 필요.
- **flaky integration test:** HARVEST pipeline 120s 타임아웃 등 CI 환경 일시 지연 문제는 `gh run rerun <id> --failed`로 재실행.

### SonarCloud "New Code Coverage" 주의사항 (ADR-015)

SonarCloud는 직전 push 이후 **추가·수정된 라인만** 신규 코드로 집계한다 (`previous_version` 모드). Python과 TypeScript LCOV가 **합산**되므로, Python 커버리지가 높아도 TypeScript 신규 파일이 미커버라면 전체 게이트가 실패한다.

**재발 방지 패턴:** 새 유틸리티 파일(`lib/`, `helpers/`)을 추가할 때 **동일 PR에 직접 단위 테스트 파일을 포함**한다. `jest.mock()`으로 통째로 교체되는 파일은 mock 없이 직접 import하는 별도 테스트가 필요하다. → 전체 규칙은 [ADR-015](ARCHITECTURE.md#adr-015-공통-mock-대상-모듈은-직접-단위-테스트-필수) 참조.

### Python 테스트 파일 분포

| 모듈 | 테스트 파일 수 | 주요 커버 영역 |
|------|-------------|--------------|
| `loop/analyze/` | 4 | models, repository, typescript parser, cloner (disk-quota/SSRF/timeout) |
| `loop/infer/` | 3 | engine (Claude mock), models, repository |
| `loop/harvest/` | 7 | chunker, chunking_strategy, embedder, playwright_crawler, pipeline, crawler_security, repository |
| `loop/generate/` | 4 | engine, metric_profile, models, repository |
| `loop/deploy/` | 3 | engine, orchestrator, repository |
| `loop/observe/` | 1 | repository |
| `loop/experiment/` | 3 | engine (Bayesian), models, repository |
| `loop/evolve/` | 2 | engine, repository |
| `loop/` (root) | 2 | llm_client, utils |
| `worker/handlers/` | 8 | 8개 핸들러 전체 |
| `worker/` (root) | 3 | chain, payloads (validator 오류경로 포함), runner |
| `db/` | 1 | session (get_db_for_user GUC) |
| `tests/` (root) | 1 | quota |
| **합계** | **40** | |

### 테스트 Role (.claude/)

6개 전문가 에이전트가 `.claude/agents/`에 상주:

| 에이전트 | 역할 |
|---------|------|
| `test-orchestrator` | 총괄. gap-analyzer → 병렬 writer → coverage-auditor 순서 조율 |
| `test-gap-analyzer` | 미테스트 모듈 P0/P1/P2 리스크 랭킹 |
| `test-unit-writer` | AsyncMock 기반 단위 테스트 (Python + TypeScript) |
| `test-integration-writer` | `requires_db` + `async_db_session` 통합 테스트 |
| `test-e2e-writer` | Playwright E2E (`/test/login` bypass 활용) |
| `test-coverage-auditor` | pytest/jest/playwright 집계 → CI artifact (`coverage/coverage-summary.json`) |

- `PostToolUse` hook: `src/**` 편집 시 `.claude/hooks/post_test_edit.py`가 대응 테스트 자동 실행 (비블로킹, 항상 exit 0). `.claude/settings.json`은 `git rev-parse --show-toplevel`로 repo root의 hook을 찾으므로 CWD와 무관. 세션 중 CWD가 하위 디렉토리인 경우를 위해 `apps/api/.claude/hooks/post_test_edit.py`와 `apps/dashboard/.claude/hooks/post_test_edit.py`에도 5단계 dirname으로 실제 hook을 위임하는 프록시 파일이 있음.
- 스킬 참조: `.claude/skills/test-run.md`, `.claude/skills/test-patterns.md`, `.claude/skills/loop-stage-coverage.md`

---

_Last updated: 2026-05-02 (docs audit: webhook_subscriptions 미구현 항목 제거, webhook handler 제거, csp-report·deploy[id]·repos[id]/analyze 엔드포인트 추가, integrations 테이블 참조 정정) | Maintained by: Claude at end of each implementation session_
