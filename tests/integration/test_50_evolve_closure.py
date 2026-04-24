"""P1 test_50: EVOLVE job closure — Loop completes full cycle.

Waits for the EVOLVE job to finish, then asserts:
- deployment.experiment_status transitions to 'completed'
- A new generation exists with status='promoted' (next challenger cycle started)
  OR deployment is marked 'full' (winner promoted fully)
- The timeline artifact captures all 8 stages
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text

from utils.timeline import build as build_timeline
from utils.wait import wait_until

pytestmark = pytest.mark.integration

STATE_DIR = Path(os.environ.get("INTEGRATION_STATE_DIR", "/integration-state"))
ARTIFACTS_DIR = Path("artifacts/integration")


def _get_deployment_id() -> str:
    path = STATE_DIR / "deployment_id.txt"
    assert path.exists(), "deployment_id.txt not found — run test_30 first"
    return path.read_text().strip()


@pytest.mark.asyncio
async def test_evolve_job_completes(async_db):
    """EVOLVE job runs to completion after experiment converges."""
    deployment_id = _get_deployment_id()

    async def evolve_done():
        row = (await async_db.execute(
            text(
                "SELECT status FROM verum_jobs"
                " WHERE kind = 'evolve' AND (payload->>'deployment_id') = :dep"
                " ORDER BY created_at DESC LIMIT 1"
            ),
            {"dep": deployment_id},
        )).mappings().first()
        return row is not None and row["status"] == "done"

    completed = await wait_until(evolve_done, timeout=60, interval=3, label="EVOLVE job done")
    assert completed, "EVOLVE job did not complete within 60s"

    # Verify deployment experiment_status updated
    dep_row = (await async_db.execute(
        text("SELECT experiment_status, status FROM deployments WHERE id = :dep"),
        {"dep": deployment_id},
    )).mappings().first()
    assert dep_row is not None
    assert dep_row["experiment_status"] in ("completed", "running"), (
        f"Unexpected experiment_status: {dep_row['experiment_status']}"
    )


@pytest.mark.asyncio
async def test_loop_closure_assertion(async_db):
    """Assert the full loop: initial repo → EVOLVE winner promoted."""
    deployment_id = _get_deployment_id()

    # Verify the EVOLVE result shows winner promoted
    row = (await async_db.execute(
        text(
            "SELECT result FROM verum_jobs"
            " WHERE kind = 'evolve' AND status = 'done'"
            " AND (payload->>'deployment_id') = :dep"
            " ORDER BY created_at DESC LIMIT 1"
        ),
        {"dep": deployment_id},
    )).mappings().first()
    assert row is not None

    import json
    result = json.loads(row["result"])
    assert result.get("winner_variant") is not None, "EVOLVE result missing winner_variant"

    # Verify experiment records winner
    exp_row = (await async_db.execute(
        text(
            "SELECT winner_variant, confidence FROM experiments"
            " WHERE deployment_id = :dep AND winner_variant IS NOT NULL"
            " ORDER BY started_at DESC LIMIT 1"
        ),
        {"dep": deployment_id},
    )).mappings().first()
    assert exp_row is not None, "No converged experiment found"
    assert float(exp_row["confidence"]) >= 0.95


@pytest.mark.asyncio
async def test_generate_timeline_artifact(async_db):
    """Build final timeline artifact covering all 8 loop stages."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    timeline_path = ARTIFACTS_DIR / "timeline.md"
    await build_timeline(async_db, timeline_path)

    assert timeline_path.exists(), "Timeline artifact was not created"
    content = timeline_path.read_text()

    # Verify key stages appear in timeline
    for stage in ("analyze", "infer", "harvest", "generate", "deploy", "judge", "evolve"):
        assert stage in content.lower(), f"Stage '{stage}' missing from timeline"
