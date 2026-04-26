---
type: backlog
authority: tier-2
last-updated: 2026-04-24
generated-by: 6-agent codebase audit
---

# Verum — Technical Backlog

> 6개 에이전트(Python Loop Core, Python Worker/DB, Next.js Dashboard, 테스트, 문서, 인프라/SDK/CI)가 전체 코드베이스를 동시 감사한 결과를 우선순위별로 정리한 일감 목록입니다.
>
> **작업 순서:** P0 → P1 → P2 → P3. 각 항목은 독립적으로 처리 가능합니다.

---

## P0 — 즉시 처리 (보안·정확성)

### ✅ B-001: Dockerfile — 비루트 사용자 실행
**발견 위치:** `Dockerfile` (USER 설정 없음)  
**문제:** 컨테이너가 루트 권한으로 실행됨. 컨테이너 탈출 시 호스트 권한 확보 가능.  
**수정:**
```dockerfile
RUN useradd -m -u 1000 appuser
USER appuser
```
**예상 공수:** 30분  
**처리 완료:** `Dockerfile:63-65` — `useradd -m -u 1000 appuser` + `USER appuser` 적용됨

---

### ✅ B-002: Dockerfile — PID 1 신호 처리 (dumb-init)
**발견 위치:** `Dockerfile:31`  
**문제:** Node.js가 PID 1로 실행되어 SIGTERM/SIGINT 신호를 제대로 전파하지 않음. `docker stop` 시 정상 종료 보장 안됨.  
**수정:** `CMD` 앞에 `dumb-init` 추가
```dockerfile
RUN apt-get install -y dumb-init
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "server.js"]
```
**예상 공수:** 30분  
**처리 완료:** `Dockerfile:36,68` — `dumb-init` 설치 및 `CMD ["dumb-init", "node", "server.js"]` 적용됨

---

### ✅ B-003: 문서 오류 — SDK 메서드 시그니처 불일치 (3건)
**발견 위치:**  
- `docs/STATUS.md:166` — Python SDK `retrieve(query, deployment_id, top_k, hybrid)` → 실제는 `retrieve(query, *, collection_name, top_k=5)` (`deployment_id` 없음)
- `docs/ARCHITECTURE.md:374` — `/v1/retrieve` → 실제 경로는 `/api/v1/retrieve-sdk`
- `docs/ARCHITECTURE.md:454` — TypeScript SDK `new Verum({apiKey, projectId})` → 실제는 `new VerumClient({apiUrl?, apiKey?})` (`projectId` 없음)

**수정:** 각 문서에서 해당 섹션 수정. 사용자가 SDK 문서를 보고 실제 구현과 달라 혼동 가능.  
**예상 공수:** 1시간  
**처리 완료:** 감사 생성 시점과 현재 사이에 이미 수정됨 — STATUS.md, ARCHITECTURE.md 모두 실제 시그니처와 일치 확인

---

### ✅ B-004: 문서 오류 — CLAUDE.md Last Updated 갱신
**발견 위치:** `CLAUDE.md` 최하단 `Last updated: 2026-04-19`  
**문제:** 현재 날짜(2026-04-24)와 35일 차이. 실제 내용과 불일치.  
**수정:** 날짜를 `2026-04-24`로 변경.  
**예상 공수:** 5분  
**처리 완료:** `CLAUDE.md` 말미 — `_Last updated: 2026-04-24_`로 갱신됨

---

## P1 — 높은 우선순위 (다음 작업 단위)

### B-005: 하드코딩 상수 → config.py 중앙화
**발견 위치:** 20+ 곳에 흩어진 상수들  

