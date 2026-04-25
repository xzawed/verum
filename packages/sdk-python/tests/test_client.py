import pytest
import respx
import httpx
from freezegun import freeze_time
from verum import Client
from verum._cache import DeploymentConfigCache
from verum._router import choose_variant


# ── Cache tests ────────────────────────────────────────────────────────────────

def test_cache_miss_returns_none():
    cache = DeploymentConfigCache(ttl=60)
    assert cache.get("dep-1") is None


def test_cache_set_and_hit():
    cache = DeploymentConfigCache(ttl=60)
    config = {"traffic_split": 0.1, "variant_prompt": "CoT prompt", "status": "canary"}
    cache.set("dep-1", config)
    result = cache.get("dep-1")
    assert result == config


def test_cache_expires():
    with freeze_time("2026-01-01 00:00:00") as frozen:
        cache = DeploymentConfigCache(ttl=60)
        cache.set("dep-1", {"traffic_split": 0.1, "variant_prompt": "x", "status": "canary"})
        frozen.tick(delta=61)
        assert cache.get("dep-1") is None


# ── Router tests ────────────────────────────────────────────────────────────────

def test_choose_variant_always_baseline_at_zero():
    for _ in range(100):
        assert choose_variant(0.0) == "baseline"


def test_choose_variant_always_variant_at_one():
    for _ in range(100):
        assert choose_variant(1.0) == "variant"


def test_choose_variant_statistically_correct():
    results = [choose_variant(0.5) for _ in range(1000)]
    variant_count = results.count("variant")
    # Should be roughly 50% ± 10%
    assert 400 < variant_count < 600


# ── Client integration tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_without_deployment_id_passes_through():
    client = Client(api_url="http://verum-test.local", api_key="test-key")

    result = await client.chat(
        messages=[{"role": "user", "content": "Hello"}],
        provider="openai",
        model="gpt-4",
        deployment_id=None,
    )
    assert result["messages"][0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_retrieve_calls_api():
    with respx.mock(base_url="http://verum-test.local") as mock:
        mock.post("/api/v1/retrieve-sdk").mock(
            return_value=httpx.Response(200, json={"chunks": [{"content": "Tarot info"}]})
        )
        client = Client(api_url="http://verum-test.local", api_key="test-key")
        chunks = await client.retrieve(query="what is the Moon card?", collection_name="arcana-tarot-knowledge")
        assert len(chunks) == 1
        assert chunks[0]["content"] == "Tarot info"


@pytest.mark.asyncio
async def test_feedback_calls_api():
    with respx.mock(base_url="http://verum-test.local") as mock:
        mock.post("/api/v1/feedback").mock(return_value=httpx.Response(204))
        client = Client(api_url="http://verum-test.local", api_key="test-key")
        await client.feedback(trace_id="trace-123", score=1)
        assert mock.calls.called


@pytest.mark.asyncio
async def test_record_returns_trace_id():
    with respx.mock(base_url="http://verum-test.local") as mock:
        mock.post("/api/v1/traces").mock(
            return_value=httpx.Response(200, json={"trace_id": "abc-123"})
        )
        client = Client(api_url="http://verum-test.local", api_key="test-key")
        trace_id = await client.record(
            deployment_id="dep-uuid",
            variant="cot",
            model="grok-2-1212",
            input_tokens=512,
            output_tokens=284,
            latency_ms=980,
        )

        assert trace_id == "abc-123"
        assert mock.calls.called
        call = mock.calls[0]
        assert "/api/v1/traces" in str(call.request.url)


# ── Client lifecycle tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_aclose_closes_http_client():
    """aclose() should close the underlying httpx.AsyncClient without error."""
    client = Client(api_url="http://verum-test.local", api_key="test-key")
    await client.aclose()


@pytest.mark.asyncio
async def test_async_context_manager():
    """__aenter__ / __aexit__ work as an async context manager."""
    async with Client(api_url="http://verum-test.local", api_key="test-key") as client:
        assert client is not None


# ── chat() variant path tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_variant_replaces_existing_system_message():
    """When routed to 'variant', the system message content is replaced."""
    import warnings
    with respx.mock(base_url="http://verum-test.local") as mock:
        mock.get("/api/v1/deploy/dep-1/config").mock(
            return_value=httpx.Response(200, json={
                "traffic_split": 1.0,
                "variant_prompt": "You are a CoT tarot reader.",
                "status": "canary",
            })
        )
        client = Client(api_url="http://verum-test.local", api_key="test-key")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = await client.chat(
                messages=[
                    {"role": "system", "content": "original system"},
                    {"role": "user", "content": "hi"},
                ],
                deployment_id="dep-1",
                model="gpt-4",
            )
    assert result["routed_to"] == "variant"
    assert result["messages"][0]["content"] == "You are a CoT tarot reader."
    assert result["messages"][0]["role"] == "system"
    # Second message unchanged
    assert result["messages"][1]["content"] == "hi"


@pytest.mark.asyncio
async def test_chat_variant_prepends_system_message_when_none_exists():
    """When routed to 'variant' and no system message exists, one is prepended."""
    import warnings
    with respx.mock(base_url="http://verum-test.local") as mock:
        mock.get("/api/v1/deploy/dep-2/config").mock(
            return_value=httpx.Response(200, json={
                "traffic_split": 1.0,
                "variant_prompt": "You are a CoT tarot reader.",
                "status": "canary",
            })
        )
        client = Client(api_url="http://verum-test.local", api_key="test-key")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                deployment_id="dep-2",
                model="gpt-4",
            )
    assert result["routed_to"] == "variant"
    assert result["messages"][0]["role"] == "system"
    assert result["messages"][0]["content"] == "You are a CoT tarot reader."
    assert result["messages"][1]["content"] == "hi"


# ── _get_deployment_config cache miss (HTTP fetch) ──────────────────────────────

@pytest.mark.asyncio
async def test_get_deployment_config_cache_miss_fetches_from_api():
    """_get_deployment_config fetches config via HTTP on a cache miss."""
    import warnings
    config_payload = {
        "traffic_split": 0.5,
        "variant_prompt": "variant system prompt",
        "status": "canary",
    }
    with respx.mock(base_url="http://verum-test.local") as mock:
        mock.get("/api/v1/deploy/dep-cache-miss/config").mock(
            return_value=httpx.Response(200, json=config_payload)
        )
        client = Client(api_url="http://verum-test.local", api_key="test-key")
        config = await client._get_deployment_config("dep-cache-miss")
        assert config == config_payload
        # Exactly one HTTP call should have been made
        assert mock.calls.call_count == 1


@pytest.mark.asyncio
async def test_get_deployment_config_cache_hit_skips_http():
    """_get_deployment_config returns cached value without HTTP on cache hit."""
    config_payload = {
        "traffic_split": 0.1,
        "variant_prompt": "cached prompt",
        "status": "canary",
    }
    client = Client(api_url="http://verum-test.local", api_key="test-key")
    # Prime the cache manually
    client._cache.set("dep-cached", config_payload)

    with respx.mock(base_url="http://verum-test.local") as mock:
        config = await client._get_deployment_config("dep-cached")

    assert config == config_payload
    # No HTTP calls should have been made
    assert mock.calls.call_count == 0
