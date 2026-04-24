"""Integration test fixtures.

Assumes `make integration-up` has been run before the test session.
Environment variables:
    VERUM_APP_URL        default http://localhost:8081
    VERUM_DB_URL         default postgresql+asyncpg://verum:verum@localhost:5433/verum
    MOCK_PROVIDERS_URL   default http://localhost:9001
    AUTH_SECRET          JWT signing key (must match verum-app AUTH_SECRET)
"""
from __future__ import annotations
import os
from pathlib import Path
import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

VERUM_APP_URL = os.environ.get("VERUM_APP_URL", "http://localhost:8081")
VERUM_DB_URL = os.environ.get(
    "VERUM_DB_URL",
    "postgresql+asyncpg://verum:verum@localhost:5433/verum",
)
MOCK_PROVIDERS_URL = os.environ.get("MOCK_PROVIDERS_URL", "http://localhost:9001")
ARTIFACTS_DIR = Path(__file__).parent.parent.parent / "artifacts" / "integration"
AUTH_SECRET = os.environ.get("AUTH_SECRET", "integration-test-secret-32chars!!")


# ---------------------------------------------------------------------------
# Session-scoped DB engine (no transaction wrap — tests need persistent data)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_engine():
    engine = create_async_engine(VERUM_DB_URL, pool_size=2, max_overflow=0)
    yield engine
    # teardown happens at process exit


@pytest_asyncio.fixture(scope="function")
async def async_db(db_engine) -> AsyncSession:
    """Non-transactional session. Changes persist for later test steps."""
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


# ---------------------------------------------------------------------------
# dashboard_client — authenticated httpx client via /api/test/login
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def _session_token() -> str:
    """Obtain a test JWT once per session."""
    async with httpx.AsyncClient(base_url=VERUM_APP_URL) as client:
        resp = await client.post("/api/test/login")
        assert resp.status_code == 200, f"/api/test/login returned {resp.status_code}: {resp.text}"
        token = resp.cookies.get("authjs.session-token")
        assert token, f"No authjs.session-token cookie in response. Cookies: {dict(resp.cookies)}"
        return token


@pytest_asyncio.fixture(scope="function")
async def dashboard_client(_session_token) -> httpx.AsyncClient:
    """Authenticated httpx client targeting the Verum dashboard."""
    async with httpx.AsyncClient(
        base_url=VERUM_APP_URL,
        cookies={"authjs.session-token": _session_token},
        timeout=30.0,
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# mock_control — helpers for fault injection
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def mock_control():
    """HTTP client for mock-providers control plane."""
    async with httpx.AsyncClient(base_url=MOCK_PROVIDERS_URL, timeout=10.0) as client:
        await client.post("/control/reset")  # clean slate before each test
        yield client


# ---------------------------------------------------------------------------
# Artifact capture on failure
# ---------------------------------------------------------------------------

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed:
        _save_failure_artifacts(item)


def _save_failure_artifacts(item) -> None:
    """Best-effort artifact dump on test failure."""
    import asyncio, subprocess, json
    test_dir = ARTIFACTS_DIR / item.name
    test_dir.mkdir(parents=True, exist_ok=True)
    # Dump docker compose logs
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", "docker-compose.integration.yml",
             "logs", "--tail=200", "verum-app"],
            capture_output=True, text=True, timeout=15,
        )
        (test_dir / "verum-app.log").write_text(result.stdout + result.stderr)
    except Exception:
        pass
    # Dump mock call log
    try:
        import urllib.request
        with urllib.request.urlopen(f"{MOCK_PROVIDERS_URL}/control/calls", timeout=5) as r:
            (test_dir / "mock-calls.json").write_text(r.read().decode())
    except Exception:
        pass
