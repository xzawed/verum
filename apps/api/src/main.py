import logging
import os

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.db.session import AsyncSessionLocal
from src.integrations.github.router import router as me_router
from src.loop.analyze.router import router as analyze_router
from src.loop.harvest.router import router as harvest_router
from src.loop.infer.router import router as infer_router

logger = logging.getLogger(__name__)

_VERUM_ENV = os.environ.get("VERUM_ENV", "development")
if _VERUM_ENV == "production" and not os.environ.get("NEXTAUTH_SECRET"):
    raise RuntimeError("NEXTAUTH_SECRET must be set in production")

app = FastAPI(title="Verum API", version="0.0.0")
app.include_router(me_router)
app.include_router(analyze_router)
app.include_router(infer_router)
app.include_router(harvest_router)


@app.get("/health")
async def health() -> dict[str, str]:
    db_status = "disconnected"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except SQLAlchemyError as exc:
        logger.warning("Health DB check failed: %s", exc)
    return {"status": "ok", "version": "0.0.0", "db": db_status}
