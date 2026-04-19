# Phase 0 stub — implements F-0.9 (/health endpoint only)
# Real loop stage routes are added in Phase 1+

from fastapi import FastAPI

app = FastAPI(title="Verum API", version="0.0.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.0.0", "db": "disconnected"}
