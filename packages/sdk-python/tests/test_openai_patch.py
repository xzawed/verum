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


class TestExtractDeploymentId(unittest.TestCase):
    """Tests for _extract_deployment_id helper."""

    def setUp(self) -> None:
        _make_openai_stub()

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        os.environ.pop("VERUM_DEPLOYMENT_ID", None)

    def test_extracts_from_extra_headers(self) -> None:
        mod = _fresh_import_verum_openai()
        kwargs: dict[str, Any] = {"extra_headers": {"x-verum-deployment": "dep-abc"}}
        dep_id, new_kwargs = mod._extract_deployment_id(kwargs)
        self.assertEqual(dep_id, "dep-abc")
        self.assertNotIn("extra_headers", new_kwargs)

    def test_falls_back_to_env_var(self) -> None:
        mod = _fresh_import_verum_openai()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-env"
        dep_id, _ = mod._extract_deployment_id({})
        self.assertEqual(dep_id, "dep-env")

    def test_preserves_remaining_headers(self) -> None:
        mod = _fresh_import_verum_openai()
        kwargs: dict[str, Any] = {
            "extra_headers": {"x-verum-deployment": "dep-1", "x-custom": "value"}
        }
        dep_id, new_kwargs = mod._extract_deployment_id(kwargs)
        self.assertEqual(dep_id, "dep-1")
        self.assertEqual(new_kwargs["extra_headers"]["x-custom"], "value")

    def test_returns_none_when_no_id(self) -> None:
        mod = _fresh_import_verum_openai()
        dep_id, _ = mod._extract_deployment_id({})
        self.assertIsNone(dep_id)


class TestExtractUsage(unittest.TestCase):
    """Tests for _extract_usage helper."""

    def setUp(self) -> None:
        _make_openai_stub()

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    def test_extracts_tokens_and_model(self) -> None:
        from unittest.mock import MagicMock
        mod = _fresh_import_verum_openai()
        response = MagicMock()
        response.usage.prompt_tokens = 20
        response.usage.completion_tokens = 8
        response.model = "gpt-4o"
        inp, out, model = mod._extract_usage(response)
        self.assertEqual(inp, 20)
        self.assertEqual(out, 8)
        self.assertEqual(model, "gpt-4o")

    def test_fallback_when_usage_is_none(self) -> None:
        from unittest.mock import MagicMock
        mod = _fresh_import_verum_openai()
        response = MagicMock()
        response.usage = None
        response.model = "gpt-4o"
        inp, out, _ = mod._extract_usage(response)
        self.assertEqual(inp, 0)
        self.assertEqual(out, 0)


class TestAsyncPassThrough(unittest.IsolatedAsyncioTestCase):
    """Async wrapper passes through when no deployment_id is set."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ.pop("VERUM_DEPLOYMENT_ID", None)
        os.environ.pop("VERUM_API_URL", None)
        os.environ.pop("VERUM_API_KEY", None)

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    async def test_async_no_deployment_id_calls_original(self) -> None:
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        call_record: list[dict[str, Any]] = []

        async def recording_acreate(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            call_record.append(kwargs)
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=10, completion_tokens=5),
            )

        comp_mod.AsyncCompletions.create = recording_acreate  # type: ignore[method-assign]
        _fresh_import_verum_openai()

        instance = comp_mod.AsyncCompletions()
        await instance.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "hello async"}],
        )

        self.assertEqual(len(call_record), 1)
        self.assertEqual(call_record[0]["messages"][0]["content"], "hello async")


class TestAsyncFailOpen(unittest.IsolatedAsyncioTestCase):
    """Async wrapper remains fail-open when resolver raises."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-async-fail"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    async def test_async_resolver_exception_does_not_break_call(self) -> None:
        from unittest.mock import AsyncMock, patch as async_patch
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        received: list[dict[str, Any]] = []

        async def spy_acreate(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            received.extend(kwargs.get("messages", []))
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=8, completion_tokens=4),
            )

        comp_mod.AsyncCompletions.create = spy_acreate  # type: ignore[method-assign]
        mod = _fresh_import_verum_openai()

        mock_resolver = AsyncMock()
        mock_resolver.resolve.side_effect = RuntimeError("network error")

        with async_patch.object(mod, "_get_resolver", return_value=mock_resolver):
            instance = comp_mod.AsyncCompletions()
            response = await instance.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "async fail-open test"}],
            )

        self.assertIsNotNone(response)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["content"], "async fail-open test")


