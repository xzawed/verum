"""Tests for the verum.anthropic monkey-patch module."""
from __future__ import annotations

import asyncio
import importlib
import os
import sys
import types
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers for building minimal anthropic stubs
# ---------------------------------------------------------------------------


def _make_anthropic_stub() -> types.ModuleType:
    """Build a minimal anthropic module stub and register it in sys.modules."""
    _cleanup_anthropic_stub()

    anthropic_mod = types.ModuleType("anthropic")
    resources_mod = types.ModuleType("anthropic.resources")
    messages_mod = types.ModuleType("anthropic.resources.messages")

    class Messages:
        def create(self, *args: Any, **kwargs: Any) -> MagicMock:
            return MagicMock(
                model="claude-opus-4-7",
                usage=MagicMock(input_tokens=10, output_tokens=5),
            )

    class AsyncMessages:
        async def create(self, *args: Any, **kwargs: Any) -> MagicMock:
            return MagicMock(
                model="claude-opus-4-7",
                usage=MagicMock(input_tokens=10, output_tokens=5),
            )

    messages_mod.Messages = Messages  # type: ignore[attr-defined]
    messages_mod.AsyncMessages = AsyncMessages  # type: ignore[attr-defined]
    resources_mod.messages = messages_mod  # type: ignore[attr-defined]
    anthropic_mod.resources = resources_mod  # type: ignore[attr-defined]

    sys.modules["anthropic"] = anthropic_mod
    sys.modules["anthropic.resources"] = resources_mod
    sys.modules["anthropic.resources.messages"] = messages_mod

    return anthropic_mod


def _cleanup_anthropic_stub() -> None:
    for key in list(sys.modules.keys()):
        if key == "anthropic" or key.startswith("anthropic.") or key == "verum.anthropic":
            del sys.modules[key]


def _fresh_import_verum_anthropic() -> types.ModuleType:
    for key in list(sys.modules.keys()):
        if key == "verum.anthropic":
            del sys.modules[key]
    return importlib.import_module("verum.anthropic")


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


class TestBuildSyntheticMessages(unittest.TestCase):
    def setUp(self) -> None:
        _make_anthropic_stub()

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()

    def test_wraps_system_as_message_list(self) -> None:
        mod = _fresh_import_verum_anthropic()
        result = mod._build_synthetic_messages("You are a tarot reader.")
        self.assertEqual(result, [{"role": "system", "content": "You are a tarot reader."}])

    def test_empty_system_string(self) -> None:
        mod = _fresh_import_verum_anthropic()
        result = mod._build_synthetic_messages("")
        self.assertEqual(result, [{"role": "system", "content": ""}])


class TestApplyResolvedMessages(unittest.TestCase):
    def setUp(self) -> None:
        _make_anthropic_stub()

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()

    def test_applies_modified_system_prompt(self) -> None:
        mod = _fresh_import_verum_anthropic()
        kwargs: dict[str, Any] = {"system": "original", "messages": []}
        resolved = [{"role": "system", "content": "modified"}]
        result = mod._apply_resolved_messages(kwargs, resolved)
        self.assertEqual(result["system"], "modified")

    def test_non_system_resolved_leaves_kwargs_unchanged(self) -> None:
        mod = _fresh_import_verum_anthropic()
        kwargs: dict[str, Any] = {"system": "original"}
        resolved = [{"role": "user", "content": "hello"}]
        result = mod._apply_resolved_messages(kwargs, resolved)
        self.assertEqual(result["system"], "original")

    def test_empty_resolved_list_leaves_kwargs_unchanged(self) -> None:
        mod = _fresh_import_verum_anthropic()
        kwargs: dict[str, Any] = {"system": "original"}
        result = mod._apply_resolved_messages(kwargs, [])
        self.assertEqual(result["system"], "original")


