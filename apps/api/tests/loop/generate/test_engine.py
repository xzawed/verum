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