class TestAsyncWithDeploymentId(unittest.IsolatedAsyncioTestCase):
    """Async wrapper forwards resolved messages when deployment_id is set."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-async-001"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    async def test_async_resolved_messages_forwarded(self) -> None:
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        received_messages: list[Any] = []

        async def spy_acreate(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            received_messages.extend(kwargs.get("messages", []))
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=10, completion_tokens=5),
            )

        comp_mod.AsyncCompletions.create = spy_acreate  # type: ignore[method-assign]
        mod = _fresh_import_verum_openai()

        variant_messages = [{"role": "user", "content": "variant content"}]
        mock_resolver = AsyncMock()
        mock_resolver.resolve.return_value = (variant_messages, "variant")

        with patch.object(mod, "_get_resolver", return_value=mock_resolver):
            instance = comp_mod.AsyncCompletions()
            response = await instance.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "original content"}],
            )

        self.assertIsNotNone(response)
        self.assertEqual(len(received_messages), 1)
        self.assertEqual(received_messages[0]["content"], "variant content")


class TestAsyncWithDeploymentIdNoResolver(unittest.IsolatedAsyncioTestCase):
    """Async wrapper calls original unchanged when resolver returns None."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-async-no-resolver"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    async def test_async_no_resolver_passes_original_messages(self) -> None:
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        received_messages: list[Any] = []

        async def spy_acreate(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            received_messages.extend(kwargs.get("messages", []))
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=5, completion_tokens=3),
            )

        comp_mod.AsyncCompletions.create = spy_acreate  # type: ignore[method-assign]
        mod = _fresh_import_verum_openai()

        # When resolver is None, variant stays "no_resolver" and original messages pass through.
        with patch.object(mod, "_get_resolver", return_value=None):
            instance = comp_mod.AsyncCompletions()
            response = await instance.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "no resolver path"}],
            )

        self.assertIsNotNone(response)
        self.assertEqual(len(received_messages), 1)
        self.assertEqual(received_messages[0]["content"], "no resolver path")


