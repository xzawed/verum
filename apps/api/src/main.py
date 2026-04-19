from fastapi import FastAPI
from sqlalchemy import text

from src.db.session import AsyncSessionLocal
from src.loop.analyze.router import router as analyze_router
from src.loop.infer.router import router as infer_router
from src.loop.harvest.router import router as harvest_router

app = FastAPI(title="Verum API", version="0.0.0")
app.include_router(analyze_router)
app.include_router(infer_router)
app.include_router(harvest_router)


@app.get("/health")
async def health() -> dict:
    db_status = "disconnected"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        pass
    return {"status": "ok", "version": "0.0.0", "db": db_status}
