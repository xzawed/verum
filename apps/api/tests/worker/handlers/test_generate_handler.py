"""Unit tests for the GENERATE job handler."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.worker.handlers.generate import handle_generate


def _make_inference(inference_id: uuid.UUID):
    m = MagicMock()
    m.id = inference_id
    m.analysis_id = uuid.uuid4()
    m.domain = "tarot_divination"
    m.tone = "mystical"
    m.language = "ko"
    m.user_type = "consumer"
    m.summary = "ArcanaInsight tarot reading service"
    return m


def _make_execute_side_effects(inference):
    """Return AsyncMock side effects for the 3 db.execute calls in handle_generate."""
    inference_result = MagicMock()
    inference_result.scalar_one_or_none.return_value = inference

    analysis_result = MagicMock()
    analysis_result.fetchone.return_value = ([], )

    chunk_result = MagicMock()
    chunk_result.fetchall.return_value = []

    return [inference_result, analysis_result, chunk_result]


def _make_generate_result(variant_count: int = 2, eval_count: int = 3):
    from src.loop.generate.models import GenerateResult, PromptVariant, RagConfig, EvalPair
    return GenerateResult(
        inference_id=uuid.uuid4(),
        prompt_variants=[
            PromptVariant(variant_type="original", content="Hello", variables=[])
            for _ in range(variant_count)
        ],
        rag_config=RagConfig(),
        eval_pairs=[
            EvalPair(query=f"q{i}", expected_answer=f"a{i}", context_needed=True)
            for i in range(eval_count)
        ],
    )


@pytest.mark.asyncio
async def test_handle_generate_happy_path() -> None:
    """Successful GENERATE returns variant and eval counts, commits via save."""
    db = AsyncMock()
    inference_id = uuid.uuid4()
    generation_id = uuid.uuid4()
    inference = _make_inference(inference_id)

    db.execute = AsyncMock(side_effect=_make_execute_side_effects(inference))
    generate_result = _make_generate_result(variant_count=2, eval_count=3)

    with patch("src.worker.handlers.generate.run_generate", new=AsyncMock(return_value=generate_result)), \
         patch("src.worker.handlers.generate.save_generate_result", new=AsyncMock()):

        result = await handle_generate(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "inference_id": str(inference_id),
                "generation_id": str(generation_id),
            },
        )

    assert result["generation_id"] == str(generation_id)
    assert result["variant_count"] == 2
    assert result["eval_pair_count"] == 3


@pytest.mark.asyncio
async def test_handle_generate_raises_when_inference_missing() -> None:
    """ValueError is raised immediately when inference_id is not in the DB."""
    db = AsyncMock()
    inference_id = uuid.uuid4()

    missing_result = MagicMock()
    missing_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=missing_result)

    with patch("src.worker.handlers.generate.run_generate", new=AsyncMock()) as mock_rg, \
         patch("src.worker.handlers.generate.mark_generate_error", new=AsyncMock()) as mock_mge:

        with pytest.raises(ValueError, match=str(inference_id)):
            await handle_generate(
                db=db,
                owner_user_id=uuid.uuid4(),
                payload={
                    "inference_id": str(inference_id),
                    "generation_id": str(uuid.uuid4()),
                },
            )

    mock_rg.assert_not_awaited()
    mock_mge.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_generate_sends_complete_email_on_success() -> None:
    """send_generate_complete_email is called when GENERATE succeeds and user has email."""
    db = AsyncMock()
    inference_id = uuid.uuid4()
    generation_id = uuid.uuid4()
    inference = _make_inference(inference_id)

    email_row = MagicMock()
    email_row.__getitem__ = lambda self, i: ["user@example.com", "https://github.com/owner/repo"][i]
    email_row.__bool__ = lambda self: True

    email_result = MagicMock()
    email_result.fetchone.return_value = email_row

    side_effects = _make_execute_side_effects(inference) + [email_result]
    db.execute = AsyncMock(side_effect=side_effects)
    generate_result = _make_generate_result()

    with patch("src.worker.handlers.generate.run_generate", new=AsyncMock(return_value=generate_result)), \
         patch("src.worker.handlers.generate.save_generate_result", new=AsyncMock()), \
         patch("src.worker.handlers.generate.send_generate_complete_email", new=AsyncMock()) as mock_email:

        await handle_generate(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "inference_id": str(inference_id),
                "generation_id": str(generation_id),
            },
        )

    mock_email.assert_awaited_once()
    call_kwargs = mock_email.await_args.kwargs
    assert call_kwargs["user_email"] == "user@example.com"
    assert call_kwargs["domain"] == "tarot_divination"


@pytest.mark.asyncio
async def test_handle_generate_skips_email_when_no_user_email() -> None:
    """No email is sent when the user has no email address on file."""
    db = AsyncMock()
    inference_id = uuid.uuid4()
    generation_id = uuid.uuid4()
    inference = _make_inference(inference_id)

    no_email_row = MagicMock()
    no_email_row.__getitem__ = lambda self, i: [None, "https://github.com/owner/repo"][i]
    no_email_row.__bool__ = lambda self: True

    email_result = MagicMock()
    email_result.fetchone.return_value = no_email_row

    side_effects = _make_execute_side_effects(inference) + [email_result]
    db.execute = AsyncMock(side_effect=side_effects)
    generate_result = _make_generate_result()

    with patch("src.worker.handlers.generate.run_generate", new=AsyncMock(return_value=generate_result)), \
         patch("src.worker.handlers.generate.save_generate_result", new=AsyncMock()), \
         patch("src.worker.handlers.generate.send_generate_complete_email", new=AsyncMock()) as mock_email:

        await handle_generate(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "inference_id": str(inference_id),
                "generation_id": str(generation_id),
            },
        )

    mock_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_generate_calls_mark_error_when_run_generate_fails() -> None:
    """mark_generate_error is called and exception re-raises when run_generate fails."""
    db = AsyncMock()
    inference_id = uuid.uuid4()
    generation_id = uuid.uuid4()
    inference = _make_inference(inference_id)

    db.execute = AsyncMock(side_effect=_make_execute_side_effects(inference))

    with patch("src.worker.handlers.generate.run_generate", side_effect=RuntimeError("LLM timeout")), \
         patch("src.worker.handlers.generate.mark_generate_error", new=AsyncMock()) as mock_mge:

        with pytest.raises(RuntimeError, match="LLM timeout"):
            await handle_generate(
                db=db,
                owner_user_id=uuid.uuid4(),
                payload={
                    "inference_id": str(inference_id),
                    "generation_id": str(generation_id),
                },
            )

    mock_mge.assert_awaited_once()
    assert mock_mge.await_args.args[1] == generation_id