class TestAsyncTraceBackground(unittest.IsolatedAsyncioTestCase):
    """_record_trace_bg_async silently skips when api_url/http are absent."""

    def setUp(self) -> None:
        _make_openai_stub()
        for v in ("VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    async def test_no_api_url_returns_without_error(self) -> None:
        mod = _fresh_import_verum_openai()
        await mod._record_trace_bg_async(
            deployment_id="dep-trace",
            variant="baseline",
            model="gpt-4",
            input_tokens=5,
            output_tokens=3,
            latency_ms=120,
        )

    async def test_async_http_none_returns_without_error(self) -> None:
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        mod = _fresh_import_verum_openai()
        original_async_http = mod._async_http
        mod._async_http = None
        try:
            await mod._record_trace_bg_async(
                deployment_id="dep-trace",
                variant="baseline",
                model="gpt-4",
                input_tokens=5,
                output_tokens=3,
                latency_ms=120,
            )
        finally:
            mod._async_http = original_async_http
            os.environ.pop("VERUM_API_URL", None)

    async def test_exception_in_post_is_swallowed(self) -> None:
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        mod = _fresh_import_verum_openai()

        mock_http = AsyncMock()
        mock_http.post.side_effect = RuntimeError("connection refused")
        original_async_http = mod._async_http
        mod._async_http = mock_http
        try:
            await mod._record_trace_bg_async(
                deployment_id="dep-trace",
                variant="variant",
                model="gpt-4",
                input_tokens=10,
                output_tokens=5,
                latency_ms=200,
            )
        finally:
            mod._async_http = original_async_http
            os.environ.pop("VERUM_API_URL", None)


class TestSyncTraceBackgroundOpenAI(unittest.TestCase):
    """_record_trace_bg daemon thread swallows all exceptions."""

    def setUp(self) -> None:
        _make_openai_stub()
        for v in ("VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    def test_no_api_url_does_not_raise(self) -> None:
        mod = _fresh_import_verum_openai()
        mod._record_trace_bg(
            deployment_id="dep-trace",
            variant="baseline",
            model="gpt-4",
            input_tokens=5,
            output_tokens=3,
            latency_ms=100,
        )

    def test_sync_http_none_does_not_raise(self) -> None:
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        mod = _fresh_import_verum_openai()
        original_sync_http = mod._sync_http
        mod._sync_http = None
        try:
            mod._record_trace_bg(
                deployment_id="dep-trace",
                variant="baseline",
                model="gpt-4",
                input_tokens=5,
                output_tokens=3,
                latency_ms=100,
            )
        finally:
            mod._sync_http = original_sync_http
            os.environ.pop("VERUM_API_URL", None)

    def test_http_exception_is_swallowed(self) -> None:
        import threading

        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        mod = _fresh_import_verum_openai()

        mock_http = MagicMock()
        mock_http.post.side_effect = RuntimeError("connection refused")
        original_sync_http = mod._sync_http
        mod._sync_http = mock_http

        done = threading.Event()
        original_start = threading.Thread.start

        def patched_start(thread_self: threading.Thread) -> None:
            original_start(thread_self)
            done.set()

        try:
            with patch.object(threading.Thread, "start", patched_start):
                mod._record_trace_bg(
                    deployment_id="dep-trace",
                    variant="variant",
                    model="gpt-4",
                    input_tokens=10,
                    output_tokens=5,
                    latency_ms=200,
                )
            done.wait(timeout=2.0)
        finally:
            mod._sync_http = original_sync_http
            os.environ.pop("VERUM_API_URL", None)


class TestExtractUsageExceptions(unittest.TestCase):
    """_extract_usage handles broken response attributes gracefully."""

    def setUp(self) -> None:
        _make_openai_stub()

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    def test_usage_attribute_raises(self) -> None:
        mod = _fresh_import_verum_openai()

        class BadResponse:
            @property
            def usage(self) -> None:
                raise AttributeError("no usage")

            model = "gpt-4"

        inp, out, model = mod._extract_usage(BadResponse())
        self.assertEqual(inp, 0)
        self.assertEqual(out, 0)
        self.assertEqual(model, "gpt-4")

    def test_model_attribute_raises(self) -> None:
        mod = _fresh_import_verum_openai()

        class BadResponse:
            usage = MagicMock(prompt_tokens=7, completion_tokens=3)

            @property
            def model(self) -> None:
                raise AttributeError("no model")

        inp, out, model = mod._extract_usage(BadResponse())
        self.assertEqual(inp, 7)
        self.assertEqual(out, 3)
        self.assertEqual(model, "")


class TestGetResolverCreationFailureOpenAI(unittest.TestCase):
    """_get_resolver returns None when httpx or internal imports fail."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        os.environ.pop("VERUM_API_URL", None)
        os.environ.pop("VERUM_API_KEY", None)

    def test_resolver_creation_exception_returns_none(self) -> None:
        mod = _fresh_import_verum_openai()
        mod._resolver = None
        mod._sync_http = None
        mod._async_http = None

        with patch("builtins.__import__", side_effect=ImportError("no httpx")):
            result = mod._get_resolver()

        self.assertIsNone(result)


class TestResolveSyncPathsOpenAI(unittest.TestCase):
    """_resolve_sync returns original messages when resolver is None."""

    def setUp(self) -> None:
        _make_openai_stub()
        for v in ("VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    def test_no_resolver_returns_original_messages(self) -> None:
        mod = _fresh_import_verum_openai()
        mod._resolver = None

        messages = [{"role": "user", "content": "hello"}]
        with patch.object(mod, "_get_resolver", return_value=None):
            result_messages, reason = mod._resolve_sync("dep-001", messages)

        self.assertIs(result_messages, messages)
        self.assertEqual(reason, "no_resolver")


class TestSyncWrappedCreateExceptionHandler(unittest.TestCase):
    """_wrapped_create swallows exceptions from _record_trace_bg."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-trace-except"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def test_trace_exception_does_not_surface(self) -> None:
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        messages = [{"role": "user", "content": "test trace exception"}]

        def spy_create(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=5, completion_tokens=3),
            )

        comp_mod.Completions.create = spy_create  # type: ignore[method-assign]
        mod = _fresh_import_verum_openai()

        with patch.object(
            mod, "_resolve_sync", return_value=(messages, "baseline")
        ), patch.object(mod, "_record_trace_bg", side_effect=RuntimeError("trace boom")):
            instance = comp_mod.Completions()
            response = instance.create(model="gpt-4", messages=messages)

        self.assertIsNotNone(response)


class TestGetResolverCachedReturnOpenAI(unittest.TestCase):
    """_get_resolver returns the cached singleton on the fast path without lock."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ.pop("VERUM_API_URL", None)
        os.environ.pop("VERUM_API_KEY", None)

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    def test_cached_resolver_returned_without_entering_lock(self) -> None:
        mod = _fresh_import_verum_openai()
        sentinel = MagicMock(name="cached_resolver")
        mod._resolver = sentinel
        result = mod._get_resolver()
        self.assertIs(result, sentinel)


class TestGetResolverNoEnvVarsOpenAI(unittest.TestCase):
    """_get_resolver returns None inside the lock when both env vars are absent."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ.pop("VERUM_API_URL", None)
        os.environ.pop("VERUM_API_KEY", None)

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    def test_no_env_vars_returns_none_inside_lock(self) -> None:
        mod = _fresh_import_verum_openai()
        mod._resolver = None
        result = mod._get_resolver()
        self.assertIsNone(result)


class TestResolveSyncWithRunningEventLoop(unittest.IsolatedAsyncioTestCase):
    """_resolve_sync dispatches to ThreadPoolExecutor when an event loop is running."""

    def setUp(self) -> None:
        _make_openai_stub()

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    async def test_running_event_loop_uses_thread_dispatch(self) -> None:
        """ThreadPoolExecutor branch executes when called from within async context."""
        mod = _fresh_import_verum_openai()
        mock_resolver = MagicMock()
        mock_resolver.resolve = AsyncMock(
            return_value=([{"role": "user", "content": "resolved"}], "variant_x")
        )
        messages = [{"role": "user", "content": "original"}]
        with patch.object(mod, "_get_resolver", return_value=mock_resolver):
            result_msgs, reason = mod._resolve_sync("dep-async", messages)
        self.assertEqual(result_msgs[0]["content"], "resolved")
        self.assertEqual(reason, "variant_x")


class TestModuleInitRuntimeErrorSwallowed(unittest.TestCase):
    """Module-level except Exception: pass keeps import alive on non-ImportError."""

    def setUp(self) -> None:
        _make_openai_stub()

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    def test_runtime_error_during_patch_openai_is_swallowed(self) -> None:
        """AttributeError from _patch_openai is caught by except Exception: pass."""
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        orig_async = comp_mod.AsyncCompletions
        # Corrupt stub so _patch_openai raises AttributeError (not ImportError)
        comp_mod.AsyncCompletions = None  # type: ignore[attr-defined]

        sys.modules.pop("verum.openai", None)
        try:
            mod = importlib.import_module("verum.openai")
            self.assertIsNotNone(mod)
        finally:
            comp_mod.AsyncCompletions = orig_async  # type: ignore[attr-defined]
            sys.modules.pop("verum.openai", None)


class TestModuleInitSetupOtelErrorSwallowed(unittest.TestCase):
    """Module-level _setup_otel exception is silently caught on import."""

    def setUp(self) -> None:
        _make_openai_stub()

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        sys.modules.pop("verum._instrument", None)

    def test_setup_otel_exception_is_swallowed(self) -> None:
        """RuntimeError from _setup_otel_fn is caught at module init time."""
        fake_instrument = types.ModuleType("verum._instrument")

        def _failing_setup() -> None:
            raise RuntimeError("otel broken in test")

        fake_instrument._setup_otel = _failing_setup  # type: ignore[attr-defined]
        sys.modules["verum._instrument"] = fake_instrument

        mod = importlib.import_module("verum.openai")
        self.assertIsNotNone(mod)
        sys.modules.pop("verum.openai", None)


# ---------------------------------------------------------------------------
# _get_resolver — successful creation path (httpx import block)
# ---------------------------------------------------------------------------


class TestGetResolverSuccessfulCreation(unittest.TestCase):
    """_get_resolver successfully creates resolver when env vars are set."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        os.environ.pop("VERUM_API_URL", None)
        os.environ.pop("VERUM_API_KEY", None)

    def test_resolver_created_successfully_when_env_set(self) -> None:
        """Covers the httpx import block inside _get_resolver()."""
        mod = _fresh_import_verum_openai()
        # Reset singletons to force re-creation
        mod._resolver = None
        mod._sync_http = None
        mod._async_http = None

        resolver = mod._get_resolver()
        self.assertIsNotNone(resolver)

        # Second call returns cached resolver (fast path)
        resolver2 = mod._get_resolver()
        self.assertIs(resolver, resolver2)


# ---------------------------------------------------------------------------
# _resolve_sync — sync no-loop path (asyncio.run branch)
# ---------------------------------------------------------------------------


class TestResolveSyncNoLoopOpenAI(unittest.TestCase):
    """_resolve_sync calls asyncio.run when there is no running event loop."""

    def setUp(self) -> None:
        _make_openai_stub()
        for v in ("VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def tearDown(self) -> None:
        _cleanup_openai_stub()

    def test_resolve_sync_calls_asyncio_run_when_no_loop(self) -> None:
        """Sync context: no running loop → asyncio.run(_run()) branch is taken."""
        mod = _fresh_import_verum_openai()
        mock_resolver = MagicMock()
        messages = [{"role": "user", "content": "hello"}]
        mock_resolver.resolve = AsyncMock(return_value=(messages, "fresh"))
        with patch.object(mod, "_get_resolver", return_value=mock_resolver):
            result_msgs, reason = mod._resolve_sync("dep-001", messages)
        self.assertEqual(result_msgs, messages)
        self.assertEqual(reason, "fresh")


# ---------------------------------------------------------------------------
# _wrapped_create — _extract_usage raises → except Exception: pass
# ---------------------------------------------------------------------------


class TestWrappedCreateExtractUsageExceptionOpenAI(unittest.TestCase):
    """_wrapped_create swallows exceptions from _extract_usage."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-extract-except-openai"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def test_extract_usage_exception_swallowed_in_wrapped_create(self) -> None:
        """When _extract_usage raises, exception is caught and response is still returned."""
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        messages = [{"role": "user", "content": "test"}]

        def spy_create(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=5, completion_tokens=3),
            )

        comp_mod.Completions.create = spy_create  # type: ignore[method-assign]
        mod = _fresh_import_verum_openai()

        with patch.object(
            mod, "_resolve_sync", return_value=(messages, "baseline")
        ), patch.object(
            mod, "_extract_usage", side_effect=RuntimeError("usage exploded")
        ):
            instance = comp_mod.Completions()
            response = instance.create(model="gpt-4", messages=messages)

        self.assertIsNotNone(response)


