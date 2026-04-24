"""Bootstrap smoke — verifies the integration stack is healthy before running Loop tests."""
import pytest
import httpx
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_verum_health(dashboard_client):
    """verum-app /health returns 200."""
    resp = await dashboard_client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_mock_providers_health():
    """mock-providers /health returns 200."""
    async with httpx.AsyncClient(base_url="http://localhost:9001") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_mock_providers_call_log_starts_empty(mock_control):
    """After reset, call log is empty."""
    resp = await mock_control.get("/control/calls")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_db_accessible(async_db):
    """Can query database."""
    result = await async_db.execute(text("SELECT 1"))
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_verum_jobs_table_exists(async_db):
    """verum_jobs table is present (migrations applied)."""
    result = await async_db.execute(
        text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'verum_jobs'")
    )
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_test_login_bypass(dashboard_client):
    """Authenticated client can reach a protected route."""
    resp = await dashboard_client.get("/api/repos")
    # 200 (empty list) or 404 but NOT 401/307 — confirms auth bypass works
    assert resp.status_code in (200, 404), f"Expected 200/404, got {resp.status_code}"
