"""ANALYZE stage pipeline: clone → detect → extract → persist."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from .cloner import cloned_repo
from .models import AnalysisResult, PromptTemplate
from .prompts import extract_prompt_templates, resolve_prompt_refs
from .python_analyzer import analyze_directory as analyze_python_directory
from .typescript import analyze_directory

_TS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
_PY_EXTENSIONS = {".py"}


def _count_languages(repo_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in repo_path.rglob("*"):
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext in _TS_EXTENSIONS:
            counts["typescript"] = counts.get("typescript", 0) + 1
        elif ext in _PY_EXTENSIONS:
            counts["python"] = counts.get("python", 0) + 1
    return counts


async def run_analysis(
    repo_url: str,
    *,
    branch: str = "main",
    repo_id: UUID | None = None,
) -> AnalysisResult:
    """Full ANALYZE pipeline for a single repository.

    Clones the repo, detects LLM call sites and prompt templates,
    resolves cross-file prompt references, and returns an AnalysisResult.

    Supports TypeScript/JavaScript (tree-sitter) and Python (ast) call-site detection.

    Raises:
        RepoCloneError: if the clone fails.
    """
    analysis_id = uuid4()
    rid = repo_id or uuid4()

    async with cloned_repo(repo_url, analysis_id, branch=branch) as repo_path:
        # Run CPU-bound parsing in a thread pool to avoid blocking the event loop
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _analyze_sync(repo_path, rid),
        )

    return result


def _analyze_sync(repo_path: Path, repo_id: UUID) -> AnalysisResult:
    """Synchronous analysis — runs in thread pool executor."""
    # Detect languages
    language_breakdown = _count_languages(repo_path)

    # TypeScript / JS detection (patterns A, B, C)
    ts_result = analyze_directory(repo_path, repo_root=repo_path)

    # Python detection (F-1.3)
    py_result = analyze_python_directory(repo_path, repo_root=repo_path)

    # Prompt extraction — collect from all TS files
    prompt_templates: list[PromptTemplate] = []
    source_cache: dict[str, bytes] = {}
    for ext in ("*.ts", "*.tsx", "*.js"):
        for path in repo_path.rglob(ext):
            if "node_modules" in path.parts or ".next" in path.parts:
                continue
            try:
                source = path.read_bytes()
            except OSError:
                continue
            rel = str(path.relative_to(repo_path))
            source_cache[rel] = source
            pts = extract_prompt_templates(rel, source)
            prompt_templates.extend(pts)

    # Merge Python prompt templates (already extracted in py_result)
    prompt_templates.extend(py_result.prompt_templates)

    # Cross-file prompt_ref resolution (one hop) — TS call sites only
    resolved_ts_sites = resolve_prompt_refs(
        ts_result.call_sites,
        prompt_templates,
        repo_root=repo_path,
        source_cache=source_cache,
    )

    # Combine call sites and model configs from both languages
    all_call_sites = resolved_ts_sites + py_result.call_sites
    all_model_configs = ts_result.model_configs + py_result.model_configs

    return AnalysisResult(
        repo_id=repo_id,
        call_sites=all_call_sites,
        prompt_templates=prompt_templates,
        model_configs=all_model_configs,
        language_breakdown=language_breakdown,
        analyzed_at=datetime.now(tz=timezone.utc),
    )