| 상수 | 현재 위치 | 권장 config.py 키 |
|------|---------|-----------------|
| `MAX_ATTEMPTS = 3` | `runner.py:42` | `JOB_MAX_ATTEMPTS` |
| `STALE_AFTER_MINUTES = 10` | `runner.py:43` | `JOB_STALE_AFTER_MINUTES` |
| `HEARTBEAT_INTERVAL = 30` | `runner.py:44` | `HEARTBEAT_INTERVAL_SECONDS` |
| `timeout=1.0` | `runner.py:325` | `LISTEN_NOTIFY_TIMEOUT_SECONDS` |
| `await asyncio.sleep(5)` | `listener.py:44,49`, `runner.py:335` | `WORKER_RETRY_DELAY_SECONDS` |
| `_TIMEOUT = 30.0` | `harvest/crawler.py:17` | `HARVEST_HTTP_TIMEOUT_SECONDS` |
| `_MAX_CONTENT_BYTES = 2*1024*1024` | `harvest/crawler.py:18` | `HARVEST_MAX_CONTENT_BYTES` |
| `MIN_SAMPLES = 100` | `experiment/engine.py:21` | `EXPERIMENT_MIN_SAMPLES` |
| `CONFIDENCE_THRESHOLD = 0.95` | `experiment/engine.py:22` | `EXPERIMENT_CONFIDENCE_THRESHOLD` |
| `temperature=0.2` | `infer/engine.py:109` | `INFER_LLM_TEMPERATURE` |
| `temperature=0.7` | `generate/engine.py:34` | `GENERATE_LLM_TEMPERATURE` |
| `sem = asyncio.Semaphore(3)` | `handlers/harvest.py:36` | `HARVEST_CONCURRENT_SOURCES` |
| `90_000` (heartbeat threshold) | `lib/db/queries.ts:161` | `WORKER_HEARTBEAT_THRESHOLD_MS` |
| `3000`, `5000` (polling ms) | `StagesView.tsx:36`, `ExperimentSection.tsx:54` | `POLLING_INTERVAL_MS` |

**수정 방향:**
1. `apps/api/src/config.py`에 모든 Python 상수 추가 (env var override 가능)
2. `apps/dashboard/src/lib/constants.ts` 신규 생성하여 TS 상수 중앙화
**예상 공수:** 3-4시간

---

### B-006: Job 상태값 Enum 정의
**발견 위치:** `runner.py`, 각 handler, Alembic 마이그레이션에서 `"queued"`, `"running"`, `"done"`, `"failed"` 문자열 리터럴 20+ 곳 반복  
**문제:** 오타 시 런타임 에러. 상태 추가 시 모든 파일 수동 수정 필요.  
**수정:**
```python
# apps/api/src/worker/job_status.py (신규)
from enum import StrEnum
class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
```
**예상 공수:** 2-3시간 (모든 사용처 교체 포함)

---

### B-007: 스킵된 동시성 테스트 활성화 (rag_configs UNIQUE 제약)
**발견 위치:** `apps/api/tests/loop/generate/test_repository.py:155-163`  
**문제:** `@pytest.mark.skip(reason="rag_configs 테이블에 UNIQUE 제약 없음으로 인한 중복 삽입")` — 실제 버그가 문서화되어 있지만 수정 안 됨.  
**수정:**
1. Alembic 마이그레이션 추가: `rag_configs`에 `(generation_id)` unique constraint 추가
2. 테스트 스킵 마커 제거
**예상 공수:** 1시간

---

### B-008: 통합 테스트 순서 의존성 제거
**발견 위치:** `tests/integration/test_10~test_50` — 각 테스트가 이전 테스트의 DB 상태에 의존  
**문제:** test_10 실패 → test_20~test_50 전부 실패. 병렬 실행 불가. 디버깅 어려움.  
**수정:** 각 테스트 파일이 fixture에서 독립적으로 repo/deployment 생성하도록 리팩터링.  
```python
@pytest_asyncio.fixture
async def fresh_repo(async_db, dashboard_client):
    """각 테스트에서 독립적인 repo 생성"""
    resp = await dashboard_client.post("/api/repos", json={...})
    yield resp.json()["id"]
    # cleanup
```
**예상 공수:** 4-6시간

---

### B-009: wait_until() 폴링 간격 최적화
**발견 위치:** `tests/integration/utils/wait.py:27` — `await asyncio.sleep(interval)`, 기본값 1초  
**문제:** 90초 타임아웃에서 최대 90회 폴링. 타임아웃 직전 실패 시 1초 단위로 지연.  
**수정:** Exponential backoff 적용 (0.1s → 0.2s → 0.5s → 1s → 1s...)  
```python
backoff = min(interval * (1.5 ** attempt_count), 2.0)
await asyncio.sleep(backoff)
```
**예상 공수:** 1시간