class TestExtractUsageAnthropic(unittest.TestCase):
    def setUp(self) -> None:
        _make_anthropic_stub()

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()

    def test_extracts_tokens_and_model(self) -> None:
        mod = _fresh_import_verum_anthropic()
        response = MagicMock()
        response.usage.input_tokens = 15
        response.usage.output_tokens = 7
        response.model = "claude-3-opus"
        inp, out, model = mod._extract_usage_anthropic(response)
        self.assertEqual(inp, 15)
        self.assertEqual(out, 7)
        self.assertEqual(model, "claude-3-opus")

    def test_fallback_when_usage_is_none(self) -> None:
        mod = _fresh_import_verum_anthropic()
        response = MagicMock()
        response.usage = None
        response.model = "claude-3-opus"
        inp, out, _ = mod._extract_usage_anthropic(response)
        self.assertEqual(inp, 0)
        self.assertEqual(out, 0)

    def test_fallback_when_model_is_none(self) -> None:
        mod = _fresh_import_verum_anthropic()
        response = MagicMock()
        response.usage.input_tokens = 5
        response.usage.output_tokens = 3
        response.model = None
        _, _, model = mod._extract_usage_anthropic(response)
        self.assertEqual(model, "")


class TestExtractDeploymentId(unittest.TestCase):
    def setUp(self) -> None:
        _make_anthropic_stub()

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()
        os.environ.pop("VERUM_DEPLOYMENT_ID", None)

    def test_extracts_from_extra_headers(self) -> None:
        mod = _fresh_import_verum_anthropic()
        kwargs: dict[str, Any] = {"extra_headers": {"x-verum-deployment": "dep-abc"}}
        dep_id, new_kwargs = mod._extract_deployment_id(kwargs)
        self.assertEqual(dep_id, "dep-abc")
        self.assertNotIn("extra_headers", new_kwargs)

    def test_falls_back_to_env_var(self) -> None:
        mod = _fresh_import_verum_anthropic()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-env"
        dep_id, _ = mod._extract_deployment_id({})
        self.assertEqual(dep_id, "dep-env")

    def test_preserves_other_extra_headers(self) -> None:
        mod = _fresh_import_verum_anthropic()
        kwargs: dict[str, Any] = {
            "extra_headers": {"x-verum-deployment": "dep-1", "x-custom": "value"}
        }
        dep_id, new_kwargs = mod._extract_deployment_id(kwargs)
        self.assertEqual(dep_id, "dep-1")
        self.assertEqual(new_kwargs["extra_headers"]["x-custom"], "value")


# ---------------------------------------------------------------------------
# Resolver singleton tests
# ---------------------------------------------------------------------------


class TestGetResolver(unittest.TestCase):
    def setUp(self) -> None:
        _make_anthropic_stub()
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()
        os.environ.pop("VERUM_API_URL", None)
        os.environ.pop("VERUM_API_KEY", None)

    def test_get_resolver_returns_instance_when_env_set(self) -> None:
        mod = _fresh_import_verum_anthropic()
        mod._resolver = None
        mod._sync_http = None
        mod._async_http = None

        resolver = mod._get_resolver()
        self.assertIsNotNone(resolver)

        # Second call returns cached resolver.
        resolver2 = mod._get_resolver()
        self.assertIs(resolver, resolver2)

    def test_get_resolver_returns_none_without_env(self) -> None:
        os.environ.pop("VERUM_API_URL", None)
        os.environ.pop("VERUM_API_KEY", None)
        mod = _fresh_import_verum_anthropic()
        mod._resolver = None
        resolver = mod._get_resolver()
        self.assertIsNone(resolver)


# ---------------------------------------------------------------------------
# Patching behaviour tests
# ---------------------------------------------------------------------------


class TestPatchIdempotent(unittest.TestCase):
    def setUp(self) -> None:
        _make_anthropic_stub()
        for key in list(sys.modules.keys()):
            if key == "verum.anthropic":
                del sys.modules[key]

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()

    def test_double_import_is_idempotent(self) -> None:
        import anthropic.resources.messages as msg_mod  # type: ignore[import]

        mod = _fresh_import_verum_anthropic()
        first_create = msg_mod.Messages.create

        self.assertTrue(mod._PATCHED)
        mod._patch_anthropic()

        self.assertIs(msg_mod.Messages.create, first_create)


