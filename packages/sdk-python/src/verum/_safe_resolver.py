"""Fault-tolerant config resolver with 5-layer safety net."""
from __future__ import annotations

import time
from typing import Any, TypedDict

import httpx

from verum._cache import DeploymentConfigCache
from verum._router import choose_variant

# Circuit breaker thresholds
_FAILURE_THRESHOLD = 5
_CIRCUIT_OPEN_SECONDS = 300.0

# Hard timeout for config fetches (200 ms)
_FETCH_TIMEOUT = 0.2


class DeploymentConfig(TypedDict, total=False):
    """Shape of a deployment config returned by the Verum API."""

    traffic_split: float
    variant_prompt: str | None


class _SafeConfigResolver:
    """Resolve deployment config without ever raising to the caller's LLM path.

    Safety-net priority (highest to lowest):
      1. circuit_open  — circuit is open, skip fetch entirely
      2. fresh_cache   — config is fresh (within TTL), use it immediately
      3. fetched       — fetch succeeded within 200 ms hard timeout
      4. stale_cache   — fetch failed but stale copy exists (up to 24 h)
      5. fail_open     — nothing works; return original messages unchanged
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        api_url: str,
        api_key: str,
        cache: DeploymentConfigCache[dict[str, Any]],
    ) -> None:
        """Initialise the resolver.

        Args:
            http_client: Shared :class:`httpx.AsyncClient` instance.
            api_url: Base URL of the Verum API (no trailing slash).
            api_key: Verum API key sent as ``x-verum-api-key``.
            cache: :class:`DeploymentConfigCache` shared with the main client.
        """
        self._http = http_client
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._cache = cache
        self._failure_count: int = 0
        self._circuit_open_until: float = 0.0

    # ── Public ────────────────────────────────────────────────────────────────

    async def resolve(
        self,
        deployment_id: str,
        fallback_messages: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], str]:
        """Resolve the deployment config and apply it to *fallback_messages*.

        Args:
            deployment_id: Verum deployment UUID.
            fallback_messages: Original LLM message list (OpenAI-compatible).

        Returns:
            A ``(messages, reason)`` tuple where ``reason`` is one of:
            ``"fresh"``, ``"fetched"``, ``"stale"``, ``"circuit_open"``,
            or ``"fail_open"``.
        """
        # Layer 1 — circuit open
        if self._is_circuit_open():
            stale = self._cache.get_stale(deployment_id)
            if stale is not None:
                return self._apply_config(stale, fallback_messages), "stale"
            return list(fallback_messages), "circuit_open"

        # Layer 2 — fresh cache hit
        fresh = self._cache.get_fresh(deployment_id)
        if fresh is not None:
            return self._apply_config(fresh, fallback_messages), "fresh"

        # Layer 3 — fetch with hard 200 ms timeout
        config = await self._fetch(deployment_id)
        if config is not None:
            self._cache.set(deployment_id, config)
            self._on_success()
            return self._apply_config(config, fallback_messages), "fetched"

        # Layer 4 — stale cache fallback
        stale = self._cache.get_stale(deployment_id)
        if stale is not None:
            return self._apply_config(stale, fallback_messages), "stale"

        # Layer 5 — fail open
        return list(fallback_messages), "fail_open"

    # ── Internal ──────────────────────────────────────────────────────────────

    def _is_circuit_open(self) -> bool:
        """Return True if the circuit breaker is currently open."""
        return time.monotonic() < self._circuit_open_until

    def _on_failure(self) -> None:
        """Record a fetch failure and open the circuit after the threshold."""
        self._failure_count += 1
        if self._failure_count >= _FAILURE_THRESHOLD:
            self._circuit_open_until = time.monotonic() + _CIRCUIT_OPEN_SECONDS

    def _on_success(self) -> None:
        """Reset the circuit breaker on a successful fetch."""
        self._failure_count = 0
        self._circuit_open_until = 0.0

    async def _fetch(self, deployment_id: str) -> DeploymentConfig | None:
        """Fetch config from the API with a hard 200 ms timeout.

        Args:
            deployment_id: Verum deployment UUID.

        Returns:
            Config dict on success, or None on any failure (network error,
            non-2xx status, or timeout).
        """
        url = f"{self._api_url}/api/v1/deploy/{deployment_id}/config"
        headers = {"x-verum-api-key": self._api_key}
        try:
            resp = await self._http.get(url, headers=headers, timeout=_FETCH_TIMEOUT)
            resp.raise_for_status()
            result: DeploymentConfig = resp.json()
            return result
        except Exception:  # noqa: BLE001
            self._on_failure()
            return None

    def _apply_config(
        self,
        config: DeploymentConfig,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Apply the deployment config to the message list.

        If the router selects the variant and ``variant_prompt`` is present,
        the system message is swapped (or prepended if absent).

        Args:
            config: Deployment config with ``traffic_split`` and optional
                ``variant_prompt`` keys.
            messages: Original LLM message list.

        Returns:
            Possibly modified copy of the message list.
        """
        routed_to = choose_variant(config.get("traffic_split", 0.0))
        if routed_to != "variant" or not config.get("variant_prompt"):
            return list(messages)

        out = list(messages)
        if out and out[0].get("role") == "system":
            out[0] = {**out[0], "content": config["variant_prompt"]}
        else:
            out = [{"role": "system", "content": config["variant_prompt"]}, *out]
        return out