---

### ✅ B-010: TypeScript SDK — fetch() 타임아웃 구현
**발견 위치:** `packages/sdk-typescript/src/client.ts:99,110,127,139` — `fetch()` 호출 전부 타임아웃 없음  
**문제:** 서버 무응답 시 영원히 대기. 프로덕션 통합 시 hang 가능.  
**수정:**
```typescript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);
try {
  const resp = await fetch(url, { ...opts, signal: controller.signal });
  clearTimeout(timeoutId);
  ...
} catch (e) {
  if (e instanceof DOMException && e.name === 'AbortError') {
    throw new Error(`Request timed out after ${this.timeoutMs}ms`);
  }
  throw e;
}
```
**예상 공수:** 1-2시간  
**처리 완료:** `packages/sdk-typescript/src/client.ts:60-71` — `timeoutMs` 옵션 및 AbortController 기반 타임아웃 구현됨

---

### ✅ B-011: Heartbeat 연속 실패 처리 강화
**발견 위치:** `apps/api/src/worker/runner.py:143-151` — heartbeat 실패를 warning 로그만 하고 계속 진행  
**문제:** heartbeat 연속 실패 시 worker가 "살아있는 좀비" 상태 — healthcheck는 실패로 표시하지만 job은 계속 처리.  
**수정:**
```python
_heartbeat_failures = 0
MAX_HEARTBEAT_FAILURES = 5  # config로 이동

async def _heartbeat_loop():
    global _heartbeat_failures
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await _update_heartbeat(db)
            _heartbeat_failures = 0
        except Exception as exc:
            _heartbeat_failures += 1
            logger.warning("Heartbeat failed (%d/%d): %s", _heartbeat_failures, MAX_HEARTBEAT_FAILURES, exc)
            if _heartbeat_failures >= MAX_HEARTBEAT_FAILURES:
                logger.critical("Heartbeat max failures reached — shutting down worker")
                os._exit(1)
        await asyncio.sleep(HEARTBEAT_INTERVAL)
```
**예상 공수:** 2시간  
**처리 완료:** `apps/api/src/worker/runner.py:145-172` — `_heartbeat_failures` 카운터, `MAX_HEARTBEAT_FAILURES` env-var 설정, `os._exit(1)` 강제 종료 구현됨

---

### ✅ B-012: 문서 — Worker Job Types에 retrieve 핸들러 추가
**발견 위치:** `docs/STATUS.md:92-103` — 8개 핸들러만 나열, `retrieve` 미포함  
**수정:** STATUS.md 표에 `retrieve` 행 추가:
```
| `retrieve` | `handle_retrieve` | `apps/api/src/worker/handlers/retrieve.py` |
```
**예상 공수:** 10분  
**처리 완료:** `docs/STATUS.md` 현재 버전에 `retrieve` 행 포함됨

---

## P2 — 중간 우선순위 (품질 개선)

### ✅ B-013: Python SDK 재시도 로직 추가
**발견 위치:** `packages/sdk-python/src/verum/client.py:37-75` — `httpx.AsyncClient` 재시도 없음  
**수정:**
```python
transport = httpx.AsyncHTTPTransport(retries=3)
self._client = httpx.AsyncClient(transport=transport, timeout=self.timeout)
```
**예상 공수:** 1시간  
**처리 완료:** `packages/sdk-python/src/verum/client.py:36,42` — `retries` 파라미터 및 `AsyncHTTPTransport(retries=retries)` 구현됨

---

### B-014: 광범위한 except Exception → 구체적 예외
**발견 위치:**
- `harvest/crawler.py:57` — playwright 오류
- `loop/utils.py` 또는 `pipeline.py` 관련
- `prompts.py:222`  

**수정:** 각 catch 블록에서 실제 발생 가능한 예외 타입만 명시  
**예상 공수:** 2시간

---

