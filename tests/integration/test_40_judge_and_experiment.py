"""P1 test_40: JUDGE drain + experiment convergence.

After test_30 records 200+ traces, this test:
1. Waits for JUDGE jobs to drain (all traces get a judge_score)
2. Injects biased judge scores: variant=0.75 (wins), original=0.45 (no win)
3. Waits for the experiment loop to aggregate and converge
4. Verifies experiment winner == 'variant' (challenger variant)

Uses pipeline_state["deployment_id"] set by test_30.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text

from utils.wait import wait_until

pytestmark = pytest.mark.integration

STATE_DIR = Path(os.environ.get("INTEGRATION_STATE_DIR", "/integration-state"))
WIN_THRESHOLD = 0.6  # matches experiments.win_threshold column default
VARIANT_WIN_SCORE = 0.75   # challenger wins: above threshold
BASELINE_LOSE_SCORE = 0.45  # baseline loses: below threshold
JUDGE_DRAIN_TIMEOUT = int(os.environ.get("VERUM_TEST_JUDGE_DRAIN_TIMEOUT", "180"))
EVOLVE_ENQUEUE_TIMEOUT = int(os.environ.get("VERUM_TEST_EVOLVE_ENQUEUE_TIMEOUT", "60"))


@pytest.mark.asyncio
async def test_judge_jobs_drain(async_db, pipeline_state):
    """Wait for all JUDGE jobs to reach done/failed status."""
    deployment_id = pipeline_state.get("deployment_id")
    if not deployment_id:
        pytest.skip("pipeline_state missing deployment_id — test_30 must run first")

    async def judge_drained():
        # All traces for this deployment should have a JUDGE job that finished
        pending = (await async_db.execute(
            text(
                "SELECT COUNT(*) AS n FROM verum_jobs"
                " WHERE kind = 'judge' AND status IN ('queued', 'running')"
            )
        )).mappings().first()
        return int(pending["n"]) == 0

    drained = await wait_until(judge_drained, timeout=JUDGE_DRAIN_TIMEOUT, interval=5, label="JUDGE jobs drained")
    assert drained, "JUDGE jobs did not drain within 180s"

    # Count finished judge jobs
    row = (await async_db.execute(
        text(
            "SELECT COUNT(*) AS n FROM verum_jobs"
            " WHERE kind = 'judge' AND status = 'done'"
        )
    )).mappings().first()
    judge_done = int(row["n"])
    assert judge_done >= 100, f"Expected 100+ done JUDGE jobs, got {judge_done}"

    # Verify traces actually have judge_score populated (not just job status)
    scored = (await async_db.execute(
        text(
            "SELECT COUNT(*) AS n FROM traces"
            " WHERE deployment_id = :dep AND judge_score IS NOT NULL"
        ),
        {"dep": deployment_id},
    )).mappings().first()
    scored_count = int(scored["n"])
    assert scored_count >= 100, (
        f"Expected 100+ traces with judge_score, got {scored_count}. "
        "JUDGE jobs finished but scores may not have been written back."
    )


@pytest.mark.asyncio
async def test_inject_biased_scores_and_converge(async_db, pipeline_state):
    """Inject variant-biased judge scores then wait for experiment loop to converge."""
    deployment_id = pipeline_state.get("deployment_id")
    if not deployment_id:
        pytest.skip("pipeline_state missing deployment_id — test_30 must run first")

    # Inject scores: variant traces win, baseline traces lose
    await async_db.execute(
        text(
            "UPDATE traces SET judge_score = :score"
            " WHERE deployment_id = :dep AND variant = 'variant'"
        ),
        {"dep": deployment_id, "score": VARIANT_WIN_SCORE},
    )
    await async_db.execute(
        text(
            "UPDATE traces SET judge_score = :score"
            " WHERE deployment_id = :dep AND variant = 'original'"
        ),
        {"dep": deployment_id, "score": BASELINE_LOSE_SCORE},
    )
    await async_db.commit()

    # Wait for experiment loop to aggregate and enqueue EVOLVE
    async def evolve_enqueued():
        row = (await async_db.execute(
            text(
                "SELECT COUNT(*) AS n FROM verum_jobs"
                " WHERE kind = 'evolve' AND (payload->>'deployment_id') = :dep"
            ),
            {"dep": deployment_id},
        )).mappings().first()
        return int(row["n"]) > 0

    enqueued = await wait_until(evolve_enqueued, timeout=EVOLVE_ENQUEUE_TIMEOUT, interval=3, label="EVOLVE job enqueued")
    assert enqueued, (
        "EVOLVE job was not enqueued within 60s after score injection. "
        "Check VERUM_EXPERIMENT_INTERVAL_SECONDS and MIN_SAMPLES threshold."
    )

    # Wait for EVOLVE handler to complete and set winner_variant on the experiment.
    # The EVOLVE job is just enqueued above; the worker needs a moment to process it.
    async def winner_set():
        row = (await async_db.execute(
            text(
                "SELECT winner_variant, confidence, status FROM experiments"
                " WHERE deployment_id = :dep AND winner_variant IS NOT NULL"
                " ORDER BY started_at DESC LIMIT 1"
            ),
            {"dep": deployment_id},
        )).mappings().first()
        return row

    exp_row = await wait_until(winner_set, timeout=30, interval=2, label="experiment winner set")
    assert exp_row is not None, "Experiment winner_variant was not set within 30s of EVOLVE enqueue"
    assert exp_row["winner_variant"] == "cot" or exp_row["winner_variant"] == "variant", (
        f"Expected challenger as winner, got: {exp_row['winner_variant']}"
    )
    assert float(exp_row["confidence"]) >= 0.95, (
        f"Confidence too low: {exp_row['confidence']}"
    )
