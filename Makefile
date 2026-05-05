.PHONY: dev api-dev dashboard-dev test test-api test-dashboard test-e2e e2e-local test-cov \
        lint type-check db-migrate db-revision db-reset \
        sdk-python-build sdk-ts-build sdk-publish-dry \
        deploy-staging deploy-prod \
        loop-analyze loop-infer loop-harvest loop-full \
        docker-healthcheck patch-coverage

# === Railway smoke test (run before ANY push that touches Dockerfile) ===
# Simulates Railway's environment: PORT=8080, ENV HOSTNAME=0.0.0.0.
# Success signal: /health returns 200.
docker-healthcheck:
	@echo "--- [1/3] Building image ---"
	docker build -t verum:smoke .
	@echo "--- [2/3] Starting container (Railway-style: PORT=8080) ---"
	docker run -d --name verum-smoke \
		-p 8080:8080 \
		-e PORT=8080 \
		-e NODE_ENV=production \
		-e AUTH_SECRET=smoke-test-secret \
		-e AUTH_GITHUB_ID=smoke \
		-e AUTH_GITHUB_SECRET=smoke \
		verum:smoke
	@echo "--- Waiting 12s for server + worker startup ---"
	@sleep 12
	@echo "--- [3/3] Checking /health ---"
	@curl -sf http://localhost:8080/health && echo "\n=== docker-healthcheck PASSED ===" \
		|| (echo "\n=== FAILED — check: docker logs verum-smoke ===" && docker logs verum-smoke && exit 1)
	@docker rm -f verum-smoke
	@docker rmi verum:smoke

# === Pre-push coverage check ===
# Approximates Codecov patch analysis locally before pushing.
# Shows line coverage for each source file changed vs origin/main.
# Use before any push that adds new source files to avoid Codecov failure cycles.
patch-coverage:
	@bash scripts/patch-coverage.sh $(or $(BASE),origin/main)

# === Local development ===
dev:
	docker compose up

api-dev:
	cd apps/api && python -m src.worker.main

dashboard-dev:
	cd apps/dashboard && pnpm dev

# === Loop stage runners ===
loop-analyze:
	cd apps/api && python -m src.loop.analyze.cli --repo $(REPO) --branch $(or $(BRANCH),main)

loop-infer:
	cd apps/api && python -m src.loop.infer.cli --analysis-id $(ANALYSIS_ID)

loop-harvest:
	# Phase 2 (F-2.4)
	@echo "Usage: make loop-harvest DOMAIN=divination/tarot"

loop-full:
	# Phase 3 (F-3.10)
	@echo "Usage: make loop-full REPO=https://github.com/owner/repo"

# === Tests ===
test: test-api
	cd apps/dashboard && pnpm build --no-lint

test-api:
	cd apps/api && pytest tests -v

## E2E (Playwright) — requires running dev server
test-e2e:
	cd apps/dashboard && npx playwright test

e2e-local:
	cd apps/dashboard && VERUM_TEST_MODE=1 npx playwright test --headed

test-dashboard: test-e2e

test-cov:
	cd apps/api && pytest tests --cov=src --cov-report=term-missing --cov-report=html

# === Quality ===
lint:
	cd apps/api && ruff check src tests
	cd apps/api && pylint src --fail-under=8.0
	cd apps/api && bandit -r src -q -ll
	cd apps/dashboard && pnpm lint

type-check:
	cd apps/api && python -m mypy src
	cd apps/dashboard && pnpm type-check

# === Database ===
db-migrate:
	cd apps/api && alembic upgrade head

db-revision:
	cd apps/api && alembic revision --autogenerate -m "$(m)"

db-reset:
	@echo "WARNING: This destroys all local data."
	@printf "Type 'yes' to continue: " && read ans && [ "$$ans" = "yes" ] || exit 1
	docker compose down -v
	docker compose up -d db
	@until docker compose exec db pg_isready -U verum -q 2>/dev/null; do sleep 1; done
	$(MAKE) db-migrate
	@echo "=== db-reset complete ==="

# === SDK (Phase 3) ===
sdk-python-build:
	# Phase 3 (F-3.8)
	cd packages/sdk-python && python -m build

sdk-ts-build:
	# Phase 3 (F-3.9)
	cd packages/sdk-typescript && pnpm build

sdk-publish-dry:
	# Phase 3
	cd packages/sdk-python && twine upload --repository testpypi dist/*

# === Deployment ===
deploy-staging:
	@echo "Deploying to Railway (main branch)..."
	railway up

deploy-prod:
	@echo "Production deploy — Railway auto-deploys on push to main."
	@echo "To force a redeploy without a new commit: railway redeploy"
	@echo "Run 'railway redeploy' manually if needed."

# === 통합 테스트 (실운영 환경 모사) ===
# 전제: Docker Desktop 실행 중. prod Dockerfile 그대로 사용.
# 사용법: make integration-up && make integration-test && make integration-down

integration-up:
	mkdir -p artifacts/integration-state && chmod 777 artifacts/integration-state
	docker compose -f docker-compose.integration.yml up -d --wait

integration-smoke:
	pytest tests/integration/test_00_bootstrap.py -m integration -v

integration-test:
	INTEGRATION_STATE_DIR=$(PWD)/artifacts/integration-state \
	pytest tests/integration -m integration -v --maxfail=1

integration-debug:
	KEEP_INTEGRATION_UP=1 pytest tests/integration -m integration -v -s

integration-logs:
	docker compose -f docker-compose.integration.yml logs --tail=200 -f

integration-down:
	docker compose -f docker-compose.integration.yml down -v
