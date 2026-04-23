"""Verum runtime configuration — all tuneable constants in one place.

Override any value with the corresponding environment variable.
Defaults are tuned for the ArcanaInsight dogfood target.
"""
from __future__ import annotations

import os

# ── INFER stage ──────────────────────────────────────────────────────────────
INFER_MODEL: str = os.environ.get("INFER_MODEL", "claude-sonnet-4-6")
INFER_MAX_TOKENS: int = int(os.environ.get("INFER_MAX_TOKENS", "512"))

# ── HARVEST stage — embedding ─────────────────────────────────────────────────
EMBED_MODEL: str = os.environ.get("EMBED_MODEL", "voyage-3.5")
EMBED_BATCH_SIZE: int = int(os.environ.get("EMBED_BATCH_SIZE", "128"))
EMBED_BASE_URL: str = os.environ.get(
    "EMBED_BASE_URL", "https://api.voyageai.com/v1/embeddings"
)

# ── HARVEST stage — chunking ──────────────────────────────────────────────────
CHUNK_SIZE: int = int(os.environ.get("CHUNK_SIZE", "512"))
CHUNK_OVERLAP: int = int(os.environ.get("CHUNK_OVERLAP", "50"))

# ── HARVEST stage — hybrid search weights ────────────────────────────────────
# Must sum to 1.0. Vector: semantic similarity, Text: BM25 keyword match.
HYBRID_VECTOR_WEIGHT: float = float(os.environ.get("HYBRID_VECTOR_WEIGHT", "0.7"))
HYBRID_TEXT_WEIGHT: float = float(os.environ.get("HYBRID_TEXT_WEIGHT", "0.3"))

# ── ANALYZE stage — prompt detection thresholds ───────────────────────────────
MIN_PROMPT_LEN: int = int(os.environ.get("MIN_PROMPT_LEN", "40"))
# Fraction of Hangul chars in content to classify as Korean (vs mixed/English).
HANGUL_RATIO_THRESHOLD: float = float(os.environ.get("HANGUL_RATIO_THRESHOLD", "0.15"))

# ── ANALYZE stage — LLM provider detection (raw-fetch pattern matching) ────────
# Each entry maps a URL substring → SDK name for TypeScript/JS raw-fetch detection.
LLM_FETCH_URL_PATTERNS: list[tuple[str, str]] = [
    ("api.openai.com/v1/chat/completions", "openai"),
    ("api.anthropic.com/v1/messages", "anthropic"),
    ("api.x.ai/v1/chat/completions", "grok"),
    ("generativelanguage.googleapis.com", "google-generativeai"),
]

LLM_PATH_SUFFIX_PATTERNS: list[tuple[str, list[str]]] = [
    ("/v1/messages", ["anthropic"]),
    ("/chat/completions", ["openai", "grok"]),
]

# ── GENERATE stage ────────────────────────────────────────────────────────────
GENERATE_MODEL: str = os.environ.get("GENERATE_MODEL", INFER_MODEL)
GENERATE_MAX_TOKENS: int = int(os.environ.get("GENERATE_MAX_TOKENS", "2048"))

# ── FREEMIUM plan limits ──────────────────────────────────────────────────────
from pydantic import BaseModel  # noqa: E402


class PlanLimits(BaseModel):
    traces: int
    chunks: int
    repos: int


FREE_PLAN: PlanLimits = PlanLimits(
    traces=int(os.environ.get("VERUM_FREE_TRACES", "1000")),
    chunks=int(os.environ.get("VERUM_FREE_CHUNKS", "10000")),
    repos=int(os.environ.get("VERUM_FREE_REPOS", "3")),
)