### B-015: SELECT * → 명시적 컬럼 선택
**발견 위치:**
- `apps/api/src/loop/deploy/repository.py:56` — `SELECT * FROM deployments`
- `apps/api/src/loop/experiment/repository.py:19` — `SELECT * FROM experiments`  

**문제:** 불필요한 컬럼 로드, 향후 컬럼 추가 시 의도치 않은 데이터 반환.  
**예상 공수:** 1시간

---

### B-016: email.py 실제 SMTP 구현
**발견 위치:** `apps/api/src/loop/email.py` — 4개 함수 모두 `logger.info()`만 출력, 실제 발송 없음  
**관련 기능:** 할당량 80% 경고 메일, 할당량 초과 메일, 가입 환영 메일  
**수정:**
1. `config.py`에 SMTP 설정 추가 (`SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`)
2. `aiosmtplib` 또는 외부 서비스(SendGrid) 연동
3. 테스트 추가
**예상 공수:** 3-4시간

---

### B-017: experiment/repository.py 테스트 작성
**발견 위치:** `apps/api/src/loop/experiment/repository.py` — 테스트 파일 없음  
**커버해야 할 함수:** `insert_experiment()`, `update_experiment_aggregate()`, `mark_experiment_converged()`, `aggregate_variant_wins()`  
**예상 공수:** 3-4시간

---

### B-018: deploy/orchestrator.py 테스트 작성
**발견 위치:** `apps/api/src/loop/deploy/orchestrator.py` — 테스트 파일 없음  
**커버해야 할 동작:** 트래픽 분할 + 실험 row 원자적 생성, INSERT 실패 시 예외  
**예상 공수:** 2시간

---

### B-019: Dashboard i18n 누락 문자열 정리
**발견 위치:**
- `app/repos/[id]/ExperimentSection.tsx:66` — `"불러오는 중..."` 한국어 하드코딩
- `app/deploy/[id]/page.tsx:71` — `"DEPLOY — Canary Deployment"` 영어 타이틀 미처리
- `app/repos/[id]/StagesView.tsx` — `"[1] ANALYZE"` 등 섹션 라벨

**수정:** `lib/i18n.ts`에 해당 키 추가 후 `t()` 함수로 교체  
**예상 공수:** 2시간

---

### B-020: CI — Codecov fail_ci_if_error 활성화
**발견 위치:** `ci.yml:79,109,136,238` — 전부 `fail_ci_if_error: false`  
**현재 이유:** "CI 초기 안정화를 위해 false로 유지" (ADR-011)  
**수정 조건:** CI가 2주 이상 안정적으로 녹색 유지되면 `true`로 변경  
**예상 공수:** 10분 (조건 충족 후)

---

### B-021: 의존성 상한 추가
**발견 위치:** Python `pyproject.toml`, TypeScript `package.json`  
**수정:**
```toml
# apps/api/pyproject.toml
anthropic = ">=0.49,<2.0"
httpx = ">=0.27,<1.0"

# packages/sdk-python/pyproject.toml
httpx = ">=0.27,<1.0"
pydantic = ">=2.7,<3.0"
```
**예상 공수:** 30분

---

### B-022: 시간 의존 SDK 테스트 → freezegun 마이그레이션
**발견 위치:** `packages/sdk-python/tests/test_client.py:28` — `time.sleep(0.01)` 캐시 TTL 테스트  
**수정:**
```python
# pip install freezegun
from freezegun import freeze_time

with freeze_time("2026-01-01 00:00:00"):
    client = VerumClient(...)
with freeze_time("2026-01-01 00:01:00"):  # 1분 후
    # 캐시 만료 검증
```
**예상 공수:** 1시간

---

### ✅ B-023: 통합 테스트 타임아웃 환경변수화
**발견 위치:** `tests/integration/test_10*.py:61` (`timeout=90`), `test_20*.py:48` (`timeout=120`) 하드코딩  
**수정:**
```python
ANALYZE_TIMEOUT = int(os.getenv("VERUM_TEST_ANALYZE_TIMEOUT", "120"))
HARVEST_TIMEOUT = int(os.getenv("VERUM_TEST_HARVEST_TIMEOUT", "180"))
```
**예상 공수:** 30분  
**처리 완료:** `tests/integration/test_10_*.py:21-22`, `test_20_*.py:20-21`, `test_30_*.py:26-27`, `test_40_*.py:27-28` — 모든 타임아웃이 `VERUM_TEST_*_TIMEOUT` env var로 환경변수화됨

