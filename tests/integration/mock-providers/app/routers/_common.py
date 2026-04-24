from __future__ import annotations
import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any
from fastapi import Request, HTTPException

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


async def check_fault(request: Request, endpoint: str) -> None:
    """Raise HTTP error if a fault is scheduled for this endpoint."""
    faults: list[dict] = request.app.state.faults.get(endpoint, [])
    if not faults:
        return
    fault = faults[0]
    import random
    if random.random() < fault.get("p", 1.0):
        faults[0]["count"] = fault.get("count", 1) - 1
        if faults[0]["count"] <= 0:
            faults.pop(0)
        kind = fault.get("kind", "http_503")
        if kind == "http_503":
            raise HTTPException(status_code=503, detail="injected fault")
        elif kind == "http_429":
            from fastapi.responses import JSONResponse
            raise HTTPException(status_code=429, headers={"Retry-After": "1"}, detail="rate limited")
        elif kind == "timeout":
            await asyncio.sleep(120)
        elif kind == "malformed_json":
            from fastapi.responses import PlainTextResponse
            raise HTTPException(status_code=200, detail="}{")


def log_call(request: Request, endpoint: str, body: Any) -> None:
    request.app.state.call_log.append({
        "ts": time.time(),
        "endpoint": endpoint,
        "body_summary": str(body)[:200],
    })


def fixture_key(system: str, last_user: str, model: str) -> str:
    raw = (system[:400] + last_user[:800] + model).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def load_fixture(path: Path) -> dict:
    return json.loads(path.read_text())
