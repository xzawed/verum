"""Integration: HARVEST → GENERATE pipeline test.

Picks up where test_10 left off (INFER completed). Waits for HARVEST and GENERATE
to complete via automatic chaining (chain.enqueue_next).

Uses pipeline_state["inference_id"] set by test_10 instead of querying for
the "latest" inference, which breaks when DB contains prior data.
"""
from __future__ import annotations
import pytest
from sqlalchemy import text
from utils.wait import wait_until
from utils.snapshot import dump
import os
from pathlib import Path

pytestmark = pytest.mark.integration

ARTIFACTS_DIR = Path(__file__).parent.parent.parent / "artifacts" / "integration"
HARVEST_TIMEOUT = int(os.environ.get("VERUM_TEST_HARVEST_TIMEOUT", "120"))
GENERATE_TIMEOUT = int(os.environ.get("VERUM_TEST_GENERATE_TIMEOUT", "90"))


@pytest.mark.asyncio
async def test_harvest_pipeline(async_db, mock_control, pipeline_state):
    """HARVEST completes with > 10 chunks stored."""
    inference_id = pipeline_state.get("inference_id")
    assert inference_id, "pipeline_state missing inference_id — test_10 must run first"

    async def harvest_done():
        try:
            r = await async_db.execute(
                text(
                    "SELECT COUNT(*) FROM harvest_sources "
                    "WHERE inference_id = :iid AND status = 'done'"
                ),
                {"iid": inference_id},
            )
            count = r.scalar_one()
            return count if count > 0 else None
        except Exception:
            await async_db.rollback()
            return None

    done_count = await wait_until(harvest_done, timeout=HARVEST_TIMEOUT, label="HARVEST sources done")
    assert done_count >= 1, "No harvest sources completed"

    # Verify chunks were stored with embeddings
    r = await async_db.execute(
        text(
            "SELECT COUNT(*) FROM chunks "
            "WHERE inference_id = :iid AND embedding_vec IS NOT NULL"
        ),
        {"iid": inference_id},
    )
    chunk_count = r.scalar_one()
    assert chunk_count > 10, f"Expected > 10 embedded chunks, got {chunk_count}"

    # Voyage embeddings should have been called
    calls_resp = await mock_control.get("/control/calls")
    calls = calls_resp.json()
    voyage_calls = [c for c in calls if "voyage" in c.get("endpoint", "")]
    assert len(voyage_calls) >= 1, "Expected Voyage embedding calls during HARVEST"

    await dump(async_db, ARTIFACTS_DIR / "test_20_harvest" / "snapshot.jsonl")


@pytest.mark.asyncio
async def test_generate_pipeline(async_db, pipeline_state):
    """GENERATE completes with prompt variants and eval pairs."""
    inference_id = pipeline_state.get("inference_id")
    assert inference_id, "pipeline_state missing inference_id — test_10 must run first"

    async def generate_done():
        try:
            r = await async_db.execute(
                text(
                    "SELECT g.id, g.status FROM generations g "
                    "WHERE g.inference_id = :iid ORDER BY g.created_at DESC LIMIT 1"
                ),
                {"iid": inference_id},
            )
            row = r.fetchone()
            return row if (row and row[1] == "done") else None
        except Exception:
            await async_db.rollback()
            return None

    gen_row = await wait_until(generate_done, timeout=GENERATE_TIMEOUT, label="GENERATE completion")
    pipeline_state["generation_id"] = str(gen_row[0])

    # Check eval pairs were generated
    r = await async_db.execute(
        text(
            "SELECT COUNT(*) FROM eval_pairs ep"
            " JOIN generations g ON g.id = ep.generation_id"
            " WHERE g.inference_id = :iid"
        ),
        {"iid": inference_id},
    )
    pair_count = r.scalar_one()
    assert pair_count >= 1, f"Expected >= 1 eval pairs, got {pair_count}"

    await dump(async_db, ARTIFACTS_DIR / "test_20_generate" / "snapshot.jsonl")

    # Build timeline after P0 pipeline completes
    from utils.timeline import build as build_timeline
    timeline_path = ARTIFACTS_DIR / "timeline.md"
    timeline_text = await build_timeline(async_db, timeline_path)
    print(f"\n{timeline_text}\n")