---

### ✅ B-024: CI — npm 보안 감사 단계 추가
**발견 위치:** `ci.yml` 내 `--no-audit` 플래그로 보안 감사 건너뜀  
**수정:** 별도 `npm audit --audit-level=high` 스텝 추가 (lint 잡에 포함)  
**예상 공수:** 30분  
**처리 완료:** `.github/workflows/ci.yml:53-56` — `npm audit --audit-level=high` 스텝이 sdk-typescript와 dashboard 모두에 추가됨

---

### ✅ B-025: CI — integration.yml checkout 버전 통일
**발견 위치:** `integration.yml:27` — `actions/checkout@v4`, `ci.yml`은 `@v6`  
**수정:** `integration.yml`도 `actions/checkout@v6`으로 통일  
**예상 공수:** 5분  
**처리 완료:** `integration.yml:39` — `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6` (SHA 고정 포함)

---

### ✅ B-026: 중복 import 제거 (infer/engine.py)
**발견 위치:** `apps/api/src/loop/infer/engine.py:116` — `from .models import DOMAIN_TAXONOMY` 중복 (라인 10에서 이미 import)  
**예상 공수:** 5분  
**처리 완료:** 현재 `engine.py:116`은 import 문이 아닌 `if domain not in DOMAIN_TAXONOMY:` 사용문. 감사 이후 이미 제거됨

---

### ✅ B-027: rollback_deployment에서 compute_traffic_split() 재사용
**발견 위치:** `apps/api/src/loop/deploy/repository.py:80` — `{"baseline": 1.0, "variant": 0.0}` 직접 dict 생성  
**수정:** `compute_traffic_split(variant_fraction=0.0)` 호출로 통일  
**예상 공수:** 15분  
**처리 완료:** `repository.py` 현재 `rollback_deployment`에서 `compute_traffic_split(variant_fraction=0.0)` 이미 사용 중

---

## P3 — 낮은 우선순위 (리팩터링·UX 개선)

### B-028: 공통 DB 헬퍼 추출
**발견 위치:** 8곳 이상에서 `await db.execute(text(...))` + `await db.commit()` 반복  
**수정:**
```python
# apps/api/src/db/helpers.py
async def execute_commit(db: AsyncSession, stmt: TextClause, params: dict) -> CursorResult:
    result = await db.execute(stmt, params)
    await db.commit()
    return result
```
**예상 공수:** 2시간 (모든 사용처 교체 포함)

---

### B-029: Dashboard 인라인 스타일 → Tailwind 클래스
**발견 위치:**
- `app/deploy/[id]/page.tsx` — 전체 페이지 인라인 `style` 사용
- `app/generate/[inference_id]/page.tsx` — 동일

**수정:** Tailwind utility class로 교체  
**예상 공수:** 4-6시간

---

### B-030: Playwright E2E 테스트 커버리지 확장
**발견 위치:** 현재 4개 spec 파일만 존재. 대시보드 UI 85% 미커버.  
**추가할 시나리오:**
- Repo 등록 → ANALYZE 잡 대기 → 상태 폴링
- DEPLOY 페이지 — 트래픽 조정 / 롤백 버튼
- 에러 UI (404, 500)
- 메트릭 대시보드 차트 렌더링

**예상 공수:** 6-8시간

---

### B-031: Dashboard 폴링 → 적응형(Exponential backoff)
**발견 위치:** `StagesView.tsx:36` (3초), `ExperimentSection.tsx:54` (5초) — 고정 간격 폴링  
**수정:** 잡 완료 직후 폴링 빠르게, 안정 후 느리게 조정하는 `useAdaptivePolling` hook 구현  
**예상 공수:** 3-4시간

---

