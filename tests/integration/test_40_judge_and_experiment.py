"""P1 test_40: JUDGE drain + experiment convergence.

After test_30 records 200+ traces, this test:
1. Waits for JUDGE jobs to drain (all traces get a judge_score)
2. Injects biased judge scores: variant=0.75 (wins), original=0.45 (no win)
3. Waits for the experiment loop to aggregate and converge
4. Verifies experiment winner == 'cot' (challenger variant)
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text

from tests.integration.utils.wait import wait_until

pytestmark = pytest.mark.integration

STATE_DIR = Path(os.environ.get("INTEGRATION_STATE_DIR", "/integration-state"))
WIN_THRESHOLD = 0.6  # matches experiments.win_threshold column default
VARIANT_WIN_SCORE = 0.75   # challenger wins: above threshold
BASELINE_LOSE_SCORE = 0.45  # baseline loses: below threshold


def _get_deployment_id() -> str:
    path = STATE_DIR / "deployment_id.txt"
    assert path.exists(), "deployment_id.txt not found — run test_30 first"
    return path.read_text().strip()


@pytest.mark.asyncio
async def test_judge_jobs_drain(async_db):
    """Wait for all JUDGE jobs to reach done/failed status."""
    deployment_id = _get_deployment_id()

    async def judge_drained():
        # All traces for this deployment should have a JUDGE job that finished
        pending = (await async_db.execute(
            text(
                "SELECT COUNT(*) AS n FROM verum_jobs"
                " WHERE kind = 'judge' AND status IN ('queued', 'running')"
            )
        )).mappings().first()
        return int(pending["n"]) == 0

    drained = await wait_until(judge_drained, timeout=180, interval=5, label="JUDGE jobs drained")
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
async def test_inject_biased_scores_and_converge(async_db):
    """Inject variant-biased judge scores then wait for experiment loop to converge."""
    deployment_id = _get_deployment_id()

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

    enqueued = await wait_until(evolve_enqueued, timeout=60, interval=3, label="EVOLVE job enqueued")
    assert enqueued, (
        "EVOLVE job was not enqueued within 60s after score injection. "
        "Check VERUM_EXPERIMENT_INTERVAL_SECONDS and MIN_SAMPLES threshold."
    )

    # Verify experiment has challenger as winner
    exp_row = (await async_db.execute(
        text(
            "SELECT winner_variant, confidence, status FROM experiments"
            " WHERE deployment_id = :dep ORDER BY started_at DESC LIMIT 1"
        ),
        {"dep": deployment_id},
    )).mappings().first()
    assert exp_row is not None, "No experiment row found"
    assert exp_row["winner_variant"] is not None, f"Experiment has no winner yet; status={exp_row['status']}"
    assert exp_row["winner_variant"] == "cot" or exp_row["winner_variant"] == "variant", (
        f"Expected challenger as winner, got: {exp_row['winner_variant']}"
    )
    assert float(exp_row["confidence"]) >= 0.95, (
        f"Confidence too low: {exp_row['confidence']}"
    )
