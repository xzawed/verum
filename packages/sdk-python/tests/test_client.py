import time
import pytest
import respx
import httpx
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
    cache = DeploymentConfigCache(ttl=0)  # instant expiry
    cache.set("dep-1", {"traffic_split": 0.1, "variant_prompt": "x", "status": "canary"})
    time.sleep(0.01)
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