### B-032: Mock-providers 스키마 동기화 자동화
**발견 위치:** `tests/integration/mock-providers/` — 실제 Claude API 변경 시 자동 업데이트 없음  
**수정:** 월 1회 실행하는 workflow가 실제 API 스키마와 mock 응답을 비교 후 PR 생성  
**예상 공수:** 2-3시간

---

### B-033: 대시보드 라우트 테스트 팩토리 추상화
**발견 위치:** 17개 라우트에서 동일한 auth/400/404/200 패턴 반복  
**수정:**
```typescript
// apps/dashboard/src/app/api/__tests__/routeFactory.ts
export function createRouteTests(routeModule, opts) {
  it("returns 401 without auth", ...)
  it("returns 400 for invalid body", ...)
  it("returns 200 on success", ...)
}
```
**예상 공수:** 3시간

---

### B-034: Dependabot 설정 추가
**발견 위치:** `.github/dependabot.yml` 미존재  
**수정:**
```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "npm"
    directory: "/apps/dashboard"
    schedule:
      interval: "weekly"
  - package-ecosystem: "pip"
    directory: "/apps/api"
    schedule:
      interval: "weekly"
```
**예상 공수:** 30분

---

### B-035: Integration test — DEPLOY job 60s timeout 조사
**발견 위치:** `tests/integration/test_30_deploy_and_sdk.py::test_deploy_job_completes`  
**문제:** PR #58 머지 후 test_00~test_20(9개) 통과, test_30에서 DEPLOY job이 60초 안에 완료되지 않아 timeout. approve PATCH 호출 자체는 성공하나 worker가 job을 처리하지 못함.  
**배경:** integration test는 2026-04-24부터 실패 중이었으나 test_10(InFailedSQLTransactionError)이 먼저 막혀 test_30에 도달하지 못했음. PR #58로 test_10 수정 후 test_30 문제 노출됨.  
**조사 포인트:**
- `docker-compose.integration.yml` — deploy worker 서비스 설정 확인
- `apps/api/src/loop/deploy/` — deploy handler 로직 및 타임아웃
- `VERUM_TEST_DEPLOY_TIMEOUT` 환경변수 (기본 60s) — CI 환경에서 충분한지 검토
- integration artifact 로그에서 worker 에러 확인  
**예상 공수:** 2~4시간  

---

## 요약 대시보드

> ✅ 항목은 코드에서 처리 완료됨. 미완료 항목만 작업 단위로 처리.

| 우선순위 | 전체 | 미완료 | 완료 |
|---------|------|--------|------|
| **P0** (즉시) | 4개 | 0개 | ✅B-001, ✅B-002, ✅B-003, ✅B-004 |
| **P1** (높음) | 8개 | 5개 (B-005~B-009) | ✅B-010, ✅B-011, ✅B-012 |
| **P2** (중간) | 14개 | 10개 | ✅B-013, ✅B-023, ✅B-024, ✅B-025, ✅B-026, ✅B-027 |
| **P3** (낮음) | 7개 | 7개 | — |
| **신규** | 1개 | 1개 (B-035) | — |
| **합계** | **34개** | **23개 미완료** | **13개 완료** |

> 참고: B-004(CLAUDE.md 날짜 갱신)는 2026-04-24 기준 이미 반영되어 있음.

---

## 처리 불필요 판단

다음은 감사에서 발견됐지만 현재 의도적으로 설계된 것임을 확인하여 백로그에서 제외합니다:

| 항목 | 이유 |
|------|------|
| `api/test/login`의 하드코딩된 테스트 UUID | `VERUM_TEST_MODE=1` 가드로 보호. 테스트 전용으로 의도적 설계 |
| `DB_SSL=disable` | Docker 로컬 Postgres 전용. 프로덕션은 Railway SSL 사용 |
| `fail_ci_if_error: false` (Codecov) | ADR-011 문서화된 결정. CI 안정 후 B-020으로 처리 |
| integration test 하드코딩 시크릿 | 테스트 전용 mock 값임을 명확히 주석 처리함 |
| `SKIP LOCKED` DB 구현 | 현재 구현이 정확함. 단순 주석 문서화로 충분 |

---

_Last updated: 2026-04-25 | Generated from 6-agent codebase audit | Maintained by: Claude at end of audit sessions_
