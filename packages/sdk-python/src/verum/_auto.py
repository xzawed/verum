"""Auto-patch OpenAI and Anthropic clients at Python startup.

Loaded automatically via verum-auto.pth installed in site-packages.
No ``import`` statement needed in user application code.

Required environment variables:
    VERUM_API_URL: Base URL of the Verum API.
    VERUM_API_KEY: Your Verum API key.
    VERUM_DEPLOYMENT_ID: Deployment UUID to route all LLM calls through.

Optional:
    VERUM_DISABLED: Set to "1", "true", or "yes" to disable auto-patching.

Integration steps (zero code changes to your service):

1. Add ``verum`` to your requirements.txt (or pyproject.toml dependencies).
2. Set the three environment variables above in your deployment platform.
3. That's it — all OpenAI and Anthropic calls are intercepted automatically.
"""
from __future__ import annotations

import os


def _patch_if_configured() -> None:
    disabled = os.environ.get("VERUM_DISABLED", "").lower()
    if disabled in ("1", "true", "yes"):
        return

    api_url = os.environ.get("VERUM_API_URL", "")
    api_key = os.environ.get("VERUM_API_KEY", "")
    if not api_url and not api_key:
        return

    try:
        import verum.openai  # noqa: F401
    except Exception:  # noqa: BLE001
        pass

    try:
        import verum.anthropic  # noqa: F401
    except Exception:  # noqa: BLE001
        pass


_patch_if_configured()
