"""Shared utilities for Verum loop stages."""
from __future__ import annotations

import json
import re
from typing import Any


def parse_json_response(text: str) -> Any:
    """Strip optional markdown fences and parse JSON.

    Handles both ` ```json\\n...\\n``` ` and plain JSON strings.

    Raises:
        json.JSONDecodeError: If the text cannot be parsed as JSON after stripping.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
    return json.loads(text.strip())
