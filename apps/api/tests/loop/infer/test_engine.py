"""Unit tests for the INFER engine (src.loop.infer.engine)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

import src.config as cfg
from src.loop.analyze.models import AnalysisResult
from src.loop.infer.engine import run_infer
from src.loop.infer.models import DOMAIN_TAXONOMY, ServiceInference


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_analysis_result() -> AnalysisResult:
    return AnalysisResult(
        repo_id=uuid.uuid4(),
        call_sites=[],
        prompt_templates=[],
        model_configs=[],
        language_breakdown={"python": 100},
        analyzed_at=datetime.now(timezone.utc),
    )


def _valid_json_response(domain: str = "divination/tarot") -> str:
    return json.dumps({
        "domain": domain,
        "tone": "mystical",
        "language": "ko",
        "user_type": "consumer",
        "confidence": 0.95,
        "summary": "Tarot reading service for Korean users.",
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_run_infer_returns_valid_service_inference(
    sample_analysis_result: AnalysisResult,
) -> None:
    """run_infer returns a fully-populated ServiceInference for a known domain."""
    with patch(
        "src.loop.infer.engine.call_claude",
        new=AsyncMock(return_value=_valid_json_response("divination/tarot")),
    ):
        result = await run_infer(sample_analysis_result, analysis_id=uuid.uuid4())

    assert isinstance(result, ServiceInference)
    assert result.domain == "divination/tarot"
    assert result.tone == "mystical"
    assert result.language == "ko"
    assert result.user_type == "consumer"
    assert result.confidence == pytest.approx(0.95)
    assert "Tarot" in result.summary
    assert result.repo_id == sample_analysis_result.repo_id


async def test_run_infer_clamps_unknown_domain_to_other(
    sample_analysis_result: AnalysisResult,
) -> None:
    """Domains not in DOMAIN_TAXONOMY are clamped to 'other'."""
    unknown_domain = "not-a-real-domain/xyz"
    assert unknown_domain not in DOMAIN_TAXONOMY

    with patch(
        "src.loop.infer.engine.call_claude",
        new=AsyncMock(return_value=_valid_json_response(unknown_domain)),
    ):
        result = await run_infer(sample_analysis_result, analysis_id=uuid.uuid4())

    assert result.domain == "other"


async def test_run_infer_populates_suggested_sources_for_tarot(
    sample_analysis_result: AnalysisResult,
) -> None:
    """Tarot domain produces non-empty suggested_sources list."""
    with patch(
        "src.loop.infer.engine.call_claude",
        new=AsyncMock(return_value=_valid_json_response("divination/tarot")),
    ):
        result = await run_infer(sample_analysis_result, analysis_id=uuid.uuid4())

    assert len(result.suggested_sources) > 0
    urls = [s.url for s in result.suggested_sources]
    assert any("tarot" in u.lower() or "wikipedia" in u.lower() for u in urls)


async def test_run_infer_raises_on_invalid_json(
    sample_analysis_result: AnalysisResult,
) -> None:
    """json.JSONDecodeError (or subclass) is raised when call_claude returns non-JSON."""
    with patch(
        "src.loop.infer.engine.call_claude",
        new=AsyncMock(return_value="not json at all"),
    ):
        with pytest.raises(json.JSONDecodeError):
            await run_infer(sample_analysis_result, analysis_id=uuid.uuid4())


async def test_run_infer_uses_correct_model(
    sample_analysis_result: AnalysisResult,
) -> None:
    """call_claude is invoked with the model from src.config.INFER_MODEL."""
    captured: dict = {}

    async def _fake_call_claude(model, max_tokens, user_msg, **kwargs):
        captured["model"] = model
        return _valid_json_response()

    with patch("src.loop.infer.engine.call_claude", side_effect=_fake_call_claude):
        await run_infer(sample_analysis_result, analysis_id=uuid.uuid4())

    assert captured["model"] == cfg.INFER_MODEL


async def test_run_infer_empty_call_sites_still_works(
    sample_analysis_result: AnalysisResult,
) -> None:
    """AnalysisResult with no call sites or prompt templates completes without error."""
    assert sample_analysis_result.call_sites == []
    assert sample_analysis_result.prompt_templates == []

    with patch(
        "src.loop.infer.engine.call_claude",
        new=AsyncMock(return_value=_valid_json_response("other")),
    ):
        result = await run_infer(sample_analysis_result, analysis_id=uuid.uuid4())

    assert result.domain == "other"
    assert isinstance(result, ServiceInference)
