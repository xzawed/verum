---
type: status
authority: tier-1
canonical-for: [current-implementation-state, file-map, api-index, db-schema]
last-updated: 2026-04-24
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

---

## Database Tables

### Alembic Migration 순서

| Migration | 내용 |
|-----------|------|
| `0001_phase1_analyze` | `users`, `repos` |
| `0002_phase2_infer_harvest` | `analyses` |
| `0003_voyage_embeddings` | `inferences`, `harvest_sources`, `chunks`, `collections` |
| `0004_users_and_repo_owner` | `verum_jobs`, `worker_heartbeat` |
| `0005_verum_jobs` | repos unique constraint |
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
| `collections` | pgvector 컬렉션 메타 (`embedding_dim` 포함) | [3] |
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

---

## API Endpoints

### Browser-facing (Auth.js JWT session)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스체크 (인증 없음) |
| GET | `/api/v1/repos` | 사용자 repo 목록 |
| POST | `/api/v1/repos` | 신규 repo 연결 |
| DELETE | `/api/v1/repos/[id]` | Repo 삭제 |
| POST | `/api/v1/analyze` | Analyze 잡 큐 등록 |
| GET | `/api/v1/analyze/[id]` | Analyze 상태 폴링 |
| POST | `/api/v1/infer` | Infer 잡 큐 등록 |
| GET | `/api/v1/infer/[id]` | Infer 상태 폴링 |
| PATCH | `/api/v1/infer/[id]/confirm` | 도메인 확인/오버라이드 |
| POST | `/api/v1/generate` | Generate 잡 큐 등록 |
| GET | `/api/v1/generate/[id]` | Generate 상태 폴링 |
| PATCH | `/api/v1/generate/[id]/approve` | 생성 자산 승인 |
| POST | `/api/v1/deploy` | 배포 생성 |
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

### Test-only (VERUM_TEST_MODE=1 환경만 활성화)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/test/login` | CI/E2E용 JWT 세션 쿠키 발급 (GitHub OAuth 우회). 미들웨어 matcher 제외 경로. |

---

## Python SDK

파일: `packages/sdk-python/src/verum/client.py`

| 메서드 | 설명 |
|--------|------|
| `await client.chat(messages, deployment_id, provider, model)` | 변형 라우팅; `{"messages": ..., "deployment_id": ..., "variant": ...}` 반환 |
| `await client.retrieve(query, deployment_id, top_k, hybrid)` | pgvector 검색; 관련 청크 반환 |
| `await client.record(deployment_id, variant, model, input_tokens, output_tokens, latency_ms, error)` | 트레이스 기록; `trace_id` 반환 |
| `await client.feedback(trace_id, score)` | 사용자 피드백 (`score=1` 또는 `-1`) |

**ArcanaInsight 통합 패턴:**
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

---

## 핵심 파일 맵

### Python Worker

