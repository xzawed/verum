.PHONY: dev api-dev dashboard-dev test test-api test-dashboard test-cov \
        lint type-check db-migrate db-revision db-reset \
        sdk-python-build sdk-ts-build sdk-publish-dry \
        deploy-staging deploy-prod \
        loop-analyze loop-infer loop-harvest loop-full \
        verify-deploy verify-deploy-clean

# === Pre-deploy verification (run before ANY push touching Dockerfile, alembic/, or db/) ===
# Uses Railway-style postgres:// URL to exercise the full conversion + SSL detection path.
# Requires: Docker running, Python 3.13+ in path.
verify-deploy:
	@echo "--- [1/4] Starting test Postgres (port 5433) ---"
	docker compose -f docker-compose.test.yml up -d
	@until docker exec verum-db-test-1 pg_isready -U verum -q 2>/dev/null; do sleep 1; done
	@echo "--- [2/4] Running alembic with Railway-style URL ---"
	cd apps/api && DATABASE_URL=postgres://verum:verum@localhost:5433/verum alembic upgrade head
	@echo "--- [3/4] Testing /health endpoint ---"
	cd apps/api && DATABASE_URL=postgres://verum:verum@localhost:5433/verum uvicorn src.main:app --host 0.0.0.0 --port 8001 &
	@sleep 4
	curl -sf http://localhost:8001/health | python -m json.tool
	@echo "--- [4/4] Cleanup ---"
	@-pkill -f "uvicorn src.main:app" 2>/dev/null || true
	docker compose -f docker-compose.test.yml down
	@echo "=== verify-deploy PASSED ==="

verify-deploy-clean:
	docker compose -f docker-compose.test.yml down -v
	@-pkill -f "uvicorn src.main:app" 2>/dev/null || true

# === Local development ===
dev:
	docker compose up

api-dev:
	# TODO: implement in Phase 0
	@echo "Phase 0: cd apps/api && uvicorn src.main:app --reload"

dashboard-dev:
	# TODO: implement in Phase 0
	@echo "Phase 0: cd apps/dashboard && npm run dev"

# === Loop stage runners ===
loop-analyze:
	cd apps/api && python -m src.loop.analyze.cli --repo $(REPO) --branch $(or $(BRANCH),main)

loop-infer:
	# TODO: implement in Phase 2 (F-2.1)
	@echo "Usage: make loop-infer ANALYSIS_ID=<uuid>"

loop-harvest:
	# TODO: implement in Phase 2 (F-2.4)
	@echo "Usage: make loop-harvest DOMAIN=divination/tarot"

loop-full:
	# TODO: implement in Phase 3 (F-3.10)
	@echo "Usage: make loop-full REPO=https://github.com/owner/repo"

# === Tests ===
test:
	# TODO: implement in Phase 0
	@echo "Phase 0: pytest apps/api/tests && cd apps/dashboard && npm test"

test-api:
	cd apps/api && pytest tests

test-dashboard:
	# TODO: implement in Phase 0
	@echo "Phase 0: cd apps/dashboard && npx playwright test"

test-cov:
	# TODO: implement in Phase 2 (coverage gate 80%)
	@echo "Phase 2: pytest --cov=src --cov-report=html apps/api/tests"

# === Quality ===
lint:
	# TODO: implement in Phase 0
	@echo "Phase 0: ruff check . && pylint apps/api/src && bandit -r apps/api/src && eslint apps/dashboard/src"

type-check:
	# TODO: implement in Phase 0
	@echo "Phase 0: mypy apps/api/src && cd apps/dashboard && tsc --noEmit"

# === Database ===
db-migrate:
	cd apps/api && alembic upgrade head

db-revision:
	cd apps/api && alembic revision --autogenerate -m "$(m)"

db-reset:
	@echo "WARNING: This destroys all local data."
	# TODO: implement in Phase 0

# === SDK ===
sdk-python-build:
	# TODO: implement in Phase 3 (F-3.8)
	@echo "Phase 3: cd packages/sdk-python && python -m build"

sdk-ts-build:
	# TODO: implement in Phase 3 (F-3.9)
	@echo "Phase 3: cd packages/sdk-typescript && npm run build"

sdk-publish-dry:
	# TODO: implement in Phase 3
	@echo "Phase 3: twine upload --repository testpypi dist/*"

# === Deployment ===
deploy-staging:
	# TODO: implement in Phase 0 (F-0.8)
	@echo "Phase 0: railway up --environment staging"

deploy-prod:
	@echo "Manual approval required before running."
	# TODO: implement in Phase 0 (F-0.8)
