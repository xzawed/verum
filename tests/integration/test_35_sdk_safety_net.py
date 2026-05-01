"""Integration: ADR-017 — Verum config failures must not block LLM calls.

Prerequisites: make integration-up (runs test_30 first to create a deployment).
These tests enable the fault-injection endpoint, trigger fake-arcana to make
LLM calls, then verify that the calls reached the mock-providers despite Verum
returning 503 on the config endpoint.
"""
from __future__ import annotations

import pytest
import httpx

from utils.wait import wait_until

pytestmark = pytest.mark.integration


async def _call_log_count(mock_control: httpx.AsyncClient, endpoint_substr: str) -> int:
    """Return how many mock-provider calls contain `endpoint_substr`."""
    resp = await mock_control.get("/control/calls")
    resp.raise_for_status()
    calls = resp.json()
    return sum(1 for c in calls if endpoint_substr in c.get("endpoint", ""))


@pytest.mark.asyncio
async def test_config_fault_503_does_not_block_llm_calls(
    dashboard_client: httpx.AsyncClient,
    mock_control: httpx.AsyncClient,
    pipeline_state: dict,
) -> None:
    """When Verum's config endpoint returns 503, fake-arcana must still
    complete LLM calls (fail-open behaviour guaranteed by ADR-017)."""
    deployment_id = pipeline_state.get("deployment_id")
    if not deployment_id:
        pytest.skip("No deployment_id in pipeline_state — run test_30 first")

    # Capture LLM call baseline before injecting fault
    baseline = await _call_log_count(mock_control, "/chat/completions")

    # Enable config fault for the next 10 requests (more than fake-arcana will send)
    resp = await dashboard_client.post(
        "/api/test/set-config-fault",
        json={"count": 10},
    )
    assert resp.status_code == 200, (
        f"set-config-fault returned {resp.status_code}: {resp.text}"
    )

    try:
        # Trigger fake-arcana to make 5 LLM calls via the SDK
        async with httpx.AsyncClient(
            base_url=dashboard_client.base_url,
            cookies=dict(dashboard_client.cookies),
            timeout=30.0,
        ) as client:
            trigger_resp = await client.post(
                "/api/test/trigger-arcana",
                json={"calls": 5},
            )
            # If trigger endpoint doesn't exist, skip gracefully
            if trigger_resp.status_code == 404:
                pytest.skip(
                    "fake-arcana trigger endpoint not available in this environment"
                )
            assert trigger_resp.status_code == 200, (
                f"trigger-arcana returned {trigger_resp.status_code}: {trigger_resp.text}"
            )

        # Wait up to 15 s for at least 5 new LLM calls to appear in mock-providers log
        async def _enough_calls() -> bool:
            current = await _call_log_count(mock_control, "/chat/completions")
            return current >= baseline + 5

        await wait_until(
            _enough_calls,
            timeout=15.0,
            interval=0.5,
            label="5 new LLM calls after config fault",
        )
        # wait_until raises TimeoutError if the condition is never met — reaching
        # this line means the assertion passed.
    except TimeoutError as exc:
        pytest.fail(
            "LLM calls did not reach mock-providers while Verum config was returning 503. "
            f"ADR-017 fail-open guarantee is broken. Detail: {exc}"
        )
    finally:
        # Always reset fault so subsequent tests are not affected
        await dashboard_client.delete("/api/test/set-config-fault")


@pytest.mark.asyncio
async def test_config_fault_resets_cleanly(
    dashboard_client: httpx.AsyncClient,
) -> None:
    """After DELETE /api/test/set-config-fault, the config endpoint must return 200."""
    resp = await dashboard_client.post(
        "/api/test/set-config-fault",
        json={"count": 999},
    )
    assert resp.status_code == 200

    # Reset
    reset_resp = await dashboard_client.delete("/api/test/set-config-fault")
    assert reset_resp.status_code == 200

    # Config endpoint should now work normally (we verify it returns non-503 for an invalid key)
    config_resp = await dashboard_client.get(
        "/api/v1/deploy/any-id/config",
        headers={"x-verum-api-key": "invalid-key"},
    )
    assert config_resp.status_code in (401, 403, 404), (
        f"After fault reset, expected auth error, got {config_resp.status_code}"
    )
