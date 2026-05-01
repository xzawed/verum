# Deployment Guide

_Last updated: 2026-04-26_

---

## 현재 인프라 구성

| 컴포넌트 | 서비스 | 상태 |
|---------|--------|------|
| API 서버 | Railway (`verum-production.up.railway.app`) | ✅ 운영 중 |
| 데이터베이스 | Supabase (`sbszcuygbifuuzdctyjq`, us-east-1) | ✅ 운영 중 |
| DB 연결 방식 | Supabase Connection Pooler — Session mode (IPv4) | ✅ |
| 마이그레이션 | Supabase MCP로 직접 적용 (0001~0023) | ✅ 완료 |

### Railway 환경변수 (Variables 탭)

```
DATABASE_URL = postgresql://postgres.<PROJECT_ID>:<PASSWORD>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
ANTHROPIC_API_KEY = ...
VOYAGE_API_KEY = ...
```

> **중요**: username이 `postgres.<PROJECT_ID>` 형태여야 합니다. `postgres`만 쓰면 인증 실패합니다.

---

## SDK Integration Tiers

서비스에 Verum을 통합할 때 세 가지 방식 중 하나를 선택한다. 코드 변경 없는 Tier 0부터 시작하는 것을 권장한다.

| Tier | 코드 변경 | Python | Node.js/TypeScript |
|------|-----------|--------|-------------------|
| **Tier 0** — Zero code changes | 없음 | `pip install verum` + `VERUM_API_URL` + `VERUM_API_KEY` env vars. `.pth` auto-patch가 인터프리터 시작 시 자동 적용 | `npm install @verum/sdk` + 위 두 env var + `NODE_OPTIONS="--require @verum/sdk/auto"` |
| **Tier 1** — One-line import | 1줄 | `import verum.openai` (또는 `verum.anthropic`) at startup | `import "@verum/sdk/openai"` at startup |
| **Tier 2** — Bidirectional | 1줄 + 1 헤더 | Tier 1 + `extra_headers={"x-verum-deployment": DEPLOYMENT_ID}` | Tier 1 + `extra_headers: { "x-verum-deployment": DEPLOYMENT_ID }` |

**Tier 0 최소 환경변수:**

```bash
# Python (Tier 0)
VERUM_API_URL=https://your-verum-instance
VERUM_API_KEY=your-key

# Node.js (Tier 0) — 위 두 변수에 추가
NODE_OPTIONS=--require @verum/sdk/auto
```

**비활성화:** `VERUM_DISABLED=1` (또는 `true`, `yes`) 설정 시 자동 패치가 완전히 비활성화됨.

자세한 내용: [SDK_PYTHON.md](SDK_PYTHON.md) · [SDK_TYPESCRIPT.md](SDK_TYPESCRIPT.md)

---

## 배포 아키텍처

```
GitHub push → Railway CI/CD → Docker build (3-stage: Node.js + Python + runtime)
                                      ↓
                        Node.js PID1 (dumb-init node server.js — Next.js standalone)
                                      ↓
                     Python worker child process (asyncio job runner)
                        (spawned via src/instrumentation.ts → src/worker/spawn.ts)
                                      ↓
                    Supabase Pooler (aws-0-us-east-1.pooler.supabase.com:5432)
                    ← SSL required (auto-detected by session.py + env.py)
```

### 핵심 설계 결정

**Architecture Pivot (2026-04-20)**

FastAPI/Uvicorn은 2026-04-20 Architecture Pivot에서 완전 제거됐습니다.
공개 HTTP는 Next.js가 전담하고, Python은 Node.js가 PID 1로 spawn하는 **asyncio 자식 프로세스**로만 동작합니다.

