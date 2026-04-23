# Verum 테스트 실행 표준 명령

## Make 타겟

```bash
make test          # 전체 (Python API + Dashboard + SDK)
make test-api      # Python worker + loop (apps/api)
make test-dashboard # Jest + Playwright (apps/dashboard)
make test-cov      # 커버리지 포함 전체
```

## Python API (apps/api)

```bash
# 기본
cd apps/api && python -m pytest tests/ -v

# 커버리지 포함
cd apps/api && python -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=xml:coverage.xml

# 특정 모듈만
cd apps/api && python -m pytest tests/loop/infer/ -v

# requires_db 마커 포함 (DATABASE_URL 필요)
DATABASE_URL=postgresql://postgres:password@localhost:5432/verum_test \
  python -m pytest tests/ -v -m requires_db

# requires_db 제외 (DB 없는 환경)
cd apps/api && python -m pytest tests/ -v -m "not requires_db"

# 빠른 smoke
cd apps/api && python -m pytest tests/ -x -q
```

### DATABASE_URL 감지

```bash
# 로컬 개발
export DATABASE_URL=postgresql://postgres:password@localhost:5432/verum_test

# Docker Compose
export DATABASE_URL=postgresql://postgres:password@db:5432/verum

# CI (GitHub Actions)
# .github/workflows/ci.yml의 test-api job에서 postgres service 자동 제공
# DATABASE_URL: postgresql://postgres:postgres@localhost:5432/verum_test
```

## Dashboard TypeScript (apps/dashboard)

```bash
# Jest 단위/통합
cd apps/dashboard && npx jest --no-coverage
cd apps/dashboard && npx jest --coverage  # 커버리지 포함

# 특정 파일
cd apps/dashboard && npx jest src/lib/db/__tests__/queries.test.ts

# watch 모드 (개발 중)
cd apps/dashboard && npx jest --watch

# Playwright E2E
cd apps/dashboard && npx playwright test                    # headless
cd apps/dashboard && npx playwright test --headed           # 브라우저 표시
cd apps/dashboard && npx playwright test e2e/tenancy.spec.ts # 특정 spec
cd apps/dashboard && npx playwright test --reporter=list    # 상세 출력
```

### Playwright 실행 조건

- Next.js dev server 또는 production build 필요
- `playwright.config.ts`의 `webServer` 설정이 자동으로 `next dev` 실행
- `NODE_ENV=test`에서 `/test/login` 엔드포인트 활성화

## SDK Python (packages/sdk-python)

```bash
cd packages/sdk-python && python -m pytest tests/ -v --cov=src
```

## 공통 옵션

| 옵션 | 설명 |
|------|------|
| `-v` | verbose (테스트 이름 표시) |
| `-x` | 첫 실패 시 중지 |
| `-q` | quiet (요약만) |
| `--tb=short` | 짧은 traceback |
| `--no-header` | pytest 헤더 숨김 |
| `-k "keyword"` | 이름으로 필터 |
| `--lf` | 마지막 실패만 재실행 |
