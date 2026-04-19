.PHONY: dev api-dev dashboard-dev test test-api test-dashboard test-cov \
        lint type-check db-migrate db-revision db-reset \
        sdk-python-build sdk-ts-build sdk-publish-dry \
        deploy-staging deploy-prod \
        loop-analyze loop-infer loop-harvest loop-full

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
	# TODO: implement in Phase 1 (F-1.3)
	@echo "Usage: make loop-analyze REPO=https://github.com/owner/repo"

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
	# TODO: implement in Phase 0
	@echo "Phase 0: pytest apps/api/tests"

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
	# TODO: implement in Phase 0
	@echo "Phase 0: cd apps/api && alembic upgrade head"

db-revision:
	# TODO: implement in Phase 0
	@echo "Usage: make db-revision m='describe the change'"

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
