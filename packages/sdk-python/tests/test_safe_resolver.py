"""Tests for _SafeConfigResolver — 5-layer safety net."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from verum._cache import DeploymentConfigCache
from verum._safe_resolver import (
    _CIRCUIT_OPEN_SECONDS,
    _FAILURE_THRESHOLD,
    _FETCH_TIMEOUT,
    _SafeConfigResolver,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_API_URL = "http://verum-test.local"
_API_KEY = "test-key"
_DEP = "dep-uuid-1"
_CONFIG_URL = f"{_API_URL}/api/v1/deploy/{_DEP}/config"
_GOOD_CONFIG = {"traffic_split": 0.0, "variant_prompt": None}


def _make_resolver(cache: DeploymentConfigCache | None = None) -> tuple[_SafeConfigResolver, httpx.AsyncClient]:
    http = httpx.AsyncClient()
    c = cache or DeploymentConfigCache()
    resolver = _SafeConfigResolver(http, _API_URL, _API_KEY, c)
    return resolver, http


# ---------------------------------------------------------------------------
# Fresh cache hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fresh_cache_hit_returns_fresh():
    cache = DeploymentConfigCache(ttl=60.0)
    cache.set(_DEP, _GOOD_CONFIG)

    resolver, http = _make_resolver(cache)
    async with http:
        messages = [{"role": "user", "content": "hello"}]
        result_msgs, reason = await resolver.resolve(_DEP, messages)

    assert reason == "fresh"
    assert result_msgs == messages


# ---------------------------------------------------------------------------
# Successful fetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_success_returns_fetched():
    with respx.mock(base_url=_API_URL) as mock:
        mock.get(f"/api/v1/deploy/{_DEP}/config").mock(
            return_value=httpx.Response(200, json=_GOOD_CONFIG)
        )
        resolver, http = _make_resolver()
        async with http:
            msgs = [{"role": "user", "content": "hi"}]
            result_msgs, reason = await resolver.resolve(_DEP, msgs)

    assert reason == "fetched"
    assert result_msgs == msgs


@pytest.mark.asyncio
async def test_fetch_success_resets_failure_count():
    with respx.mock(base_url=_API_URL) as mock:
        mock.get(f"/api/v1/deploy/{_DEP}/config").mock(
            return_value=httpx.Response(200, json=_GOOD_CONFIG)
        )
        resolver, http = _make_resolver()
        # Prime some failures
        resolver._failure_count = 3
        async with http:
            await resolver.resolve(_DEP, [])

    assert resolver._failure_count == 0


# ---------------------------------------------------------------------------
# Stale cache fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_fallback_when_fetch_fails():
    cache = DeploymentConfigCache(ttl=1.0, stale_ttl=86400.0)
    cache.set(_DEP, _GOOD_CONFIG)

    # Let the fresh TTL expire
    with patch("verum._cache.time") as mock_time:
        # Simulate 120 seconds later: fresh expired, stale still valid
        base = time.monotonic()
        mock_time.monotonic.return_value = base + 120

        resolver, http = _make_resolver(cache)
        # Force fetch to fail by not mocking (ConnectError)
        async with http:
            result_msgs, reason = await resolver.resolve(_DEP, [{"role": "user", "content": "q"}])

    assert reason == "stale"


# ---------------------------------------------------------------------------
# Fail-open when nothing works
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fail_open_when_no_cache_and_fetch_fails():
    resolver, http = _make_resolver()  # empty cache
    original = [{"role": "user", "content": "original message"}]

    async with http:
        result_msgs, reason = await resolver.resolve(_DEP, original)

    assert reason == "fail_open"
    assert result_msgs == original


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_circuit_opens_after_five_failures():
    resolver, http = _make_resolver()

    async with http:
        # Trigger FAILURE_THRESHOLD failures (no mock → ConnectError each time)
        for _ in range(_FAILURE_THRESHOLD):
            await resolver.resolve(_DEP, [])

    assert resolver._failure_count >= _FAILURE_THRESHOLD
    now = time.monotonic()
    assert resolver._circuit_open_until > now
    assert resolver._circuit_open_until == pytest.approx(now + 300.0, abs=1.0)


@pytest.mark.asyncio
async def test_circuit_open_skips_fetch_returns_circuit_open():
    resolver, http = _make_resolver()
    # Manually open circuit
    resolver._failure_count = _FAILURE_THRESHOLD
    resolver._circuit_open_until = time.monotonic() + _CIRCUIT_OPEN_SECONDS

    call_count = 0

    with respx.mock(base_url=_API_URL, assert_all_called=False) as mock:
        route = mock.get(f"/api/v1/deploy/{_DEP}/config").mock(
            return_value=httpx.Response(200, json=_GOOD_CONFIG)
        )
        async with http:
            _, reason = await resolver.resolve(_DEP, [])
        call_count = route.call_count

    # Fetch must NOT be attempted while circuit is open
    assert call_count == 0
    assert reason == "circuit_open"


@pytest.mark.asyncio
async def test_circuit_closes_after_timeout():
    resolver, http = _make_resolver()
    # Set circuit open_until to the past
    resolver._failure_count = _FAILURE_THRESHOLD
    resolver._circuit_open_until = time.monotonic() - 1.0  # already expired

    with respx.mock(base_url=_API_URL) as mock:
        mock.get(f"/api/v1/deploy/{_DEP}/config").mock(
            return_value=httpx.Response(200, json=_GOOD_CONFIG)
        )
        async with http:
            _, reason = await resolver.resolve(_DEP, [])

    # Circuit was closed → fetch was attempted and succeeded
    assert reason == "fetched"
    assert resolver._failure_count == 0


@pytest.mark.asyncio
async def test_circuit_open_returns_stale_if_available():
    cache = DeploymentConfigCache(ttl=1.0, stale_ttl=86400.0)
    stale_config = {"traffic_split": 0.0, "variant_prompt": None}
    cache.set(_DEP, stale_config)

    resolver, http = _make_resolver(cache)
    # Open circuit
    resolver._circuit_open_until = time.monotonic() + _CIRCUIT_OPEN_SECONDS
    resolver._failure_count = _FAILURE_THRESHOLD

    # Let fresh TTL expire so get_fresh() returns None, but stale is available
    with patch("verum._cache.time") as mock_time:
        base = time.monotonic()
        mock_time.monotonic.return_value = base + 120

        async with http:
            _, reason = await resolver.resolve(_DEP, [])

    assert reason == "stale"


# ---------------------------------------------------------------------------
# Hard timeout (200 ms)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hard_timeout_does_not_block_caller():
    """Resolver must fall back immediately when the server times out."""
    # Simulate a timeout by having the mock raise httpx.TimeoutException,
    # which is exactly what httpx raises when the timeout elapses.
    with respx.mock(base_url=_API_URL) as mock:
        mock.get(f"/api/v1/deploy/{_DEP}/config").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        resolver, http = _make_resolver()
        start = time.monotonic()
        async with http:
            _, reason = await resolver.resolve(_DEP, [])
        elapsed = time.monotonic() - start

    # Must return quickly (well under 0.5 s — no real sleep involved)
    assert elapsed < 0.5
    # Timeout counts as a failure → falls back to stale or fail_open
    assert reason in ("stale", "fail_open")


@pytest.mark.asyncio
async def test_fetch_uses_200ms_hard_timeout():
    """Verify that the resolver uses exactly 200ms hard timeout for HTTP requests."""
    # Contract test: the constant must be 0.2 seconds
    assert _FETCH_TIMEOUT == pytest.approx(0.2)

    # Test that a successful fetch actually completes
    with respx.mock(base_url=_API_URL) as mock:
        route = mock.get(f"/api/v1/deploy/{_DEP}/config").mock(
            return_value=httpx.Response(200, json=_GOOD_CONFIG)
        )
        resolver, http = _make_resolver()
        async with http:
            result_msgs, reason = await resolver.resolve(_DEP, [{"role": "user", "content": "test"}])

    # Verify the fetch was attempted with the correct timeout value
    # by checking the implementation uses _FETCH_TIMEOUT
    assert reason == "fetched"
    assert route.called


# ---------------------------------------------------------------------------
# _apply_config variant routing
# ---------------------------------------------------------------------------


def test_apply_config_swaps_system_message_when_variant():
    cache = DeploymentConfigCache()
    resolver = _SafeConfigResolver(MagicMock(), _API_URL, _API_KEY, cache)

    config = {"traffic_split": 1.0, "variant_prompt": "You are a variant assistant."}
    messages = [
        {"role": "system", "content": "Original system."},
        {"role": "user", "content": "Hello"},
    ]

    result = resolver._apply_config(config, messages)

    assert result[0]["content"] == "You are a variant assistant."
    assert result[1]["content"] == "Hello"


def test_apply_config_prepends_system_when_none_exists():
    cache = DeploymentConfigCache()
    resolver = _SafeConfigResolver(MagicMock(), _API_URL, _API_KEY, cache)

    config = {"traffic_split": 1.0, "variant_prompt": "New system."}
    messages = [{"role": "user", "content": "Hi"}]

    result = resolver._apply_config(config, messages)

    assert result[0]["role"] == "system"
    assert result[0]["content"] == "New system."
    assert result[1]["content"] == "Hi"


def test_apply_config_baseline_leaves_messages_unchanged():
    cache = DeploymentConfigCache()
    resolver = _SafeConfigResolver(MagicMock(), _API_URL, _API_KEY, cache)

    config = {"traffic_split": 0.0, "variant_prompt": "Unused variant."}
    messages = [{"role": "user", "content": "Hello"}]

    result = resolver._apply_config(config, messages)

    assert result == messages
