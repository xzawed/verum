#!/usr/bin/env python3
"""Validate Anthropic mock fixtures against the anthropic SDK's Message model.

Exits 0 if all fixtures are valid; exits 1 and prints details for any fixture
that no longer matches the current SDK's expected response shape.

Usage:
    python .github/scripts/check_mock_schema.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FIXTURES_DIR = (
    Path(__file__).parent.parent.parent
    / "tests"
    / "integration"
    / "mock-providers"
    / "fixtures"
    / "anthropic"
)

# Keys injected by the mock server for routing — not part of the API response.
_PRIVATE_PREFIXES = ("_",)


def _strip_private(data: dict) -> dict:
    return {k: v for k, v in data.items() if not k.startswith(_PRIVATE_PREFIXES)}


def main() -> int:
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed — run: pip install anthropic")
        return 1

    failures: list[str] = []

    for path in sorted(FIXTURES_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        cleaned = _strip_private(raw)

        try:
            anthropic.types.Message.model_validate(cleaned)
            print(f"OK  {path.name}")
        except Exception as exc:
            failures.append(f"{path.name}: {exc}")
            print(f"DRIFT  {path.name}: {exc}")

    if failures:
        print(f"\n{len(failures)} fixture(s) failed schema validation.")
        print("Update the fixtures to match the current anthropic SDK response shape,")
        print("or pin the SDK version if the change is unintentional.")
        return 1

    count = len(list(FIXTURES_DIR.glob("*.json")))
    print(f"\nAll {count} fixture(s) are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
