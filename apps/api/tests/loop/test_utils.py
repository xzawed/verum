"""Unit tests for src/loop/utils.py — parse_json_response."""
from __future__ import annotations

import json

import pytest

from src.loop.utils import parse_json_response


def test_plain_json_object() -> None:
    result = parse_json_response('{"key": "value"}')
    assert result == {"key": "value"}


def test_plain_json_array() -> None:
    result = parse_json_response('[1, 2, 3]')
    assert result == [1, 2, 3]


def test_fenced_with_json_language() -> None:
    text = "```json\n{\"domain\": \"tarot\"}\n```"
    result = parse_json_response(text)
    assert result == {"domain": "tarot"}


def test_fenced_without_language() -> None:
    text = "```\n{\"key\": 42}\n```"
    result = parse_json_response(text)
    assert result == {"key": 42}


def test_invalid_json_raises_decode_error() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_json_response("not valid json at all")


def test_invalid_json_in_fence_raises_decode_error() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_json_response("```json\nnot json\n```")


def test_whitespace_padded_json() -> None:
    result = parse_json_response("   \n  {\"x\": 1}  \n  ")
    assert result == {"x": 1}


def test_nested_object() -> None:
    data = {"outer": {"inner": [1, 2, {"deep": True}]}}
    result = parse_json_response(json.dumps(data))
    assert result == data


def test_nested_array_in_fence() -> None:
    text = "```json\n[[1, 2], [3, 4]]\n```"
    result = parse_json_response(text)
    assert result == [[1, 2], [3, 4]]


def test_json_number() -> None:
    result = parse_json_response("3.14")
    assert result == pytest.approx(3.14)


def test_json_boolean() -> None:
    assert parse_json_response("true") is True
    assert parse_json_response("false") is False


def test_json_null() -> None:
    assert parse_json_response("null") is None


# ── Truncation repair ────────────────────────────────────────────────────────

def test_truncated_array_repaired() -> None:
    """JSON array truncated mid-item should be repaired to the last complete item."""
    truncated = '{"variants": [{"type": "a", "content": "hello"}, {"type": "b", "content": "trun'
    result = parse_json_response(truncated)
    assert "variants" in result
    assert len(result["variants"]) >= 1
    assert result["variants"][0]["type"] == "a"


def test_truncated_nested_string_repaired() -> None:
    """JSON truncated mid-string produces at least the complete preceding items."""
    truncated = '{"pairs": [{"query": "q1", "expected": "a1"}, {"query": "q2", "expected": "mid'
    result = parse_json_response(truncated)
    assert "pairs" in result
    assert result["pairs"][0]["query"] == "q1"


def test_completely_garbled_still_raises() -> None:
    """Text with no valid JSON structure at all must still raise JSONDecodeError."""
    with pytest.raises(json.JSONDecodeError):
        parse_json_response("this is just plain text with no json whatsoever !!!")
