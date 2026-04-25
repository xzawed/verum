"""Tests for the verum.openai monkey-patch module.

These tests verify the patching behaviour without requiring a live OpenAI
account. The openai SDK is mocked at the class level before the patch is
applied so we can assert on call counts and argument mutations.
"""
from __future__ import annotations

import importlib
import os
import sys
import types
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers for building minimal openai stubs
# ---------------------------------------------------------------------------


def _make_openai_stub() -> types.ModuleType:
    """Build a minimal openai module stub and register it in sys.modules.

    Provides just enough structure for ``verum.openai._patch_openai()`` to
    work without the real openai package installed:

    * ``openai.resources.chat.completions.Completions``
    * ``openai.resources.chat.completions.AsyncCompletions``
    """
    # Remove any previously registered stub to start fresh.
    _cleanup_openai_stub()

    openai_mod = types.ModuleType("openai")
    resources_mod = types.ModuleType("openai.resources")
    chat_mod = types.ModuleType("openai.resources.chat")
    completions_mod = types.ModuleType("openai.resources.chat.completions")

    # Minimal Completions class with a real callable ``create``.
    class Completions:
        def create(self, *args: Any, **kwargs: Any) -> MagicMock:  # noqa: ANN401
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=10, completion_tokens=5),
            )

    class AsyncCompletions:
        async def create(self, *args: Any, **kwargs: Any) -> MagicMock:  # noqa: ANN401
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=10, completion_tokens=5),
            )

    completions_mod.Completions = Completions  # type: ignore[attr-defined]
    completions_mod.AsyncCompletions = AsyncCompletions  # type: ignore[attr-defined]
    chat_mod.completions = completions_mod  # type: ignore[attr-defined]
    resources_mod.chat = chat_mod  # type: ignore[attr-defined]
    openai_mod.resources = resources_mod  # type: ignore[attr-defined]

    sys.modules["openai"] = openai_mod
    sys.modules["openai.resources"] = resources_mod
    sys.modules["openai.resources.chat"] = chat_mod
    sys.modules["openai.resources.chat.completions"] = completions_mod

    return openai_mod


def _cleanup_openai_stub() -> None:
    """Remove openai stub and verum.openai from sys.modules."""
    for key in list(sys.modules.keys()):
        if key == "openai" or key.startswith("openai.") or key == "verum.openai":
            del sys.modules[key]


def _fresh_import_verum_openai() -> types.ModuleType:
    """Import (or re-import) verum.openai with a clean _PATCHED state."""
    # Remove old module so the top-level _patch_openai() runs again.
    for key in list(sys.modules.keys()):
        if key == "verum.openai":
            del sys.modules[key]

    mod = importlib.import_module("verum.openai")
    return mod


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestPatchIdempotent(unittest.TestCase):
    """Verify that importing verum.openai twice does not double-wrap."""

    def setUp(self) -> None:
        _make_openai_stub()
        # Reset the patch flag on the module if it was already imported.
        if "verum.openai" in sys.modules:
            del sys.modules["verum.openai"]

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    def test_double_import_is_idempotent(self) -> None:
        """Calling _patch_openai() when already patched is a no-op.

        The idempotency guarantee is provided by the _PATCHED flag: if it is
        True, the function returns immediately without touching Completions.
        We verify this by capturing the wrapped create after the first patch,
        setting _PATCHED=True manually, calling _patch_openai() again, and
        confirming the function object did NOT change.
        """
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        mod = _fresh_import_verum_openai()
        first_create = comp_mod.Completions.create

        # _PATCHED is True at this point — calling _patch_openai again is a no-op.
        self.assertTrue(mod._PATCHED)
        mod._patch_openai()

        # create must be the same object — no second wrapping occurred.
        self.assertIs(comp_mod.Completions.create, first_create)