# ---------------------------------------------------------------------------
# _wrapped_acreate — resolver is None → variant stays "no_resolver"
# ---------------------------------------------------------------------------


class TestWrappedAcreateNoResolverOpenAI(unittest.IsolatedAsyncioTestCase):
    """_wrapped_acreate uses 'no_resolver' variant when resolver is None."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-acreate-no-resolver"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    async def test_acreate_no_resolver_calls_original_with_original_messages(self) -> None:
        """When _get_resolver returns None in async path, original messages pass through."""
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        received_messages: list[Any] = []

        async def spy_acreate(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            received_messages.extend(kwargs.get("messages", []))
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=5, completion_tokens=3),
            )

        comp_mod.AsyncCompletions.create = spy_acreate  # type: ignore[method-assign]
        mod = _fresh_import_verum_openai()

        with patch.object(mod, "_get_resolver", return_value=None):
            instance = comp_mod.AsyncCompletions()
            response = await instance.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "no resolver async"}],
            )

        self.assertIsNotNone(response)
        self.assertEqual(len(received_messages), 1)
        self.assertEqual(received_messages[0]["content"], "no resolver async")


# ---------------------------------------------------------------------------
# _wrapped_acreate — _extract_usage raises → except Exception: pass
# ---------------------------------------------------------------------------


class TestWrappedAcreateExtractUsageExceptionOpenAI(unittest.IsolatedAsyncioTestCase):
    """_wrapped_acreate swallows exceptions from _extract_usage."""

    def setUp(self) -> None:
        _make_openai_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-async-extract-except-openai"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_openai_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    async def test_extract_usage_exception_swallowed_in_wrapped_acreate(self) -> None:
        """When _extract_usage raises in async path, response is still returned."""
        import openai.resources.chat.completions as comp_mod  # type: ignore[import]

        async def spy_acreate(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            return MagicMock(
                model="gpt-4",
                usage=MagicMock(prompt_tokens=5, completion_tokens=3),
            )

        comp_mod.AsyncCompletions.create = spy_acreate  # type: ignore[method-assign]
        mod = _fresh_import_verum_openai()

        mock_resolver = AsyncMock()
        mock_resolver.resolve.return_value = (
            [{"role": "user", "content": "resolved"}],
            "baseline",
        )

        with patch.object(
            mod, "_get_resolver", return_value=mock_resolver
        ), patch.object(
            mod, "_extract_usage", side_effect=RuntimeError("async usage exploded")
        ):
            instance = comp_mod.AsyncCompletions()
            response = await instance.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "async test"}],
            )

        self.assertIsNotNone(response)
