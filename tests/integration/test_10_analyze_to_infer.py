"""Integration: ANALYZE → INFER pipeline test.

Registers the fixture sample-repo, triggers ANALYZE, waits for INFER to complete,
and asserts the expected DB state.
"""
from __future__ import annotations
import pytest
from sqlalchemy import text
from utils.wait import wait_until
from utils.snapshot import dump
from utils.timeline import build as build_timeline
from pathlib import Path
import os

pytestmark = pytest.mark.integration

FIXTURE_REPO_URL = os.environ.get(
    "FIXTURE_REPO_URL",
    "http://git-http/verum-fixtures/sample-repo.git",
)
ARTIFACTS_DIR = Path(__file__).parent.parent.parent / "artifacts" / "integration"


@pytest.mark.asyncio
async def test_analyze_to_infer_pipeline(dashboard_client, async_db, mock_control):
    """Full ANALYZE → INFER pipeline with fixture repo."""
    # Reset mock call log
    await mock_control.post("/control/reset")

    # 1. Register repo
    register_resp = await dashboard_client.post(
        "/api/repos",
        json={"repo_url": FIXTURE_REPO_URL, "name": "arcana-mini"},
    )
    assert register_resp.status_code in (200, 201), (
        f"Failed to register repo: {register_resp.status_code} {register_resp.text}"
    )
    repo_data = register_resp.json()
    repo_id = repo_data.get("id") or repo_data.get("repo", {}).get("id")
    assert repo_id, f"No repo id in response: {repo_data}"

    # 2. Trigger ANALYZE
    analyze_resp = await dashboard_client.post(f"/api/repos/{repo_id}/analyze")
    assert analyze_resp.status_code in (200, 201, 202), (
        f"Failed to trigger analyze: {analyze_resp.status_code} {analyze_resp.text}"
    )

    # 3. Wait for ANALYZE to complete
    async def analyze_done():
        try:
            r = await async_db.execute(
                text("SELECT status, jsonb_array_length(call_sites) FROM analyses WHERE repo_id = :rid ORDER BY created_at DESC LIMIT 1"),
                {"rid": repo_id},
            )
            row = r.fetchone()
            return row if (row and row[0] == "done") else None
        except Exception:
            await async_db.rollback()
            return None

    analysis_row = await wait_until(analyze_done, timeout=90, label="ANALYZE completion")
    assert analysis_row[1] >= 4, (
        f"Expected >= 4 call sites, got {analysis_row[1]}. "
        "Check tests/fixtures/sample-repo/ — LLM call patterns may not match ANALYZE rules."
    )

    # 4. Wait for INFER to complete
    async def infer_done():
        try:
            r = await async_db.execute(
                text("SELECT status, domain FROM inferences WHERE repo_id = :rid ORDER BY created_at DESC LIMIT 1"),
                {"rid": repo_id},
            )
            row = r.fetchone()
            return row if (row and row[0] == "done") else None
        except Exception:
            await async_db.rollback()
            return None

    infer_row = await wait_until(infer_done, timeout=60, label="INFER completion")
    assert infer_row[1] is not None, "inferences.domain is NULL after INFER"
    assert "tarot" in infer_row[1].lower() or "divination" in infer_row[1].lower(), (
        f"Expected tarot/divination domain, got {infer_row[1]!r}. "
        "Check mock-providers fixtures/anthropic/infer_tarot.json."
    )

    # 5. Verify mock was called
    calls_resp = await mock_control.get("/control/calls")
    calls = calls_resp.json()
    anthropic_calls = [c for c in calls if "anthropic" in c.get("endpoint", "")]
    assert len(anthropic_calls) >= 1, f"Expected >= 1 Anthropic call for INFER, got {calls}"

    # 6. Dump snapshot for diagnostics
    await dump(async_db, ARTIFACTS_DIR / "test_10" / "snapshot.jsonl")

    # Store repo_id for downstream tests via a known DB state
    # (downstream tests re-query the DB)