- **Node.js** (`dumb-init node server.js`) = PID 1. Next.js standalone + SDK API routes + worker spawn 담당
- **Python worker** (`python3 -m src.worker.main`) = child process. asyncio job loop (ANALYZE → EVOLVE 8단계)
- `apps/api/Dockerfile` 삭제 (pre-pivot Python-only 이미지, uvicorn 참조 — 2026-04-26 PR #64에서 제거)
- Railway에서 사용하는 유일한 이미지는 루트 `Dockerfile` (3-stage 통합 이미지)

**alembic 마이그레이션 실행 방식**

- **프로덕션**: Supabase MCP `apply_migration`으로 직접 적용 (알림: Railway 컨테이너에서 alembic auto-upgrade 실행 안 함)
- **로컬 검증**: `make verify-deploy` → 로컬 Docker Postgres (pgvector/pgvector:pg16, 포트 5433)에서 alembic upgrade head 검증

**Railway 대시보드 캐시 문제 (2026-04-26)**

Railway는 서비스를 처음 연결할 때 설정을 캐시하며, `railway.toml`을 새로 추가/변경해도
대시보드에 이전 값이 남아있는 경우가 있습니다. 이 경우 `railway.toml`의 설정이 무시됩니다.

증상:
- Railway 대시보드에 Dockerfile path = `/apps/api/Dockerfile`, Start command = `npm run start`로 표시
- 실제 `railway.toml`은 `dockerfilePath = "Dockerfile"` + `startCommand = "dumb-init node server.js"` 지정
- 결과: 빌드는 성공하지만 런타임에서 `uvicorn` / `src.main:app` 참조 → 실패

해결: Railway 대시보드에서 **직접 수동으로 변경** 필요:
- Settings → Build → Dockerfile Path → `Dockerfile` (루트)
- Settings → Deploy → Start Command → `dumb-init node server.js`

---

## 마이그레이션 관리

### 적용된 마이그레이션 (0001 → 0023)

| 버전 | 내용 | 일자 |
|------|------|------|
| `0001_phase1_analyze` | repos, analyses 테이블 | 2026-04-19 |
| `0002_phase2_infer_harvest` | inferences, harvest_sources, chunks + pgvector + tsvector | 2026-04-19 |
| `0003_voyage_embeddings` | embedding_vec vector(1536) → vector(1024) | 2026-04-19 |
| `0004_users_and_repo_owner` | users 테이블 + repos.owner_user_id FK (Phase 2.5 멀티테넌트) | 2026-04-20 |
| `0005_verum_jobs` | verum_jobs 큐 테이블 (SKIP LOCKED + LISTEN/NOTIFY) | 2026-04-20 |
| `0006_phase3_generate` | generations, prompt_variants, rag_configs, eval_pairs 테이블 | 2026-04-22 |
| `0007_rag_configs_unique` | rag_configs.generation_id UNIQUE 제약 | 2026-04-22 |
| `0008_metric_profile_deployments` | generations.metric_profile + deployments 테이블 | 2026-04-22 |
| `0009_phase4a_observe` | model_pricing, traces, spans, judge_prompts 테이블 | 2026-04-23 |
| `0010_phase4b_experiment_evolve` | experiments 테이블 + deployments 컬럼 확장 | 2026-04-23 |
| `0011_usage_quotas` | usage_quotas 테이블 | 2026-04-23 |
| `0013_unique_evolve_job` | evolve job 중복 방지 partial unique 인덱스 | 2026-04-23 |
| `0014_deployment_api_keys` | deployments.api_key_hash 컬럼 | 2026-04-24 |
| `0015_notify_trigger` | verum_jobs INSERT → pg_notify 트리거 | 2026-04-24 |
| `0016_drop_chunks_embedding_jsonb` | chunks.embedding JSONB 컬럼 제거 (pgvector로 대체) | 2026-04-24 |
| `0017_add_missing_indexes` | inferences + traces 성능 인덱스 | 2026-04-24 |
| `0018_chunks_inference_fk` | chunks.inference_id → inferences.id FK 제약 | 2026-04-24 |
| `0019_sdk_pr_requests` | sdk_pr_requests 테이블 ([5] DEPLOY 자동 PR 생성) | 2026-04-27 |
| `0019_lookup_indexes` | traces + verum_jobs 핫 경로 조회 인덱스 | 2026-04-27 |
| `0020_row_level_security` | 테넌트 소유 테이블 RLS 활성화 | 2026-04-25 |
| `0021_rls_roles` | verum_app 전용 DB 역할 생성 + DML 권한 부여 | 2026-04-25 |
| `0022_force_row_level_security` | FORCE ROW LEVEL SECURITY 적용 | 2026-04-25 |
| `0023_otlp_trace_attrs` | spans.span_attributes JSONB (OTLP raw 속성 저장) | 2026-04-25 |

`alembic_version` 테이블에 `0023_otlp_trace_attrs`로 스탬프됨.

### 새 마이그레이션 추가 절차

1. `apps/api/alembic/versions/` 에 마이그레이션 파일 작성
2. SQL을 Supabase MCP `apply_migration`으로 적용:
   ```
   mcp__claude_ai_Supabase__apply_migration(
     project_id="sbszcuygbifuuzdctyjq",
     name="XXXX_description",
     query="<DDL SQL>"
   )
   ```
3. alembic_version 업데이트:
   ```sql
   UPDATE alembic_version SET version_num = 'XXXX_description';
   ```
4. 코드 배포 (git push → Railway 자동 배포)

> alembic은 로컬 `verify-deploy`에서만 사용. 프로덕션 마이그레이션은 MCP 직접 적용.

---

## Pre-push checklist

`Dockerfile` (root), `apps/api/alembic/`, `apps/api/src/worker/` 변경 전 반드시 실행:

> `apps/api/Dockerfile`은 삭제됨 — Railway는 루트 `Dockerfile` (Node + Python 통합 이미지)만 사용합니다.

```bash
make docker-healthcheck
```

`Dockerfile` 또는 `railway.toml`을 건드린 PR은 push 전에 이 명령으로 로컬 검증 필수.
`pnpm dev`는 standalone을 사용하지 않으므로 이 종류의 버그가 로컬에서 재현되지 않습니다.

스키마/마이그레이션 전용 변경은 추가로:

```bash
make verify-deploy
```

Expected output:
```
--- [1/4] Starting test Postgres (port 5433) ---
--- [2/4] Running alembic with Railway-style URL ---
INFO  [alembic.env] alembic: host=localhost ssl=off
INFO  [alembic.runtime.migration] Running upgrade ...
--- [3/4] Testing /health endpoint ---
{"status": "ok", "version": "0.0.0", "db": "disconnected"}
--- [4/4] Cleanup ---
=== verify-deploy PASSED ===
```

### verify-deploy가 테스트하는 것

1. `postgres://` 형식 URL 변환 — Railway 주입 형식과 동일하게 테스트
2. 모든 마이그레이션이 빈 스키마에서 정상 적용
3. Next.js standalone 빌드 정상 시작 + `/health` 200 응답

---

## 로컬 개발 제약

- **로컬 Python 3.14 vs Railway Python 3.13**: SQLAlchemy ORM 모델 스캔 시
  `typing.Union.__getitem__` 비호환 발생 → alembic 로컬 실패는 Railway 문제 아님
- **Docker 빌드 로컬 실패**: `deb.debian.org` DNS 이슈 → Railway에서는 정상 빌드됨
- **verify-deploy**: 로컬 Docker Postgres(pgvector/pgvector:pg16, 포트 5433) 사용

---

## SSL 자동 감지

`apps/api/alembic/env.py`와 `apps/api/src/db/session.py` 모두:

```python
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "db", "db-test", ""}
_ENGINE_KWARGS = {"connect_args": {"ssl": "require"}} if host not in _LOCAL_HOSTS else {}
```

로컬/Docker 호스트 → SSL 없음, Supabase/Railway 원격 호스트 → `ssl=require` 자동 적용.

---

## Supabase 연결 방식

### 왜 직접 연결(Direct)이 아닌 풀러(Pooler)를 쓰는가

| 방식 | 호스트 | 포트 | 문제 |
|------|--------|------|------|
| Direct (❌) | `db.*.supabase.co` | 5432 | IPv6 주소 → Railway에서 `ENETUNREACH` |
| Pooler Transaction (❌) | `aws-0-us-east-1.pooler.supabase.com` | 6543 | DDL/트랜잭션 세션 상태 미지원 |
| **Pooler Session (✅)** | `aws-0-us-east-1.pooler.supabase.com` | **5432** | IPv4, 세션 유지, 정상 작동 |

---

## 배포 실패 진단

### Railway 로그 확인 순서

1. Railway Dashboard → 서비스 → Deployments → 실패한 배포 클릭
2. **Deploy Logs** 탭 클릭 (Build Logs가 아님 — 런타임 에러는 Deploy Logs에 있음)
3. 로그 맨 아래 예외 메시지 확인

### 공통 에러 및 해결책

| 에러 | 원인 | 해결 |
|------|------|------|
| `OSError: [Errno 101] Network is unreachable` | Direct 연결(IPv6) 사용 | Pooler Session URL로 변경 |
| `The executable 'npm' could not be found` | Railway Start Command가 npm으로 설정됨 | Settings → Deploy → Start Command를 `dumb-init node server.js`로 수동 변경 |
| `asyncpg.InvalidPasswordError` | DATABASE_URL 패스워드 오류 | Supabase Settings → Database → Reset password |
| `Healthcheck failure` — `ENOENT: uvicorn` | `apps/api/Dockerfile` 캐시 + Railway dashboard가 구 설정 유지 | Railway 대시보드에서 Dockerfile path + Start command 수동 수정 |
| `ssl.SSLError` | SSL 감지 미작동 | env.py의 `_LOCAL_HOSTS` 로직 확인 |
| `Module not found: src.main` | apps/api/Dockerfile 또는 구 start command 사용 중 | 루트 `Dockerfile` + `dumb-init node server.js` 확인 |

---

## 배포 이력

### 2026-04-19 (초기 배포)

| 배포 # | 커밋 | 결과 | 실패 원인 | 학습 |
|--------|------|------|----------|------|
| 1 | PR #5 머지 | ❌ | Dockerfile에 anthropic/voyageai 의존성 누락 | pyproject.toml 전체 설치 필요 |
| 2 | `fcae3f3` | ❌ | `postgres://` URL → asyncpg 미지원 | URL prefix 변환 추가 |
| 3~4 | `7b225d7` | ❌ | Supabase Direct IPv6 → `ENETUNREACH` | Pooler Session 전환 필요 |
| 5 | 수동 재배포 | ❌ | Start Command `npm run start` 설정 오류 | Settings에서 Start Command 비워야 함 |
| 6 | `9fef205` | ❌ | alembic이 DB 연결 timeout → uvicorn 미시작 | alembic을 CMD에서 분리해야 함 |
| **7** | **`f72190a`** | **✅** | — | alembic 제거 + MCP 마이그레이션 직접 적용 |

### 2026-04-26 (Railway 구성 수정)

| 배포 # | PR/커밋 | 결과 | 원인/조치 |
|--------|---------|------|----------|
| — | PR #64 | ✅ 빌드 성공 | `apps/api/Dockerfile` 삭제 (pre-pivot 잔재). Railway 대시보드가 캐시로 인해 이 파일을 참조하고 있어 런타임 실패 반복. |
| — | 수동 | ✅ 적용 | Railway 대시보드에서 Dockerfile path → `Dockerfile`, Start Command → `dumb-init node server.js` 직접 수정 |
| — | PR #66 (검증) | ✅ 헬스체크 200 | `{"status":"ok","db":"disconnected"}` 확인. 정상 배포 복구. |

---

## 보안 주의사항

- Railway Variables에 설정된 `DATABASE_URL`에 패스워드가 포함됨 — 스크린샷 공유 금지
- 패스워드 노출 시: Supabase Dashboard → Settings → Database → **Reset database password**
  → Railway Variables의 `DATABASE_URL` 패스워드도 즉시 갱신 필요