class TestPassThroughNoDeploymentId(unittest.TestCase):
    """When VERUM_DEPLOYMENT_ID is absent the original create is called unchanged."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ.pop("VERUM_DEPLOYMENT_ID", None)
        os.environ.pop("VERUM_API_URL", None)
        os.environ.pop("VERUM_API_KEY", None)

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    def test_no_deployment_id_calls_original(self) -> None:
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        call_record: list[dict[str, Any]] = []
        original_create = comp_mod.Completions.create

        def recording_create(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            call_record.append({"args": args, "kwargs": kwargs})
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=10, completion_tokens=5),
            )

        comp_mod.Completions.create = recording_create  # type: ignore[method-assign]

        _fresh_import_verum_openai()

        instance = comp_mod.Completions()
        instance.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "hello"}],
        )

        self.assertEqual(len(call_record), 1)
        self.assertEqual(call_record[0]["kwargs"]["messages"][0]["content"], "hello")

        comp_mod.Completions.create = original_create  # type: ignore[method-assign]


class TestBaselineWhenTrafficSplitZero(unittest.TestCase):
    """When the resolver returns traffic_split=0 the original messages are used."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-test-001"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        os.environ.pop("VERUM_DEPLOYMENT_ID", None)
        os.environ.pop("VERUM_API_URL", None)
        os.environ.pop("VERUM_API_KEY", None)

    def test_baseline_messages_pass_through(self) -> None:
        original_messages = [{"role": "user", "content": "tarot reading"}]
        received_messages: list[Any] = []

        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        def spy_create(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            received_messages.extend(kwargs.get("messages", []))
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=5, completion_tokens=3),
            )

        comp_mod.Completions.create = spy_create  # type: ignore[method-assign]

        mod = _fresh_import_verum_openai()

        # Patch _resolve_sync to return baseline (traffic_split=0 → same msgs)
        with patch.object(
            mod,
            "_resolve_sync",
            return_value=(original_messages, "fresh"),
        ):
            instance = comp_mod.Completions()
            instance.create(
                model="gpt-4",
                messages=original_messages,
            )

        self.assertEqual(len(received_messages), 1)
        self.assertEqual(received_messages[0]["content"], "tarot reading")


class TestFailOpenFallback(unittest.TestCase):
    """When the resolver raises, original messages are used and the call succeeds."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-fail-001"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        os.environ.pop("VERUM_DEPLOYMENT_ID", None)
        os.environ.pop("VERUM_API_URL", None)
        os.environ.pop("VERUM_API_KEY", None)

    def test_resolver_exception_does_not_break_call(self) -> None:
        original_messages = [{"role": "user", "content": "what is the moon card?"}]
        received_messages: list[Any] = []

        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        def spy_create(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            received_messages.extend(kwargs.get("messages", []))
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=8, completion_tokens=4),
            )

        comp_mod.Completions.create = spy_create  # type: ignore[method-assign]

        mod = _fresh_import_verum_openai()

        def _raising_resolve(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("simulated network error")

        with patch.object(mod, "_resolve_sync", side_effect=_raising_resolve):
            instance = comp_mod.Completions()
            response = instance.create(
                model="gpt-4",
                messages=original_messages,
            )

        # Call must succeed and original messages must be forwarded.
        self.assertIsNotNone(response)
        self.assertEqual(len(received_messages), 1)
        self.assertEqual(received_messages[0]["content"], "what is the moon card?")


class TestPatchApplied(unittest.TestCase):
    """Verify that importing verum.openai actually patches Completions.create."""

    def setUp(self) -> None:
        _make_openai_stub()

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    def test_import_patches_completions_create(self) -> None:
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        original = comp_mod.Completions.create
        _fresh_import_verum_openai()
        patched = comp_mod.Completions.create

        # The function should have been replaced.
        self.assertIsNot(patched, original)

    def test_patched_flag_is_true_after_import(self) -> None:
        mod = _fresh_import_verum_openai()
        self.assertTrue(mod._PATCHED)
