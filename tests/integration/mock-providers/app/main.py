from __future__ import annotations
import os
from fastapi import FastAPI
from .routers import anthropic, voyage, openai_router, github, wiki, control

app = FastAPI(title="Verum Mock Providers")
app.state.faults: dict[str, list[dict]] = {}
app.state.call_log: list[dict] = []
app.state.mock_seed: int = int(os.environ.get("MOCK_SEED", "42"))
app.state.latency_ms: int = int(os.environ.get("MOCK_LATENCY_MS", "0"))
app.state.strict: bool = os.environ.get("MOCK_FIXTURE_STRICT", "0") == "1"

app.include_router(anthropic.router, prefix="/anthropic")
app.include_router(voyage.router, prefix="/voyage")
app.include_router(openai_router.router, prefix="/openai")
app.include_router(github.router, prefix="/github")
app.include_router(wiki.router, prefix="/wiki")
app.include_router(control.router, prefix="/control")


@app.get("/health")
async def health():
    return {"status": "ok"}