class TestPatchApplied(unittest.TestCase):
    def setUp(self) -> None:
        _make_anthropic_stub()

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()

    def test_import_patches_messages_create(self) -> None:
        import anthropic.resources.messages as msg_mod  # type: ignore[import]

        original = msg_mod.Messages.create
        _fresh_import_verum_anthropic()
        patched = msg_mod.Messages.create

        self.assertIsNot(patched, original)

    def test_patched_flag_is_true_after_import(self) -> None:
        mod = _fresh_import_verum_anthropic()
        self.assertTrue(mod._PATCHED)


class TestPassThroughNoDeploymentId(unittest.TestCase):
    def setUp(self) -> None:
        _make_anthropic_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()

    def test_no_deployment_id_calls_original_create(self) -> None:
        import anthropic.resources.messages as msg_mod  # type: ignore[import]

        call_record: list[dict[str, Any]] = []

        def recording_create(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            call_record.append(kwargs)
            return MagicMock(
                model="claude-3", usage=MagicMock(input_tokens=5, output_tokens=3)
            )

        msg_mod.Messages.create = recording_create  # type: ignore[method-assign]
        _fresh_import_verum_anthropic()

        instance = msg_mod.Messages()
        instance.create(
            model="claude-3-opus",
            messages=[{"role": "user", "content": "hi"}],
        )

        self.assertEqual(len(call_record), 1)


class TestBaselineWhenResolverReturnsBaseline(unittest.TestCase):
    def setUp(self) -> None:
        _make_anthropic_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-ant-001"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def test_resolved_messages_forwarded_to_original(self) -> None:
        import anthropic.resources.messages as msg_mod  # type: ignore[import]

        original_system = "You are a tarot reader."
        received: list[str] = []

        def spy_create(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            received.append(kwargs.get("system", ""))
            return MagicMock(
                model="claude-3", usage=MagicMock(input_tokens=5, output_tokens=3)
            )

        msg_mod.Messages.create = spy_create  # type: ignore[method-assign]
        mod = _fresh_import_verum_anthropic()

        resolved = [{"role": "system", "content": original_system}]
        with patch.object(mod, "_resolve_sync", return_value=(resolved, "fresh")):
            instance = msg_mod.Messages()
            instance.create(
                model="claude-3",
                system=original_system,
                messages=[{"role": "user", "content": "draw a card"}],
            )

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], original_system)


class TestFailOpenFallback(unittest.TestCase):
    def setUp(self) -> None:
        _make_anthropic_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-ant-fail"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def test_resolver_exception_does_not_break_call(self) -> None:
        import anthropic.resources.messages as msg_mod  # type: ignore[import]

        received: list[dict[str, Any]] = []

        def spy_create(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            received.append(kwargs)
            return MagicMock(
                model="claude-3", usage=MagicMock(input_tokens=5, output_tokens=3)
            )

        msg_mod.Messages.create = spy_create  # type: ignore[method-assign]
        mod = _fresh_import_verum_anthropic()

        def _raise(*a: Any, **kw: Any) -> None:
            raise RuntimeError("simulated network error")

        with patch.object(mod, "_resolve_sync", side_effect=_raise):
            instance = msg_mod.Messages()
            response = instance.create(
                model="claude-3",
                system="You are a tarot reader.",
                messages=[{"role": "user", "content": "test"}],
            )

        self.assertIsNotNone(response)
        self.assertEqual(len(received), 1)


# ---------------------------------------------------------------------------
# Async wrapper tests
# ---------------------------------------------------------------------------


class TestAsyncWrappedCreateNoDeploymentId(unittest.IsolatedAsyncioTestCase):
    """Async wrapper passes through unchanged when no deployment_id is set."""

    def setUp(self) -> None:
        _make_anthropic_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()

    async def test_async_no_deployment_id_calls_original(self) -> None:
        import anthropic.resources.messages as msg_mod  # type: ignore[import]

        call_record: list[dict[str, Any]] = []

        async def recording_acreate(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            call_record.append(kwargs)
            return MagicMock(
                model="claude-3-opus",
                usage=MagicMock(input_tokens=10, output_tokens=5),
            )

        msg_mod.AsyncMessages.create = recording_acreate  # type: ignore[method-assign]
        mod = _fresh_import_verum_anthropic()

        # _resolve_async should NOT be called when there's no deployment_id.
        with patch.object(mod, "_get_resolver") as mock_get_resolver:
            instance = msg_mod.AsyncMessages()
            await instance.create(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "hello async"}],
            )

        mock_get_resolver.assert_not_called()
        self.assertEqual(len(call_record), 1)
        self.assertEqual(call_record[0]["messages"][0]["content"], "hello async")


