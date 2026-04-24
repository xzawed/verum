from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ._common import check_fault, log_call, fixture_key, FIXTURES_DIR

router = APIRouter()
_FIXTURES = FIXTURES_DIR / "anthropic"

_FALLBACK = {
    "id": "msg_mock",
    "type": "message",
    "role": "assistant",
    "content": [{"type": "text", "text": '{"domain":"divination/tarot","tone":"mystical","language":"korean","user_type":"consumer","confidence":0.9,"summary":"Tarot reading service"}'}],
    "model": "claude-sonnet-4-6",
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 100, "output_tokens": 50},
}


@router.post("/v1/messages")
async def messages(request: Request):
    await check_fault(request, "anthropic")
    body = await request.json()
    system = body.get("system", "")
    messages_list = body.get("messages", [])
    last_user = messages_list[-1].get("content", "") if messages_list else ""
    model = body.get("model", "")
    log_call(request, "anthropic/v1/messages", {"model": model, "system_len": len(system)})

    key = fixture_key(system, last_user, model)
    fixture_path = _FIXTURES / f"{key}.json"
    if fixture_path.exists():
        return JSONResponse(json.loads(fixture_path.read_text()))
    # Try named fixtures — match on system prompt or last user message
    for f in _FIXTURES.glob("*.json"):
        data = json.loads(f.read_text())
        if data.get("_match_system_contains") and data["_match_system_contains"] in system:
            resp = {k: v for k, v in data.items() if not k.startswith("_")}
            return JSONResponse(resp)
        if data.get("_match_user_contains") and data["_match_user_contains"] in last_user:
            resp = {k: v for k, v in data.items() if not k.startswith("_")}
            return JSONResponse(resp)
    if request.app.state.strict:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"No fixture for key {key}. system[:80]={system[:80]!r}")
    return JSONResponse(_FALLBACK)
