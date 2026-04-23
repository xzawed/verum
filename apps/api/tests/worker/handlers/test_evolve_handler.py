"""Tests for the EVOLVE job handler."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.worker.handlers.evolve import handle_evolve


def _make_payload(
    *,
    experiment_id: uuid.UUID | None = None,
    deployment_id: uuid.UUID | None = None,
    winner_variant: str = "cot",
    confidence: float = 0.97,
    current_challenger: str = "cot",
) -> dict:
    return {
        "experiment_id": str(experiment_id or uuid.uuid4()),
        "deployment_id": str(deployment_id or uuid.uuid4()),
        "winner_variant": winner_variant,
        "confidence": confidence,
        "current_challenger": current_challenger,
    }


# ---------------------------------------------------------------------------
# Happy path: next round exists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_evolve_promotes_winner_and_starts_next_round() -> None:
    """When start_next_challenger returns True, complete_deployment is not called."""
    db = AsyncMock()
    payload = _make_payload(winner_variant="cot", current_challenger="cot")

    with (
        patch(
            "src.worker.handlers.evolve.promote_winner",
            new_callable=AsyncMock,
        ) as mock_promote,
        patch(
            "src.worker.handlers.evolve.start_next_challenger",
            return_value=True,
            new_callable=AsyncMock,
        ) as mock_start,
        patch(
            "src.worker.handlers.evolve.complete_deployment",
            new_callable=AsyncMock,
        ) as mock_complete,
    ):
        result = await handle_evolve(db, uuid.uuid4(), payload)

    mock_promote.assert_awaited_once()
    mock_start.assert_awaited_once()
    mock_complete.assert_not_awaited()

    assert result["next_round_started"] is True
    assert result["winner_variant"] == "cot"
    assert "deployment_id" in result


# ---------------------------------------------------------------------------
# Final round: no more challengers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_evolve_completes_when_no_next_round() -> None:
    """When start_next_challenger returns False, complete_deployment is called."""
    db = AsyncMock()
    payload = _make_payload(winner_variant="concise", current_challenger="concise")

    with (
        patch("src.worker.handlers.evolve.promote_winner", new_callable=AsyncMock),
        patch(
            "src.worker.handlers.evolve.start_next_challenger",
            return_value=False,
            new_callable=AsyncMock,
        ),
        patch(
            "src.worker.handlers.evolve.complete_deployment",
            new_callable=AsyncMock,
        ) as mock_complete,
    ):
        result = await handle_evolve(db, uuid.uuid4(), payload)

    mock_complete.assert_awaited_once()
    assert result["next_round_started"] is False


# ---------------------------------------------------------------------------
# Return dict structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_evolve_return_dict_contains_required_keys() -> None:
    """Return value always has deployment_id, winner_variant, next_round_started."""
    db = AsyncMock()
    deployment_id = uuid.uuid4()
    payload = _make_payload(deployment_id=deployment_id, winner_variant="few_shot")

    with (
        patch("src.worker.handlers.evolve.promote_winner", new_callable=AsyncMock),
        patch(
            "src.worker.handlers.evolve.start_next_challenger",
            return_value=True,
            new_callable=AsyncMock,
        ),
        patch("src.worker.handlers.evolve.complete_deployment", new_callable=AsyncMock),
    ):
        result = await handle_evolve(db, uuid.uuid4(), payload)

    assert result["deployment_id"] == str(deployment_id)
    assert result["winner_variant"] == "few_shot"
    assert isinstance(result["next_round_started"], bool)


# ---------------------------------------------------------------------------
# Rollback: promote_winner failure prevents start_next_challenger
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_evolve_propagates_promote_winner_error() -> None:
    """If promote_winner raises, start_next_challenger is never called."""
    db = AsyncMock()

    with (
        patch(
            "src.worker.handlers.evolve.promote_winner",
            side_effect=RuntimeError("DB write failed"),
        ),
        patch(
            "src.worker.handlers.evolve.start_next_challenger",
            new_callable=AsyncMock,
        ) as mock_start,
    ):
        with pytest.raises(RuntimeError, match="DB write failed"):
            await handle_evolve(db, uuid.uuid4(), _make_payload())

    mock_start.assert_not_awaited()
