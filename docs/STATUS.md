---
type: status
authority: tier-1
canonical-for: [current-implementation-state, file-map, api-index, db-schema]
last-updated: 2026-04-23
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

**Next:** Phase 4-B 완료 게이트 — ArcanaInsight 자동 진화 1회 달성 (F-4.11)

---

## Database Tables

### Alembic Migration 순서

| Migration | 생성 테이블 |
|-----------|-----------|
| `0001` | `users`, `repos` |
| `0002` | `analyses` |
| `0003` | `inferences`, `harvest_sources`, `chunks`, `collections` |
| `0004` | `verum_jobs`, `worker_heartbeat` |
| `0005` | `generations`, `prompt_variants`, `rag_configs`, `eval_pairs` |
| `0006` | `deployments` |
| `0007` | `users.github_token` 컬럼 |
| `0008` | `generations.status = "pending"` 지원 |
| `0009` | `model_pricing`, `traces`, `spans`, `judge_prompts` |
| `0010` | `experiments` 테이블 + `deployments.experiment_status`, `deployments.current_baseline_variant` |

### 테이블 참조

| 테이블 | 역할 | 단계 |
|--------|------|------|
| `users` | GitHub OAuth 사용자 | Auth |
| `repos` | 연결된 레포지토리 | Auth |
| `analyses` | ANALYZE 결과 JSON | [1] |
| `inferences` | INFER 도메인 JSON | [2] |
| `harvest_sources` | 크롤링 소스 URL | [3] |
| `chunks` | 지식 청크 (pgvector) | [3] |
| `collections` | pgvector 컬렉션 메타 (`embedding_dim` 포함) | [3] |
| `verum_jobs` | 비동기 잡 큐 | Worker |
| `worker_heartbeat` | Worker liveness (id=1 row, 30s 갱신) | Worker |
| `generations` | GENERATE 실행 결과 | [4] |
| `prompt_variants` | 5개 프롬프트 변형 per generation | [4] |
| `rag_configs` | RAG 설정 per generation | [4] |
| `eval_pairs` | 쿼리/답변 평가셋 | [4] |
| `deployments` | 활성 배포 (canary/full/rolled_back) | [5] |
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

Job 등록: `apps/api/src/worker/runner.py` — `_HANDLERS` dict에 모두 등록됨.

`evolve` 잡은 `_HANDLERS`로 등록되는 것 외에 `runner.py`의 `_experiment_loop()` (5분 주기 background task)에 의해 자동 enqueueing됨. idempotency guard(WHERE NOT EXISTS)로 중복 방지.

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
| POST | `/api/v1/harvest/propose` | 크롤링 소스 제안 |
| POST | `/api/v1/harvest/start` | 승인된 소스 크롤링 시작 |
| POST | `/api/v1/retrieve` | 의미론적/하이브리드 검색 |
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

### SDK-facing (X-Verum-API-Key 헤더 = deployment_id UUID)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/v1/chat` | LLM 호출 → 변형 라우팅 |
| GET | `/api/v1/chat/[id]/messages` | 변형 메시지 반환 |
| POST | `/api/v1/traces` | `client.record()` 트레이스 수집 |
| POST | `/api/v1/feedback` | `client.feedback()` 사용자 피드백 |

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

## 핵심 파일 맵

### Python Worker

| 파일 | 역할 |
|------|------|
| `apps/api/src/worker/main.py` | asyncio entrypoint (`python3 -m src.worker.main`) |
| `apps/api/src/worker/runner.py` | LISTEN/NOTIFY 잡 루프 + 핸들러 디스패치 |
| `apps/api/src/worker/handlers/judge.py` | LLM-as-Judge: AsyncAnthropic, 2회 재시도, idempotent |
| `apps/api/src/loop/observe/models.py` | TraceRecord, SpanRecord, DailyMetric Pydantic 모델 |
| `apps/api/src/loop/observe/repository.py` | `insert_trace`, `update_judge_score`, `get_daily_metrics` |
| `apps/api/src/db/models/traces.py` | SQLAlchemy `Trace` ORM 모델 |
| `apps/api/alembic/versions/0009_phase4a_observe.py` | Phase 4-A 스키마 마이그레이션 |
| `apps/api/src/loop/experiment/engine.py` | `compute_winner_score`, `bayesian_confidence`, `check_experiment` |
| `apps/api/src/loop/experiment/models.py` | `VariantStats`, `ExperimentResult` Pydantic 모델 |
| `apps/api/src/loop/experiment/repository.py` | `get_running_experiment`, `aggregate_variant_wins`, `insert_experiment` 등 |
| `apps/api/src/loop/evolve/engine.py` | `promote_winner`, `next_challenger`, `start_next_challenger`, `complete_deployment` |
| `apps/api/src/loop/evolve/repository.py` | `update_deployment_baseline`, `update_traffic_split`, `set_experiment_status` |
| `apps/api/src/worker/handlers/evolve.py` | EVOLVE 잡 핸들러 |
| `apps/api/alembic/versions/0010_phase4b_experiment_evolve.py` | Phase 4-B 스키마 마이그레이션 |

