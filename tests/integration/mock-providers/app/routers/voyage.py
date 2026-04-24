from __future__ import annotations
import numpy as np
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ._common import check_fault, log_call

router = APIRouter()
DIM = 1024


def _det_embedding(text: str, seed_offset: int = 0) -> list[float]:
    seed = abs(hash(text)) % (2**31) + seed_offset
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(DIM)
    vec = vec / (np.linalg.norm(vec) + 1e-9)
    return vec.tolist()


@router.post("/v1/embeddings")
async def embeddings(request: Request):
    await check_fault(request, "voyage")
    body = await request.json()
    inputs = body.get("input", [])
    if isinstance(inputs, str):
        inputs = [inputs]
    log_call(request, "voyage/v1/embeddings", {"n": len(inputs)})
    data = [{"embedding": _det_embedding(t), "index": i} for i, t in enumerate(inputs)]
    return JSONResponse({"data": data, "model": "voyage-3.5", "usage": {"total_tokens": len(inputs) * 10}})
