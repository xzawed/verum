from __future__ import annotations
import numpy as np
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ._common import check_fault, log_call

router = APIRouter()
DIM_EMBED = 1536


def _det_embedding(text: str) -> list[float]:
    seed = abs(hash(text)) % (2**31)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(DIM_EMBED)
    vec = vec / (np.linalg.norm(vec) + 1e-9)
    return vec.tolist()


@router.post("/v1/embeddings")
async def embeddings(request: Request):
    await check_fault(request, "openai_embed")
    body = await request.json()
    inputs = body.get("input", [])
    if isinstance(inputs, str):
        inputs = [inputs]
    log_call(request, "openai/v1/embeddings", {"n": len(inputs)})
    data = [{"embedding": _det_embedding(t), "index": i, "object": "embedding"} for i, t in enumerate(inputs)]
    return JSONResponse({"data": data, "model": "text-embedding-3-small", "usage": {"prompt_tokens": len(inputs) * 5, "total_tokens": len(inputs) * 5}})


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    await check_fault(request, "openai_chat")
    body = await request.json()
    log_call(request, "openai/v1/chat/completions", {"model": body.get("model")})
    return JSONResponse({
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "타로 카드가 당신의 질문에 대한 답을 보여줍니다."}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
    })