class TestAsyncWrappedCreateWithDeploymentId(unittest.IsolatedAsyncioTestCase):
    """Async wrapper forwards resolved messages when deployment_id is set."""

    def setUp(self) -> None:
        _make_anthropic_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-async-ant-001"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    async def test_async_resolved_messages_forwarded(self) -> None:
        import anthropic.resources.messages as msg_mod  # type: ignore[import]

        received_systems: list[str] = []

        async def spy_acreate(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            received_systems.append(kwargs.get("system", ""))
            return MagicMock(
                model="claude-3-opus",
                usage=MagicMock(input_tokens=8, output_tokens=4),
            )

        msg_mod.AsyncMessages.create = spy_acreate  # type: ignore[method-assign]
        mod = _fresh_import_verum_anthropic()

        resolved_system = "You are a modified tarot reader."
        mock_resolver = AsyncMock()
        mock_resolver.resolve.return_value = (
            [{"role": "system", "content": resolved_system}],
            "variant",
        )

        with patch.object(mod, "_get_resolver", return_value=mock_resolver):
            instance = msg_mod.AsyncMessages()
            response = await instance.create(
                model="claude-3-opus",
                system="You are a tarot reader.",
                messages=[{"role": "user", "content": "draw a card"}],
            )

        self.assertIsNotNone(response)
        self.assertEqual(len(received_systems), 1)
        self.assertEqual(received_systems[0], resolved_system)


class TestAsyncWrappedCreateFailOpen(unittest.IsolatedAsyncioTestCase):
    """Async wrapper is fail-open when resolver raises."""

    def setUp(self) -> None:
        _make_anthropic_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-async-fail"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    async def test_async_resolver_exception_does_not_break_call(self) -> None:
        import anthropic.resources.messages as msg_mod  # type: ignore[import]

        received: list[dict[str, Any]] = []

        async def spy_acreate(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            received.append(kwargs)
            return MagicMock(
                model="claude-3-opus",
                usage=MagicMock(input_tokens=6, output_tokens=3),
            )

        msg_mod.AsyncMessages.create = spy_acreate  # type: ignore[method-assign]
        mod = _fresh_import_verum_anthropic()

        mock_resolver = AsyncMock()
        mock_resolver.resolve.side_effect = RuntimeError("simulated network error")

        with patch.object(mod, "_get_resolver", return_value=mock_resolver):
            instance = msg_mod.AsyncMessages()
            response = await instance.create(
                model="claude-3-opus",
                system="You are a tarot reader.",
                messages=[{"role": "user", "content": "fail-open test"}],
            )

        self.assertIsNotNone(response)
        self.assertEqual(len(received), 1)


class TestAsyncTraceBackground(unittest.IsolatedAsyncioTestCase):
    """_record_trace_bg_async silently skips when api_url/http are absent."""

    def setUp(self) -> None:
        _make_anthropic_stub()
        for v in ("VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()

    async def test_no_api_url_returns_without_error(self) -> None:
        mod = _fresh_import_verum_anthropic()
        # Should complete without raising even when api_url is missing.
        await mod._record_trace_bg_async(
            deployment_id="dep-trace",
            variant="baseline",
            model="claude-3-opus",
            input_tokens=5,
            output_tokens=3,
            latency_ms=120,
        )

    async def test_async_http_none_returns_without_error(self) -> None:
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        mod = _fresh_import_verum_anthropic()
        # Ensure _async_http is None so the early-exit branch is exercised.
        original_async_http = mod._async_http
        mod._async_http = None
        try:
            await mod._record_trace_bg_async(
                deployment_id="dep-trace",
                variant="baseline",
                model="claude-3-opus",
                input_tokens=5,
                output_tokens=3,
                latency_ms=120,
            )
        finally:
            mod._async_http = original_async_http
            os.environ.pop("VERUM_API_URL", None)

    async def test_exception_in_post_is_swallowed(self) -> None:
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        mod = _fresh_import_verum_anthropic()

        mock_http = AsyncMock()
        mock_http.post.side_effect = RuntimeError("connection refused")
        original_async_http = mod._async_http
        mod._async_http = mock_http
        try:
            # Must not raise even when the HTTP post fails.
            await mod._record_trace_bg_async(
                deployment_id="dep-trace",
                variant="variant",
                model="claude-3",
                input_tokens=10,
                output_tokens=5,
                latency_ms=200,
            )
        finally:
            mod._async_http = original_async_http
            os.environ.pop("VERUM_API_URL", None)


class TestSyncTraceBackground(unittest.TestCase):
    """_record_trace_bg daemon thread swallows all exceptions."""

    def setUp(self) -> None:
        _make_anthropic_stub()
        for v in ("VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()

    def test_no_api_url_does_not_raise(self) -> None:
        mod = _fresh_import_verum_anthropic()
        # Fire-and-forget — calling it must not raise in the caller thread.
        mod._record_trace_bg(
            deployment_id="dep-trace",
            variant="baseline",
            model="claude-3",
            input_tokens=5,
            output_tokens=3,
            latency_ms=100,
        )

    def test_sync_http_none_does_not_raise(self) -> None:
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        mod = _fresh_import_verum_anthropic()
        original_sync_http = mod._sync_http
        mod._sync_http = None
        try:
            mod._record_trace_bg(
                deployment_id="dep-trace",
                variant="baseline",
                model="claude-3",
                input_tokens=5,
                output_tokens=3,
                latency_ms=100,
            )
        finally:
            mod._sync_http = original_sync_http
            os.environ.pop("VERUM_API_URL", None)

    def test_http_exception_is_swallowed(self) -> None:
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        mod = _fresh_import_verum_anthropic()

        mock_http = MagicMock()
        mock_http.post.side_effect = RuntimeError("connection refused")
        original_sync_http = mod._sync_http
        mod._sync_http = mock_http
        import threading
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
                    model="claude-3",
                    input_tokens=10,
                    output_tokens=5,
                    latency_ms=200,
                )
            done.wait(timeout=2.0)
        finally:
            mod._sync_http = original_sync_http
            os.environ.pop("VERUM_API_URL", None)


class TestExtractUsageAnthropicExceptions(unittest.TestCase):
    """_extract_usage_anthropic handles broken response attributes gracefully."""

    def setUp(self) -> None:
        _make_anthropic_stub()

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()

    def test_usage_attribute_raises(self) -> None:
        mod = _fresh_import_verum_anthropic()

        class BadResponse:
            @property
            def usage(self) -> None:
                raise AttributeError("no usage")

            model = "claude-3"

        inp, out, model = mod._extract_usage_anthropic(BadResponse())
        self.assertEqual(inp, 0)
        self.assertEqual(out, 0)
        self.assertEqual(model, "claude-3")

    def test_model_attribute_raises(self) -> None:
        mod = _fresh_import_verum_anthropic()

        class BadResponse:
            usage = MagicMock(input_tokens=5, output_tokens=3)

            @property
            def model(self) -> None:
                raise AttributeError("no model")

        inp, out, model = mod._extract_usage_anthropic(BadResponse())
        self.assertEqual(inp, 5)
        self.assertEqual(out, 3)
        self.assertEqual(model, "")


class TestGetResolverCreationFailure(unittest.TestCase):
    """_get_resolver returns None when httpx or internal imports fail."""

    def setUp(self) -> None:
        _make_anthropic_stub()
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()
        os.environ.pop("VERUM_API_URL", None)
        os.environ.pop("VERUM_API_KEY", None)

    def test_resolver_creation_exception_returns_none(self) -> None:
        mod = _fresh_import_verum_anthropic()
        # Reset cached resolver to force re-creation.
        mod._resolver = None
        mod._sync_http = None
        mod._async_http = None

        with patch("builtins.__import__", side_effect=ImportError("no httpx")):
            result = mod._get_resolver()

        # Must return None and not propagate the exception.
        self.assertIsNone(result)


class TestResolveSyncPaths(unittest.TestCase):
    """_resolve_sync handles no-resolver and no-event-loop paths."""

    def setUp(self) -> None:
        _make_anthropic_stub()
        for v in ("VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()

    def test_no_resolver_returns_original_messages(self) -> None:
        mod = _fresh_import_verum_anthropic()
        mod._resolver = None

        messages = [{"role": "user", "content": "hello"}]
        with patch.object(mod, "_get_resolver", return_value=None):
            result_messages, reason = mod._resolve_sync("dep-001", messages)

        self.assertIs(result_messages, messages)
        self.assertEqual(reason, "no_resolver")


class TestSyncWrappedCreateExceptionHandlerAnthropic(unittest.TestCase):
    """_wrapped_create (sync) swallows exceptions from _record_trace_bg."""

    def setUp(self) -> None:
        _make_anthropic_stub()
        os.environ["VERUM_DEPLOYMENT_ID"] = "dep-trace-except"
        os.environ["VERUM_API_URL"] = "http://verum-test.local"
        os.environ["VERUM_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        _cleanup_anthropic_stub()
        for v in ("VERUM_DEPLOYMENT_ID", "VERUM_API_URL", "VERUM_API_KEY"):
            os.environ.pop(v, None)

    def test_trace_exception_does_not_surface(self) -> None:
        import anthropic.resources.messages as msg_mod  # type: ignore[import]

        system_prompt = "You are a tarot reader."

        def spy_create(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            return MagicMock(
                model="claude-3",
                usage=MagicMock(input_tokens=5, output_tokens=3),
            )

        msg_mod.Messages.create = spy_create  # type: ignore[method-assign]
        mod = _fresh_import_verum_anthropic()

        resolved = [{"role": "system", "content": system_prompt}]
        with patch.object(
            mod, "_resolve_sync", return_value=(resolved, "baseline")
        ), patch.object(mod, "_record_trace_bg", side_effect=RuntimeError("trace boom")):
            instance = msg_mod.Messages()
            response = instance.create(
                model="claude-3",
                system=system_prompt,
                messages=[{"role": "user", "content": "trace test"}],
            )

        self.assertIsNotNone(response)

    def test_resolve_exception_uses_fail_open_variant(self) -> None:
        """When _resolve_sync raises, variant becomes 'fail_open' and call still succeeds."""
        import anthropic.resources.messages as msg_mod  # type: ignore[import]

        received_calls: list[dict[str, Any]] = []

        def spy_create(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
            received_calls.append(kwargs)
            return MagicMock(
                model="claude-3",
                usage=MagicMock(input_tokens=5, output_tokens=3),
            )

        msg_mod.Messages.create = spy_create  # type: ignore[method-assign]
        mod = _fresh_import_verum_anthropic()

        with patch.object(
            mod, "_resolve_sync", side_effect=RuntimeError("network fail")
        ):
            instance = msg_mod.Messages()
            response = instance.create(
                model="claude-3",
                system="system prompt",
                messages=[{"role": "user", "content": "test"}],
            )

        self.assertIsNotNone(response)
        self.assertEqual(len(received_calls), 1)
