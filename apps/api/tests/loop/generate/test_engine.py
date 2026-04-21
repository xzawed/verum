# apps/api/tests/loop/generate/test_engine.py
import json
import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.loop.generate.engine import _best_prompt, _parse_json, run_generate


def test_best_prompt_picks_longest():
    templates = [
        {"content": "short"},
        {"content": "a" * 200},
        {"content": "medium prompt here"},
    ]
    assert _best_prompt(templates) == "a" * 200


def test_best_prompt_empty_returns_fallback():
    result = _best_prompt([])
    assert "no prompt detected" in result


def test_parse_json_strips_fences():
    raw = '```json\n{"key": "value"}\n```'
    assert _parse_json(raw) == {"key": "value"}


def test_parse_json_plain():
    assert _parse_json('{"x": 1}') == {"x": 1}


@pytest.mark.asyncio
async def test_run_generate_calls_claude_three_times(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            payload = {"variants": [
                {"variant_type": "original", "content": "You are helpful.", "variables": []},
                {"variant_type": "cot", "content": "Think step by step.", "variables": []},
                {"variant_type": "few_shot", "content": "Example:", "variables": []},
                {"variant_type": "role_play", "content": "You are a tarot master.", "variables": []},
                {"variant_type": "concise", "content": "Help.", "variables": []},
            ]}
        elif call_count == 2:
            payload = {"chunking_strategy": "semantic", "chunk_size": 512, "chunk_overlap": 50, "top_k": 5, "hybrid_alpha": 0.8}
        else:
            payload = {"pairs": [{"query": "What is tarot?", "expected_answer": "A card system.", "context_needed": True}]}

        mock = MagicMock()
        mock.content = [MagicMock(text=json.dumps(payload))]
        return mock

    with patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=fake_create)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await run_generate(
            inference_id=str(uuid.uuid4()),
            domain="divination/tarot",
            tone="mystical",
            language="ko",
            user_type="consumer",
            summary="A tarot reading service.",
            prompt_templates=[{"content": "You are a tarot reader.", "variables": []}],
            sample_chunks=["The Tower card represents sudden change."],
        )

    assert call_count == 3
    assert len(result.prompt_variants) == 5
    assert result.rag_config.chunking_strategy == "semantic"
    assert len(result.eval_pairs) == 1


# ── New edge-case tests ──────────────────────────────────────────────────────


def test_parse_json_nested_objects_in_array():
    """_parse_json must handle nested JSON structures (arrays of objects)."""
    raw = '```json\n[{"id": 1, "nested": {"a": true}}, {"id": 2, "nested": {"a": false}}]\n```'
    result = _parse_json(raw)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["nested"]["a"] is True
    assert result[1]["nested"]["a"] is False


def test_parse_json_invalid_raises():
    """_parse_json must propagate json.JSONDecodeError on malformed input."""
    with pytest.raises(json.JSONDecodeError):
        _parse_json("this is not json {broken")


def test_parse_json_whitespace_only_raises():
    """_parse_json on whitespace-only input must raise json.JSONDecodeError."""
    with pytest.raises(json.JSONDecodeError):
        _parse_json("   \n\t  ")


def test_best_prompt_all_empty_content_returns_empty_string():
    """When every template has an empty content field, _best_prompt returns ''
    (the longest among equal-length empty strings). This documents the
    boundary: callers that rely on a non-empty base prompt should check for
    empty strings separately."""
    templates = [{"content": ""}, {"content": ""}, {"content": ""}]
    result = _best_prompt(templates)
    # All are equally "longest" (length 0); max() returns the first one's content.
    assert result == ""


def test_best_prompt_single_template():
    """A single-element list must return that template's content unchanged."""
    templates = [{"content": "You are a helpful assistant."}]
    assert _best_prompt(templates) == "You are a helpful assistant."


@pytest.mark.asyncio
async def test_run_generate_raises_when_api_key_missing(monkeypatch):
    """run_generate must raise RuntimeError immediately when ANTHROPIC_API_KEY
    is absent — no network calls should be made."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        await run_generate(
            inference_id=str(uuid.uuid4()),
            domain="divination/tarot",
            tone="mystical",
            language="ko",
            user_type="consumer",
            summary="A tarot service.",
            prompt_templates=[],
            sample_chunks=[],
        )


@pytest.mark.asyncio
async def test_run_generate_empty_sample_chunks(monkeypatch):
    """run_generate must succeed and use the '(no chunks yet)' placeholder
    when sample_chunks is an empty list (HARVEST stage not yet complete)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    call_count = 0
    captured_prompts: list[str] = []

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        captured_prompts.append(kwargs.get("messages", [{}])[0].get("content", ""))
        if call_count == 1:
            payload = {"variants": [
                {"variant_type": "original", "content": "v1", "variables": []},
                {"variant_type": "cot", "content": "v2", "variables": []},
                {"variant_type": "few_shot", "content": "v3", "variables": []},
                {"variant_type": "role_play", "content": "v4", "variables": []},
                {"variant_type": "concise", "content": "v5", "variables": []},
            ]}
        elif call_count == 2:
            payload = {"chunking_strategy": "recursive", "chunk_size": 512, "chunk_overlap": 50, "top_k": 5, "hybrid_alpha": 0.7}
        else:
            payload = {"pairs": []}

        mock = MagicMock()
        mock.content = [MagicMock(text=json.dumps(payload))]
        return mock

    with patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=fake_create)
        mock_client_cls.return_value = mock_client

        result = await run_generate(
            inference_id=str(uuid.uuid4()),
            domain="code_review",
            tone="professional",
            language="en",
            user_type="developer",
            summary="A code review service.",
            prompt_templates=[{"content": "Review the code.", "variables": []}],
            sample_chunks=[],
        )

    # The RAG and eval prompts must contain the placeholder, not empty string
    assert any("(no chunks yet)" in p for p in captured_prompts[1:])
    assert call_count == 3
    assert len(result.prompt_variants) == 5
    assert result.eval_pairs == []
