"""Zero-invasive OpenAI integration for Verum.

Importing this module is the *only* change needed in a user's service::

    import verum.openai  # noqa: F401  — patches openai automatically

After import, all ``openai.chat.completions.create()`` calls are
transparently intercepted. Verum reads the deployment config (with a
5-layer safety net), optionally swaps the system prompt, then fires an
async background trace — all without changing the call signature.

Environment variables:
    VERUM_API_URL: Base URL of the Verum API (e.g. https://verum.dev).
    VERUM_API_KEY: Your Verum API key.
    VERUM_DEPLOYMENT_ID: Default deployment ID (overridden by the
        ``x-verum-deployment`` key in ``extra_headers``).
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    pass

_PATCHED = False
_logger = logging.getLogger(__name__)

# Module-level singleton — initialised lazily on first call.
_resolver: Any = None
_resolver_lock = threading.Lock()
_sync_http: Any = None  # httpx.Client for sync trace posting
_async_http: Any = None  # httpx.AsyncClient for async trace posting
_bg_tasks: set[asyncio.Task[Any]] = set()  # prevents GC of fire-and-forget tasks


# ── Resolver singleton ────────────────────────────────────────────────────────


def _get_resolver() -> Any:
    """Return the module-level :class:`_SafeConfigResolver` singleton.

    Returns:
        Configured resolver, or ``None`` when both
        ``VERUM_API_URL`` and ``VERUM_API_KEY`` are absent (no-op mode).
    """
    global _resolver, _sync_http, _async_http  # noqa: PLW0603

    if _resolver is not None:
        return _resolver

    with _resolver_lock:
        if _resolver is not None:  # pragma: no cover
            return _resolver

        api_url = os.environ.get("VERUM_API_URL", "").rstrip("/")
        api_key = os.environ.get("VERUM_API_KEY", "")

        if not api_url and not api_key:
            return None

        try:
            import httpx

            from verum._cache import DeploymentConfigCache
            from verum._safe_resolver import DeploymentConfig, _SafeConfigResolver

            _sync_http = httpx.Client()
            _async_http = httpx.AsyncClient()
            cache: DeploymentConfigCache[DeploymentConfig] = DeploymentConfigCache()
            _resolver = _SafeConfigResolver(
                http_client=_async_http,
                api_url=api_url,
                api_key=api_key,
                cache=cache,
            )
        except Exception:  # noqa: BLE001
            _logger.warning("Verum: failed to create resolver — running in pass-through mode.")
            return None

    return _resolver


# ── Sync resolver bridge ──────────────────────────────────────────────────────


def _resolve_sync(
    deployment_id: str,
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    """Run the async resolver from synchronous code.

    If an event loop is already running in the current thread, we dispatch
    to a fresh thread to avoid ``RuntimeError: This event loop is already
    running``.

    Args:
        deployment_id: Verum deployment UUID.
        messages: Original message list.

    Returns:
        ``(messages, reason)`` tuple from
        :meth:`_SafeConfigResolver.resolve`.
    """
    resolver = _get_resolver()
    if resolver is None:
        return messages, "no_resolver"

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    async def _run() -> tuple[list[dict[str, Any]], str]:
        return await resolver.resolve(deployment_id, messages)

    if loop is None:
        return asyncio.run(_run())

    # An event loop is already running — run in a new thread with its own loop.
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, _run())
        return future.result()


# ── Trace posting ─────────────────────────────────────────────────────────────


def _record_trace_bg(
    *,
    deployment_id: str,
    variant: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
) -> None:
    """Post a trace to Verum in a fire-and-forget daemon thread.

    All exceptions are swallowed — observability must never break the
    user's service.

    Args:
        deployment_id: Verum deployment UUID.
        variant: Routing decision (``"baseline"`` or ``"variant"``).
        model: Model string from the OpenAI response.
        input_tokens: Prompt token count.
        output_tokens: Completion token count.
        latency_ms: Wall-clock latency in milliseconds.
    """

    def _post() -> None:
        try:
            api_url = os.environ.get("VERUM_API_URL", "").rstrip("/")
            api_key = os.environ.get("VERUM_API_KEY", "")
            if not api_url or _sync_http is None:
                return
            _sync_http.post(
                f"{api_url}/api/v1/traces",
                json={
                    "deployment_id": deployment_id,
                    "variant": variant,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": latency_ms,
                },
                headers={"x-verum-api-key": api_key},
                timeout=5.0,
            )
        except Exception:  # noqa: BLE001
            pass

    t = threading.Thread(target=_post, daemon=True)
    t.start()


async def _record_trace_bg_async(
    *,
    deployment_id: str,
    variant: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
) -> None:
    """Post a trace to Verum asynchronously (fire-and-forget).

    Args:
        deployment_id: Verum deployment UUID.
        variant: Routing decision.
        model: Model string from the OpenAI response.
        input_tokens: Prompt token count.
        output_tokens: Completion token count.
        latency_ms: Wall-clock latency in milliseconds.
    """
    try:
        api_url = os.environ.get("VERUM_API_URL", "").rstrip("/")
        api_key = os.environ.get("VERUM_API_KEY", "")
        if not api_url or _async_http is None:
            return
        await _async_http.post(
            f"{api_url}/api/v1/traces",
            json={
                "deployment_id": deployment_id,
                "variant": variant,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
            },
            headers={"x-verum-api-key": api_key},
            timeout=5.0,
        )
    except Exception:  # noqa: BLE001
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_deployment_id(kwargs: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """Extract and remove ``x-verum-deployment`` from ``extra_headers``.

    Falls back to ``VERUM_DEPLOYMENT_ID`` environment variable.

    Args:
        kwargs: The keyword arguments dict to mutate.

    Returns:
        ``(deployment_id, kwargs)`` where ``kwargs`` has the header removed.
    """
    extra_headers = kwargs.get("extra_headers") or {}
    deployment_id: str | None = None

    if isinstance(extra_headers, dict):
        deployment_id = extra_headers.pop("x-verum-deployment", None)
        if not extra_headers:
            # Remove the key entirely to avoid passing an empty dict to OpenAI
            kwargs.pop("extra_headers", None)
        else:
            kwargs["extra_headers"] = extra_headers

    if not deployment_id:
        deployment_id = os.environ.get("VERUM_DEPLOYMENT_ID") or None

    return deployment_id, kwargs


def _extract_usage(response: Any) -> tuple[int, int, str]:
    """Extract token counts and model name from an OpenAI response object.

    Args:
        response: OpenAI ``ChatCompletion`` response object.

    Returns:
        ``(input_tokens, output_tokens, model)`` tuple.
    """
    try:
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
    except Exception:  # noqa: BLE001
        input_tokens = 0
        output_tokens = 0

    try:
        model = response.model or ""
    except Exception:  # noqa: BLE001
        model = ""

    return input_tokens, output_tokens, model


# ── Patching ──────────────────────────────────────────────────────────────────


def _patch_openai() -> None:
    """Monkey-patch ``openai.resources.chat.completions`` with Verum wrappers.

    Idempotent — calling this function more than once is safe.

    Raises:
        ImportError: If the ``openai`` package is not installed.
    """
    global _PATCHED  # noqa: PLW0603

    if _PATCHED:
        return

    try:
        import openai.resources.chat.completions as _completions_mod
    except ImportError as exc:
        raise ImportError(
            "Verum requires the openai package. Install it with: pip install openai"
        ) from exc

    Completions = _completions_mod.Completions
    AsyncCompletions = _completions_mod.AsyncCompletions

    _orig_create = Completions.create
    _orig_acreate = AsyncCompletions.create

    def _wrapped_create(self: Any, *args: Any, **kwargs: Any) -> Any:  # type: ignore[return]
        deployment_id, kwargs = _extract_deployment_id(kwargs)

        if deployment_id is None:
            return _orig_create(self, *args, **kwargs)

        messages: list[dict[str, Any]] = kwargs.get("messages", [])
        try:
            modified_messages, variant = _resolve_sync(deployment_id, messages)
            kwargs["messages"] = modified_messages
        except Exception:  # noqa: BLE001
            variant = "fail_open"

        start = time.monotonic()
        response = _orig_create(self, *args, **kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        try:
            input_tokens, output_tokens, model = _extract_usage(response)
            _record_trace_bg(
                deployment_id=deployment_id,
                variant=variant,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        except Exception:  # noqa: BLE001
            pass

        return response

    async def _wrapped_acreate(self: Any, *args: Any, **kwargs: Any) -> Any:  # type: ignore[return]
        deployment_id, kwargs = _extract_deployment_id(kwargs)

        if deployment_id is None:
            return await _orig_acreate(self, *args, **kwargs)

        messages: list[dict[str, Any]] = kwargs.get("messages", [])
        resolver = _get_resolver()
        variant = "no_resolver"
        if resolver is not None:
            try:
                modified_messages, variant = await resolver.resolve(deployment_id, messages)
                kwargs["messages"] = modified_messages
            except Exception:  # noqa: BLE001
                variant = "fail_open"

        start = time.monotonic()
        response = await _orig_acreate(self, *args, **kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        try:
            input_tokens, output_tokens, model = _extract_usage(response)
            _task = asyncio.create_task(
                _record_trace_bg_async(
                    deployment_id=deployment_id,
                    variant=variant,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )
            )
            _bg_tasks.add(_task)
            _task.add_done_callback(_bg_tasks.discard)
        except Exception:  # noqa: BLE001
            pass

        return response

    Completions.create = _wrapped_create  # type: ignore[method-assign]
    AsyncCompletions.create = _wrapped_acreate  # type: ignore[method-assign]

    _PATCHED = True


# ── Module init ───────────────────────────────────────────────────────────────

try:
    _patch_openai()
except ImportError as _e:
    raise ImportError(str(_e)) from _e
except Exception:  # noqa: BLE001  # pragma: no cover
    # Never break the user's import
    pass

try:
    from verum._instrument import _setup_otel as _setup_otel_fn

    _setup_otel_fn()
except Exception:  # noqa: BLE001  # pragma: no cover
    pass
