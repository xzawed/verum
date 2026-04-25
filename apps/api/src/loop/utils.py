"""Shared utilities for Verum loop stages."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

_log = logging.getLogger(__name__)


def _repair_truncated_json(text: str) -> Any | None:
    """Best-effort repair for JSON truncated mid-string by an LLM hitting max_tokens.

    Scans backward for each closing-brace position and tries closing any
    unclosed brackets/braces. Returns the parsed object or None on failure.
    Note: brace counting is approximate — unbalanced literal braces inside
    string values can produce incorrect results. The primary defence against
    truncation is an adequate max_tokens budget.
    """
    for pos in range(len(text) - 1, -1, -1):
        if text[pos] not in ('}', ']'):
            continue
        fragment = text[:pos + 1]
        opens = fragment.count('{') - fragment.count('}')
        arr_opens = fragment.count('[') - fragment.count(']')
        if opens < 0 or arr_opens < 0:
            continue
        candidate = fragment + ']' * arr_opens + '}' * opens
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def parse_json_response(text: str) -> Any:
    """Strip optional markdown fences and parse JSON.

    Handles both ` ```json\\n...\\n``` ` and plain JSON strings.
    On parse failure, attempts best-effort repair for responses truncated by
    an LLM max_tokens limit before re-raising the original error.

    Raises:
        json.JSONDecodeError: If the text cannot be parsed as JSON after stripping
            and repair attempts.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        _log.warning("JSON parse failed (%s); attempting truncation repair", exc)
        repaired = _repair_truncated_json(text)
        if repaired is not None:
            _log.warning("Truncation repair succeeded — partial response recovered")
            return repaired
        raise
