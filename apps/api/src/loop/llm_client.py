"""Shared Anthropic async client for all Verum loop stages."""
from __future__ import annotations

import os

import anthropic


def _get_client() -> anthropic.AsyncAnthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.AsyncAnthropic(api_key=api_key)


async def call_claude(
    model: str,
    max_tokens: int,
    user: str,
    *,
    system: str = "",
    temperature: float = 0.0,
) -> str:
    """Call Claude and return the first text block from the response.

    Args:
        model: Model ID (e.g. "claude-sonnet-4-6").
        max_tokens: Maximum tokens to generate.
        user: User message content.
        system: Optional system prompt. Omitted if empty.
        temperature: Sampling temperature. Defaults to 0.0 (deterministic).

    Returns:
        Text from the first content block.

    Raises:
        RuntimeError: If ANTHROPIC_API_KEY is not set.
        anthropic.APIError: On API failure.
    """
    client = _get_client()
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        kwargs["system"] = system
    if temperature > 0:
        kwargs["temperature"] = temperature

    msg = await client.messages.create(**kwargs)
    return next((block.text for block in msg.content if hasattr(block, "text")), "")
