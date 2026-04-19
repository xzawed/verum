# Deployment Guide

_Last updated: 2026-04-19_

---

## 현재 인프라 구성

| 컴포넌트 | 서비스 | 상태 |
|---------|--------|------|
| API 서버 | Railway (`verum-production.up.railway.app`) | ✅ 운영 중 |
| 데이터베이스 | Supabase (`sbszcuygbifuuzdctyjq`, us-east-1) | ✅ 운영 중 |
| DB 연결 방식 | Supabase Connection Pooler — Session mode (IPv4) | ✅ |
| 마이그레이션 | Supabase MCP로 직접 적용 (0001~0003) | ✅ 완료 |

### Railway 환경변수 (Variables 탭)

```
DATABASE_URL = postgresql://postgres.<PROJECT_ID>:<PASSWORD>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
ANTHROPIC_API_KEY = ...
VOYAGE_API_KEY = ...
```

> **중요**: username이 `postgres.<PROJECT_ID>` 형태여야 합니다. `postgres`만 쓰면 인증 실패합니다.

---

## 배포 아키텍처

```
GitHub push → Railway CI/CD → Docker build (python:3.13-slim)
                                      ↓
                              uvicorn src.main:app 시작
                                      ↓
                    Supabase Pooler (aws-0-us-east-1.pooler.supabase.com:5432)
                    ← SSL required (auto-detected by session.py + env.py)
```

### 핵심 설계 결정

**alembic은 Dockerfile CMD에서 제거됨 (2026-04-19)**

이유: Railway 컨테이너 → Supabase 직접 연결 시 IPv6 주소로 라우팅되어
`OSError: [Errno 101] Network is unreachable` 발생. 풀러(IPv4)로 전환 후에도
alembic 시작 시 연결 실패로 uvicorn이 시작되지 않는 문제가 반복.

현재 CMD:
```dockerfile
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

**마이그레이션은 Supabase MCP로 별도 적용.**

---

## 마이그레이션 관리

### 현재 적용된 마이그레이션

| 버전 | 내용 | 적용 방법 | 일자 |
|------|------|----------|------|
| `0001_phase1_analyze` | repos, analyses 테이블 | Supabase MCP | 2026-04-19 |
| `0002_phase2_infer_harvest` | inferences, harvest_sources, chunks 테이블 + pgvector + tsvector | Supabase MCP | 2026-04-19 |
| `0003_voyage_embeddings` | embedding_vec vector(1536) → vector(1024) | Supabase MCP | 2026-04-19 |

`alembic_version` 테이블에 `0003_voyage_embeddings`로 스탬프됨.

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

`apps/api/Dockerfile`, `apps/api/alembic/`, `apps/api/src/db/`, `apps/api/src/main.py`
변경 전 반드시 실행:

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
3. uvicorn 시작 + `/health` 200 응답

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
| `The executable 'npm' could not be found` | Railway Start Command가 npm으로 설정됨 | Settings → Deploy → Start Command 비우기 |
| `asyncpg.InvalidPasswordError` | DATABASE_URL 패스워드 오류 | Supabase Settings → Database → Reset password |
| `Healthcheck failure` (alembic 실패) | alembic이 DB 연결 실패 → uvicorn 미시작 | alembic을 CMD에서 제거 (현재 적용됨) |
| `ssl.SSLError` | SSL 감지 미작동 | env.py의 `_LOCAL_HOSTS` 로직 확인 |

---

## 배포 이력 (2026-04-19)

| 배포 # | 커밋 | 결과 | 실패 원인 | 학습 |
|--------|------|------|----------|------|
| 1 | PR #5 머지 | ❌ | Dockerfile에 anthropic/voyageai 의존성 누락 | pyproject.toml 전체 설치 필요 |
| 2 | `fcae3f3` | ❌ | `postgres://` URL → asyncpg 미지원 | URL prefix 변환 추가 |
| 3~4 | `7b225d7` | ❌ | Supabase Direct IPv6 → `ENETUNREACH` | Pooler Session 전환 필요 |
| 5 | 수동 재배포 | ❌ | Start Command `npm run start` 설정 오류 | Settings에서 Start Command 비워야 함 |
| 6 | `9fef205` | ❌ | alembic이 DB 연결 timeout → uvicorn 미시작 | alembic을 CMD에서 분리해야 함 |
| **7** | **`f72190a`** | **✅** | — | alembic 제거 + MCP 마이그레이션 직접 적용 |

---

## 보안 주의사항

- Railway Variables에 설정된 `DATABASE_URL`에 패스워드가 포함됨 — 스크린샷 공유 금지
- 패스워드 노출 시: Supabase Dashboard → Settings → Database → **Reset database password**
  → Railway Variables의 `DATABASE_URL` 패스워드도 즉시 갱신 필요