### Next.js Dashboard

| 파일 | 역할 |
|------|------|
| `apps/dashboard/src/lib/db/schema.ts` | Drizzle 테이블 정의 (Alembic SoT → 수동 동기화) |
| `apps/dashboard/src/lib/db/queries.ts` | 읽기 전용 쿼리 (모두 `owner_user_id` 검증) |
| `apps/dashboard/src/lib/db/jobs.ts` | 쓰기 작업 (잡 큐 등록, 상태 변경) |
| `apps/dashboard/src/app/api/v1/traces/route.ts` | POST (SDK 수집) + GET (브라우저 목록) |
| `apps/dashboard/src/app/api/v1/traces/[id]/route.ts` | GET 상세 (소유권 JOIN 검증) |
| `apps/dashboard/src/app/api/v1/metrics/route.ts` | GET 일별 집계 (소유권 검증) |
| `apps/dashboard/src/app/api/v1/feedback/route.ts` | POST 사용자 피드백 |
| `apps/dashboard/src/app/repos/[id]/ObserveSection.tsx` | OBSERVE 섹션 (메트릭 카드 + Recharts 차트 + 테이블) |
| `apps/dashboard/src/components/SpanWaterfall.tsx` | 트레이스 상세 슬라이드오버 패널 |
| `apps/dashboard/src/app/repos/[id]/StagesView.tsx` | OBSERVE 섹션 마운트 (`latestDeploymentId` 존재 시) + EXPERIMENT 섹션 마운트 |
| `apps/dashboard/src/app/api/v1/experiments/route.ts` | GET 실험 목록 (배포별) |
| `apps/dashboard/src/app/api/v1/experiments/[id]/route.ts` | GET 실험 상세 |
| `apps/dashboard/src/app/repos/[id]/ExperimentSection.tsx` | EXPERIMENT 섹션 UI (5초 폴링, Bayesian 신뢰도 바) |

---

## 인증 규칙

| 엔드포인트 | 인증 방식 |
|------------|----------|
| SDK 엔드포인트 (`POST /api/v1/traces`, `POST /api/v1/feedback`, `POST /api/v1/chat`) | `X-Verum-API-Key` 헤더 = deployment_id UUID |
| 브라우저 엔드포인트 (모든 GET, 대시보드 PATCH/POST) | Auth.js JWT 세션 (GitHub OAuth) |
| `/health` | 인증 없음 |

---

## 소유권 검증 패턴

브라우저 엔드포인트는 반드시 `owner_user_id`를 검증한다. 패턴:

- **단일 리소스**: `queries.ts`의 함수에 `userId` 파라미터 → SQL JOIN으로 `repos.owner_user_id = userId`
- **deployment 필터 목록**: 라우트에서 `getDeployment(userId, deploymentId)` 먼저 호출 → 없으면 404
- **트레이스 상세**: `getTraceDetail(userId, traceId)` — traces → deployments → repos JOIN

---

## 알려진 제약 / 다음 Phase로 미룬 것

| 항목 | 이유 | 예정 단계 |
|------|------|----------|
| spans에 실제 프롬프트/응답 텍스트 미저장 | 개인정보 보호; opt-in 방식으로 | Phase 5 |
| 세그먼트별 지연 분석 (TTFT, 스트리밍 청크) | Phase 5 | Phase 5 |
| RAGAS 평가 (faithfulness, answer_relevancy) | Phase 4-B 스코프 외 명시적 제외 | Phase 5 |
| model_pricing 관리 UI | Phase 5; 현재 DB 직접 편집 | Phase 5 |
| 다중 배포 메트릭 비교 | Phase 5 | Phase 5 |
| 실시간 트레이스 스트리밍 (WebSocket/SSE) | Phase 5 | Phase 5 |
| 30일 Abandonment 정책 (experiment_status="abandoned") | Phase 4-B 스코프 외 명시적 제외 | Phase 5 |
| avg_winner_score 실시간 집계 (현재 0.0 stub) | ExperimentResult 모델에 필드 있음, 집계는 미구현 | Phase 5 |

---

## Drizzle Schema 동기화 규칙

Alembic이 스키마 SoT다. Next.js에서 `drizzle-kit pull`이 동작하지 않는 환경(워트리 등)에서는 `apps/dashboard/src/lib/db/schema.ts`에 수동으로 테이블을 추가한다. 추가 시 타입 임포트도 함께 export해야 한다.

---

_Last updated: 2026-04-23 (Phase 4-B complete) | Maintained by: Claude at end of each implementation session_
