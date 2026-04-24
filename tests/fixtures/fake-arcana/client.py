"""Fake ArcanaInsight SDK workload runner for integration testing.

Waits for /integration-state/deployment_info.json written by test_30,
then drives N LLM calls through the Verum observability path (record/feedback).
Uses forced 50/50 variant split so both variants reach MIN_SAMPLES quickly.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path

import httpx
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fake-arcana")

STATE_FILE = Path(os.environ.get("INTEGRATION_STATE_DIR", "/integration-state")) / "deployment_info.json"
VERUM_URL = os.environ.get("VERUM_APP_URL", "http://verum-app:8080")
OPENAI_BASE = os.environ.get("OPENAI_BASE_URL", "http://mock-providers:9000/openai/v1")
POLL_INTERVAL = 2
POLL_TIMEOUT = 300


async def _wait_for_state() -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT
    while time.monotonic() < deadline:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text())
            if data.get("deployment_id") and data.get("api_key"):
                logger.info("Got deployment_info: deployment_id=%s", data["deployment_id"])
                return data
        logger.info("Waiting for deployment_info.json...")
        await asyncio.sleep(POLL_INTERVAL)
    raise TimeoutError(f"deployment_info.json not found within {POLL_TIMEOUT}s")


async def _fake_llm_call(messages: list[dict]) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{OPENAI_BASE}/chat/completions",
            json={"model": "gpt-4o-mini", "messages": messages},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()


async def _record_trace(
    api_key: str,
    deployment_id: str,
    variant: str,
    model: str,
    usage: dict,
    latency_ms: int,
) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{VERUM_URL}/api/v1/traces",
            json={
                "deployment_id": deployment_id,
                "variant": variant,
                "model": model,
                "input_tokens": usage.get("prompt_tokens", 50),
                "output_tokens": usage.get("completion_tokens", 30),
                "latency_ms": latency_ms,
            },
            headers={"x-verum-api-key": api_key},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["trace_id"]


async def _run_workload(deployment_id: str, api_key: str, workload: dict) -> None:
    total = workload.get("total_calls", 210)
    model = workload.get("model", "gpt-4o-mini")
    messages = workload.get("messages", [{"role": "user", "content": "타로 카드 리딩"}])
    force_split = workload.get("force_split", True)

    success = 0
    for i in range(total):
        # Force deterministic 50/50 split: even=original, odd=variant
        if force_split:
            variant = "variant" if i % 2 == 1 else "original"
        else:
            variant = "original"

        t0 = time.monotonic()
        try:
            result = await _fake_llm_call(messages)
            latency_ms = int((time.monotonic() - t0) * 1000)
            usage = result.get("usage", {})
            await _record_trace(api_key, deployment_id, variant, model, usage, latency_ms)
            success += 1
        except Exception as exc:
            logger.warning("call %d failed: %s", i, exc)

        if (i + 1) % 50 == 0:
            logger.info("Progress: %d/%d calls complete (%d success)", i + 1, total, success)

        # Small pause to avoid overwhelming the service
        await asyncio.sleep(0.05)

    logger.info("Workload complete: %d/%d successful traces recorded", success, total)


async def main() -> None:
    workload_path = Path(__file__).parent / "workload.yaml"
    workload = yaml.safe_load(workload_path.read_text())

    info = await _wait_for_state()
    deployment_id = info["deployment_id"]
    api_key = info["api_key"]

    logger.info("Starting workload: %d calls for deployment %s", workload.get("total_calls", 210), deployment_id)
    await _run_workload(deployment_id, api_key, workload)


if __name__ == "__main__":
    asyncio.run(main())
