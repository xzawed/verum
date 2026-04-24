from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


class FaultSpec(BaseModel):
    endpoint: str
    kind: str = "http_503"
    count: int = 1
    p: float = 1.0


@router.post("/fault")
async def inject_fault(spec: FaultSpec, request: Request):
    faults = request.app.state.faults
    if spec.endpoint not in faults:
        faults[spec.endpoint] = []
    faults[spec.endpoint].append({"kind": spec.kind, "count": spec.count, "p": spec.p})
    return JSONResponse({"ok": True, "pending": faults[spec.endpoint]})


@router.post("/reset")
async def reset(request: Request):
    request.app.state.faults.clear()
    request.app.state.call_log.clear()
    return JSONResponse({"ok": True})


@router.get("/calls")
async def get_calls(request: Request):
    return JSONResponse(request.app.state.call_log)


@router.post("/seed")
async def set_seed(request: Request):
    body = await request.json()
    request.app.state.mock_seed = int(body.get("seed", 42))
    return JSONResponse({"ok": True, "seed": request.app.state.mock_seed})
