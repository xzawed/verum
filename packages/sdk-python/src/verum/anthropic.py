"""Zero-invasive Anthropic integration for Verum.

Importing this module is the *only* change needed in a user's service::

    import verum.anthropic  # noqa: F401  — patches anthropic automatically

After import, all ``anthropic.Anthropic().messages.create()`` and
``anthropic.AsyncAnthropic().messages.create()`` calls are transparently
intercepted.

The Anthropic SDK places the system prompt in a top-level ``system``
kwarg (not inside the ``messages`` list). Verum synthesises a
``[{"role": "system", "content": ...}]`` list to pass through the
resolver, then extracts any modified system prompt back out.

Environment variables:
    VERUM_API_URL: Base URL of the Verum API.
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
from typing import Any

_PATCHED = False
_logger = logging.getLogger(__name__)

# Shared singleton state reused from the openai module if already initialised,
# otherwise created here on demand.
_resolver: Any = None
_resolver_lock = threading.Lock()
_sync_http: Any = None
_async_http: Any = None


# ── Resolver singleton ────────────────────────────────────────────────────────


def _get_resolver() -> Any:
    """Return the module-level :class:`_SafeConfigResolver` singleton.

    Returns:
        Configured resolver, or ``None`` in no-op mode.
    """
    global _resolver, _sync_http, _async_http  # noqa: PLW0603

    if _resolver is not None:
        return _resolver

    with _resolver_lock:
        if _resolver is not None:
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

    Args:
        deployment_id: Verum deployment UUID.
        messages: Synthetic message list (system message first).

    Returns:
        ``(messages, reason)`` from :meth:`_SafeConfigResolver.resolve`.
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

    Args:
        deployment_id: Verum deployment UUID.
        variant: Routing decision.
        model: Model string from the Anthropic response.
        input_tokens: Input token count.
        output_tokens: Output token count.
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
        model: Model string.
        input_tokens: Input token count.
        output_tokens: Output token count.
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

    Args:
        kwargs: The keyword arguments dict.

    Returns:
        ``(deployment_id, kwargs)`` with header removed.
    """
    extra_headers = kwargs.get("extra_headers") or {}
    deployment_id: str | None = None

    if isinstance(extra_headers, dict):
        deployment_id = extra_headers.pop("x-verum-deployment", None)
        if not extra_headers:
            kwargs.pop("extra_headers", None)
        else:
            kwargs["extra_headers"] = extra_headers

    if not deployment_id:
        deployment_id = os.environ.get("VERUM_DEPLOYMENT_ID") or None

    return deployment_id, kwargs


def _build_synthetic_messages(system: str) -> list[dict[str, Any]]:
    """Wrap the Anthropic ``system`` string as a synthetic message list.

    Args:
        system: The system prompt string.

    Returns:
        ``[{"role": "system", "content": system}]``
    """
    return [{"role": "system", "content": system}]


def _apply_resolved_messages(
    kwargs: dict[str, Any],
    resolved: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write back any modified system prompt from resolved messages.

    If the first resolved message has ``role == "system"``, its content
    is set as ``kwargs["system"]``.

    Args:
        kwargs: Original keyword arguments.
        resolved: Messages returned by the resolver.

    Returns:
        Updated kwargs dict.
    """
    if resolved and resolved[0].get("role") == "system":
        kwargs["system"] = resolved[0]["content"]
    return kwargs


def _extract_usage_anthropic(response: Any) -> tuple[int, int, str]:
    """Extract token counts and model from an Anthropic response object.

    Args:
        response: Anthropic ``Message`` response object.

    Returns:
        ``(input_tokens, output_tokens, model)`` tuple.
    """
    try:
        usage = response.usage
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0
    except Exception:  # noqa: BLE001
        input_tokens = 0
        output_tokens = 0

    try:
        model = response.model or ""
    except Exception:  # noqa: BLE001
        model = ""

    return input_tokens, output_tokens, model


# ── Patching ──────────────────────────────────────────────────────────────────


def _patch_anthropic() -> None:
    """Monkey-patch ``anthropic`` messages.create with Verum wrappers.

    Idempotent — calling this more than once is safe.

    Raises:
        ImportError: If the ``anthropic`` package is not installed.
    """
    global _PATCHED  # noqa: PLW0603

    if _PATCHED:
        return

    try:
        import anthropic.resources.messages as _messages_mod
    except ImportError as exc:
        raise ImportError(
            "Verum requires the anthropic package. Install it with: pip install anthropic"
        ) from exc

    Messages = _messages_mod.Messages
    AsyncMessages = _messages_mod.AsyncMessages

    _orig_create = Messages.create
    _orig_acreate = AsyncMessages.create

    def _wrapped_create(self: Any, *args: Any, **kwargs: Any) -> Any:  # type: ignore[return]
        deployment_id, kwargs = _extract_deployment_id(kwargs)

        if deployment_id is None:
            return _orig_create(self, *args, **kwargs)

        system_text: str = kwargs.get("system", "")
        synthetic = _build_synthetic_messages(system_text)
        variant = "no_resolver"
        try:
            resolved, variant = _resolve_sync(deployment_id, synthetic)
            kwargs = _apply_resolved_messages(kwargs, resolved)
        except Exception:  # noqa: BLE001
            variant = "fail_open"

        start = time.monotonic()
        response = _orig_create(self, *args, **kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        try:
            input_tokens, output_tokens, model = _extract_usage_anthropic(response)
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

        system_text: str = kwargs.get("system", "")
        synthetic = _build_synthetic_messages(system_text)
        resolver = _get_resolver()
        variant = "no_resolver"
        if resolver is not None:
            try:
                resolved, variant = await resolver.resolve(deployment_id, synthetic)
                kwargs = _apply_resolved_messages(kwargs, resolved)
            except Exception:  # noqa: BLE001
                variant = "fail_open"

        start = time.monotonic()
        response = await _orig_acreate(self, *args, **kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        try:
            input_tokens, output_tokens, model = _extract_usage_anthropic(response)
            asyncio.create_task(
                _record_trace_bg_async(
                    deployment_id=deployment_id,
                    variant=variant,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )
            )
        except Exception:  # noqa: BLE001
            pass

        return response

    Messages.create = _wrapped_create  # type: ignore[method-assign]
    AsyncMessages.create = _wrapped_acreate  # type: ignore[method-assign]

    _PATCHED = True


# ── Module init ───────────────────────────────────────────────────────────────

try:
    _patch_anthropic()
except ImportError as _e:
    raise ImportError(str(_e)) from _e
except Exception:  # noqa: BLE001
    pass

try:
    from verum._instrument import _setup_otel as _setup_otel_fn

    _setup_otel_fn()
except Exception:  # noqa: BLE001
    pass
