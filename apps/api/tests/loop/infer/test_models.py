"""Tests for INFER stage models and domain taxonomy."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.loop.analyze.models import AnalysisResult, LLMCallSite, PromptTemplate
from src.loop.infer.engine import run_infer
from src.loop.infer.models import (
    DOMAIN_TAXONOMY,
    LANGUAGE_OPTIONS,
    TONE_OPTIONS,
    USER_TYPE_OPTIONS,
    ServiceInference,
    SuggestedSource,
)


def test_domain_taxonomy_has_20_entries() -> None:
    assert len(DOMAIN_TAXONOMY) == 20


def test_domain_taxonomy_contains_tarot() -> None:
    assert "divination/tarot" in DOMAIN_TAXONOMY


def test_domain_taxonomy_has_other() -> None:
    assert "other" in DOMAIN_TAXONOMY


def test_service_inference_round_trip() -> None:
    repo_id = uuid.uuid4()
    analysis_id = uuid.uuid4()
    infer = ServiceInference(
        repo_id=repo_id,
        analysis_id=analysis_id,
        domain="divination/tarot",
        tone="mystical",
        language="ko",
        user_type="consumer",
        confidence=0.92,
        summary="A tarot divination service in Korean.",
        suggested_sources=[
            SuggestedSource(
                url="https://en.wikipedia.org/wiki/Tarot",
                title="Tarot — Wikipedia",
                description="Overview of tarot.",
            )
        ],
    )
    dumped = infer.model_dump(mode="json")
    reloaded = ServiceInference.model_validate(dumped)
    assert reloaded.domain == "divination/tarot"
    assert reloaded.confidence == 0.92
    assert len(reloaded.suggested_sources) == 1


def test_confidence_clamped() -> None:
    with pytest.raises(Exception):
        ServiceInference(
            repo_id=uuid.uuid4(),
            analysis_id=uuid.uuid4(),
            domain="other",
            tone="professional",
            language="en",
            user_type="consumer",
            confidence=1.5,  # out of range
            summary="test",
        )


def test_tone_options_not_empty() -> None:
    assert len(TONE_OPTIONS) >= 5


def test_language_options_includes_ko() -> None:
    assert "ko" in LANGUAGE_OPTIONS


def test_user_type_options_includes_consumer() -> None:
    assert "consumer" in USER_TYPE_OPTIONS


@pytest.fixture
def sample_analysis() -> AnalysisResult:
    return AnalysisResult(
        repo_id=uuid.uuid4(),
        call_sites=[
            LLMCallSite(file_path="a.ts", line=1, sdk="grok", function="generate"),
        ],
        prompt_templates=[
            PromptTemplate(
                id="abc123",
                file_path="a.ts",
                line=5,
                content="You are a tarot reader",
            )
        ],
        model_configs=[],
        language_breakdown={"typescript": 10},
        analyzed_at=datetime.now(tz=timezone.utc),
    )


async def test_run_infer_uses_passed_analysis_id(sample_analysis: AnalysisResult) -> None:
    """run_infer must set analysis_id from the parameter, not from result.repo_id."""
    expected_analysis_id = uuid.uuid4()
    assert expected_analysis_id != sample_analysis.repo_id

    json_resp = '{"domain": "divination/tarot", "tone": "mystical", "language": "ko", "user_type": "consumer", "confidence": 0.9, "summary": "A tarot service."}'

    with patch("src.loop.infer.engine.call_claude", new_callable=AsyncMock, return_value=json_resp):
        result = await run_infer(sample_analysis, analysis_id=expected_analysis_id)

    assert result.analysis_id == expected_analysis_id
    assert result.repo_id == sample_analysis.repo_id
