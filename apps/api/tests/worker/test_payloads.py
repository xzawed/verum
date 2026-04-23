"""Payload schema validation tests — fast, no I/O."""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from src.worker.payloads import (
    AnalyzePayload,
    DeployPayload,
    EvolvePayload,
    GeneratePayload,
    HarvestPayload,
    InferPayload,
    JudgePayload,
    RetrievePayload,
)

_ID = uuid.uuid4()
_ID2 = uuid.uuid4()


class TestAnalyzePayload:
    def test_valid(self) -> None:
        p = AnalyzePayload(
            repo_url="https://github.com/x/y",
            branch="main",
            repo_id=_ID,
            analysis_id=_ID2,
        )
        assert p.branch == "main"

    def test_missing_field(self) -> None:
        with pytest.raises(ValidationError):
            AnalyzePayload(repo_url="https://github.com/x/y", branch="main", repo_id=_ID)  # type: ignore[call-arg]

    def test_invalid_uuid(self) -> None:
        with pytest.raises(ValidationError):
            AnalyzePayload(
                repo_url="https://github.com/x/y",
                branch="main",
                repo_id="not-a-uuid",  # type: ignore[arg-type]
                analysis_id=_ID2,
            )


class TestInferPayload:
    def test_valid(self) -> None:
        p = InferPayload(analysis_id=_ID, inference_id=_ID2)
        assert p.analysis_id == _ID


class TestHarvestPayload:
    def test_valid(self) -> None:
        p = HarvestPayload(inference_id=_ID, source_ids=[(_ID2, "https://example.com")])
        assert len(p.source_ids) == 1

    def test_empty_sources(self) -> None:
        p = HarvestPayload(inference_id=_ID, source_ids=[])
        assert p.source_ids == []


class TestGeneratePayload:
    def test_valid(self) -> None:
        p = GeneratePayload(inference_id=_ID, generation_id=_ID2)
        assert p.generation_id == _ID2


class TestDeployPayload:
    def test_valid(self) -> None:
        p = DeployPayload(generation_id=_ID)
        assert p.generation_id == _ID


class TestJudgePayload:
    def test_valid(self) -> None:
        p = JudgePayload(trace_id=_ID, deployment_id=_ID2, variant="cot")
        assert p.variant == "cot"

    def test_missing_variant(self) -> None:
        with pytest.raises(ValidationError):
            JudgePayload(trace_id=_ID, deployment_id=_ID2)  # type: ignore[call-arg]


class TestEvolvePayload:
    def test_valid(self) -> None:
        p = EvolvePayload(
            experiment_id=_ID,
            deployment_id=_ID2,
            winner_variant="cot",
            confidence=0.97,
            current_challenger="cot",
        )
        assert p.confidence == pytest.approx(0.97)

    def test_confidence_float(self) -> None:
        p = EvolvePayload(
            experiment_id=_ID,
            deployment_id=_ID2,
            winner_variant="original",
            confidence=1.0,
            current_challenger="cot",
        )
        assert p.confidence == 1.0


class TestRetrievePayload:
    def test_defaults(self) -> None:
        p = RetrievePayload(inference_id=_ID, query="What is the Tower card?")
        assert p.hybrid is True
        assert p.top_k == 5

    def test_override(self) -> None:
        p = RetrievePayload(inference_id=_ID, query="q", hybrid=False, top_k=10)
        assert p.top_k == 10
        assert p.hybrid is False
