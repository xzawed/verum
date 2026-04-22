"""Tests for the judge handler."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.worker.handlers.judge import _build_judge_prompt, _parse_judge_response


def test_build_judge_prompt_contains_domain():
    prompt = _build_judge_prompt(
        domain="divination/tarot",
        tone="mystical",
        eval_pairs=[
            {"query": "What does The Star mean?", "expected_answer": "Hope and renewal"},
        ],
    )
    assert "divination/tarot" in prompt
    assert "mystical" in prompt
    assert "The Star" in prompt


def test_parse_judge_response_valid():
    raw = json.dumps({"score": 0.82, "reason": "Good answer"})
    score, reason = _parse_judge_response(raw)
    assert abs(score - 0.82) < 0.001
    assert reason == "Good answer"


def test_parse_judge_response_clamped():
    raw = json.dumps({"score": 1.5, "reason": "Over limit"})
    score, _ = _parse_judge_response(raw)
    assert score == 1.0


def test_parse_judge_response_invalid_returns_none():
    score, reason = _parse_judge_response("not json at all")
    assert score is None
    assert reason is None
