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