| 파일 | 역할 |
|------|------|
| `apps/api/src/config.py` | 모든 런타임 상수 + `PlanLimits`/`FREE_PLAN` (env-var 오버라이드 가능) |
| `apps/api/src/worker/main.py` | asyncio entrypoint (`python3 -m src.worker.main`) |
| `apps/api/src/worker/runner.py` | LISTEN/NOTIFY 잡 루프 + 핸들러 디스패치 + payload 스키마 검증 |
| `apps/api/src/worker/payloads.py` | 8개 job kind별 Pydantic payload 모델 |
| `apps/api/src/worker/listener.py` | asyncpg 전용 연결로 LISTEN/NOTIFY wake event 관리 |
| `apps/api/src/worker/chain.py` | `enqueue_next()` — 핸들러가 다음 잡을 큐에 등록하는 공통 헬퍼 |
| `apps/api/src/db/session.py` | SQLAlchemy async engine + `AsyncSessionLocal` (pool_size=20, max_overflow=40) |
| `apps/api/src/db/error_helpers.py` | `mark_error(db, model, row_id, msg)` — 4개 단계 공통 에러 마킹 헬퍼 |
| `apps/api/src/loop/llm_client.py` | `call_claude(model, max_tokens, system, user, temperature)` — Anthropic 클라이언트 공통 래퍼 |
| `apps/api/src/loop/utils.py` | `parse_json_response(text)` — markdown fence 파싱 + `json.loads` 예외 처리 |
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
| `apps/dashboard/src/lib/db/queries.ts` | 읽기 전용 쿼리 (모두 `owner_user_id` 검증) |
| `apps/dashboard/src/lib/db/jobs.ts` | 쓰기 작업 (잡 큐 등록, 상태 변경); INSERT 실패 시 명시적 throw |
| `apps/dashboard/src/lib/db/deploys.ts` | `findDeploymentByApiKey(hash)` — SDK 인증용 |
| `apps/dashboard/src/lib/db/quota.ts` | `getQuota(userId)` — 대시보드용 쿼터 조회 |
| `apps/dashboard/src/lib/api/handlers.ts` | `createGetByIdHandler<T>()`, `getAuthUserId()` — 라우트 보일러플레이트 제거 |
| `apps/dashboard/src/lib/api/validateApiKey.ts` | `validateApiKey(rawKey)` → SHA-256 해시 → `findDeploymentByApiKey` |
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
| `apps/dashboard/src/app/repos/[id]/StagesView.tsx` | OBSERVE + EXPERIMENT 섹션 마운트 |
| `apps/dashboard/src/app/api/v1/experiments/route.ts` | GET 실험 목록 (배포별) |
| `apps/dashboard/src/app/api/v1/experiments/[id]/route.ts` | GET 실험 상세 |
| `apps/dashboard/src/app/repos/[id]/ExperimentSection.tsx` | EXPERIMENT 섹션 UI (5초 폴링, Bayesian 신뢰도 바) |
| `apps/dashboard/src/app/api/repos/[id]/status/route.ts` | Repo 잡 상태 폴링 (미들웨어 matcher `api/repos` 제외) |
| `apps/dashboard/src/app/api/test/login/route.ts` | CI/E2E JWT 세션 발급 (`VERUM_TEST_MODE=1`만 활성화) |

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
- `apps/dashboard/src/lib/db/client.ts` — `getDb()` lazy getter (DATABASE_URL)
- `apps/dashboard/src/app/api/v1/retrieve-sdk/route.ts` — `getOpenAI()` lazy getter (OPENAI_API_KEY)

새 라우트에서 외부 클라이언트(OpenAI, Anthropic, Redis 등)를 사용할 때는 반드시 이 패턴을 적용한다.

---

## Python 테스트 인프라

| 파일 | 역할 |
|------|------|
| `apps/api/tests/conftest.py` | `mock_db` (AsyncMock), `make_execute_result(rows)`, `owner_user_id` UUID, `requires_db` skip marker, `async_db_session` (real Postgres + rollback) |

- `async_db_session` fixture: pytest-asyncio 기반, Postgres가 도달 불가능하면 자동 skip.
- `requires_db` 마커: `conftest.py`의 `requires_db = pytest.mark.skipif(not _is_db_available(), ...)`. `pyproject.toml` `[tool.pytest.ini_options]`에 마커 등록됨.
- CI `test-api` 잡은 Postgres service를 기동하므로 `requires_db` 테스트가 CI에서 자동 실행됨.
- 로컬에서 `DATABASE_URL` 없으면 `requires_db` 테스트만 skip — 나머지 mock-based 단위 테스트는 항상 실행됨.

---

_Last updated: 2026-04-26 (CI reporting fix — codecov-action v4→v5; jest collectCoverageFrom expanded to src/**; sonar exclusion conflict fixed; 10 skip-stub tests implemented; 8 new unit test files added) | Maintained by: Claude at end of each implementation session_
