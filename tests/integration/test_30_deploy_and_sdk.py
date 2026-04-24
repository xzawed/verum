"""P1 test_30: DEPLOY job + fake-arcana SDK workload.

Waits for GENERATE to complete (from test_20), approves the generation,
triggers DEPLOY, then writes deployment_info.json so fake-arcana can start.
Verifies 200+ traces are recorded within the timeout window.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from sqlalchemy import text

from tests.integration.utils.wait import wait_until

pytestmark = pytest.mark.integration

STATE_DIR = Path(os.environ.get("INTEGRATION_STATE_DIR", "/integration-state"))
TRACES_TARGET = 200
TRACES_TIMEOUT = 300  # seconds — fake-arcana needs to finish 210 calls @ 50ms each ≈ 11s


@pytest.mark.asyncio
async def test_deploy_job_completes(dashboard_client, async_db):
    """Approve the latest generation and wait for DEPLOY job to complete."""
    # Find the latest completed generation
    row = (await async_db.execute(
        text("SELECT id FROM generations WHERE status = 'ready' ORDER BY created_at DESC LIMIT 1")
    )).mappings().first()
    assert row is not None, "No ready generation found — run test_20 first"
    generation_id = str(row["id"])

    # Approve the generation
    resp = await dashboard_client.post(f"/api/v1/generate/{generation_id}/approve")
    assert resp.status_code in (200, 204), f"Approve failed: {resp.status_code} {resp.text}"

    # Trigger DEPLOY
    resp = await dashboard_client.post("/api/v1/deploy", json={"generation_id": generation_id})
    assert resp.status_code == 202, f"Deploy enqueue failed: {resp.status_code} {resp.text}"

    # Wait for DEPLOY job to finish
    async def deploy_done():
        result = (await async_db.execute(
            text(
                "SELECT status, result FROM verum_jobs"
                " WHERE kind = 'deploy' AND status IN ('done', 'failed')"
                " ORDER BY created_at DESC LIMIT 1"
            )
        )).mappings().first()
        return result is not None and result["status"] == "done"

    completed = await wait_until(deploy_done, timeout=60, label="DEPLOY job done")
    assert completed, "DEPLOY job did not complete within 60s"

    # Read deployment_id from job result (api_key is no longer stored in DB — P0-2 fix).
    # The worker wrote api_key to deployment_info.json via VERUM_TEST_MODE path.
    row = (await async_db.execute(
        text(
            "SELECT result FROM verum_jobs"
            " WHERE kind = 'deploy' AND status = 'done'"
            " ORDER BY created_at DESC LIMIT 1"
        )
    )).mappings().first()
    assert row is not None

    result_data = json.loads(row["result"])
    deployment_id = result_data.get("deployment_id")
    assert deployment_id, "deployment_id missing from job result"

    # Security regression check: api_key must NOT be in the DB job result.
    assert "api_key" not in result_data, (
        "api_key leaked into verum_jobs.result — P0-2 regression: "
        "deploy.py must write to /integration-state, not DB"
    )

    # Read deployment_info.json written atomically by the worker (_write_integration_state).
    state_file = STATE_DIR / "deployment_info.json"
    deadline = time.time() + 30
    while not state_file.exists():
        if time.time() > deadline:
            pytest.fail("deployment_info.json not written by worker within 30s")
        time.sleep(0.5)

    info = json.loads(state_file.read_text())
    api_key = info.get("api_key")
    assert api_key, "api_key missing from deployment_info.json — VERUM_TEST_MODE must be '1'"

    # Store in a shared fixture-accessible location for subsequent tests
    (STATE_DIR / "deployment_id.txt").write_text(deployment_id)


@pytest.mark.asyncio
async def test_fake_arcana_records_traces(async_db):
    """Verify fake-arcana recorded 200+ traces for the deployment."""
    deployment_id_file = STATE_DIR / "deployment_id.txt"
    assert deployment_id_file.exists(), "deployment_id.txt not found — run test_deploy_job_completes first"
    deployment_id = deployment_id_file.read_text().strip()

    async def traces_sufficient():
        row = (await async_db.execute(
            text("SELECT COUNT(*) AS n FROM traces WHERE deployment_id = :dep"),
            {"dep": deployment_id},
        )).mappings().first()
        count = int(row["n"]) if row else 0
        return count >= TRACES_TARGET

    reached = await wait_until(
        traces_sufficient,
        timeout=TRACES_TIMEOUT,
        interval=5,
        label=f"traces >= {TRACES_TARGET}",
    )
    assert reached, f"Expected {TRACES_TARGET}+ traces; fake-arcana workload may not have completed"

    # Verify both variants recorded
    rows = (await async_db.execute(
        text(
            "SELECT variant, COUNT(*) AS n FROM traces"
            " WHERE deployment_id = :dep GROUP BY variant"
        ),
        {"dep": deployment_id},
    )).mappings().all()
    variants = {r["variant"]: int(r["n"]) for r in rows}
    assert "original" in variants, f"No baseline traces; found: {variants}"
    assert "variant" in variants, f"No challenger traces; found: {variants}"
    assert variants["original"] >= 90, f"Too few baseline traces: {variants}"
    assert variants["variant"] >= 90, f"Too few challenger traces: {variants}"
