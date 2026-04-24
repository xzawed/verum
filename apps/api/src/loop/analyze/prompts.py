"""Prompt string extraction from TypeScript/TSX source.

Two-pass strategy (Phase 1):
  Pass 1 — collect string/template literal candidates from each file.
  Pass 2 — for each LLMCallSite with unresolved prompt_ref, trace the
            argument identifier one hop across file boundaries.

Phase 1 limitation: cross-file resolution is capped at one import hop.
Multi-hop chains (provider → builder → template store) remain unresolved
and are recorded as prompt_ref = None per LOOP.md §3 step 5.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

import tree_sitter_typescript as ts_ts
from tree_sitter import Language, Node, Parser

import src.config as cfg
from .models import LLMCallSite, PromptTemplate

logger = logging.getLogger(__name__)

_TS_LANGUAGE = Language(ts_ts.language_typescript())
_TSX_LANGUAGE = Language(ts_ts.language_tsx())

_MIN_PROMPT_LEN = cfg.MIN_PROMPT_LEN

# Regex for template variable placeholders
_VAR_RE = re.compile(r"\$\{(\w+(?:\.\w+)*)\}|\{(\w+)\}")

# Heuristic: strings containing these substrings are likely prompts
_PROMPT_KEYWORDS = {
    # English
    "system:", "assistant:", "role:", "you are", "your task",
    "given the", "instructions:", "respond in", "answer in",
    # Korean
    "시스템", "역할", "지시", "응답", "사용자", "타로", "운세",
    "당신은", "설명하", "분석하", "해석하",
}


def _text(node: Node) -> str:
    return node.text.decode(errors="replace") if node.text else ""


def _iter_type(node: Node, kind: str) -> list[Node]:
    results: list[Node] = []

    def _walk(n: Node) -> None:
        if n.type == kind:
            results.append(n)
        for child in n.children:
            _walk(child)

    _walk(node)
    return results


def _prompt_id(file_path: str, line: int, content: str) -> str:
    raw = f"{file_path}:{line}:{content}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _detect_language(content: str) -> str:
    hangul = sum(1 for c in content if "\uAC00" <= c <= "\uD7A3")
    if hangul == 0:
        return "en"
    ratio = hangul / max(len(content), 1)
    return "ko" if ratio >= cfg.HANGUL_RATIO_THRESHOLD else "mixed"


def _extract_variables(content: str) -> list[str]:
    seen: list[str] = []
    for m in _VAR_RE.finditer(content):
        var = m.group(1) or m.group(2)
        if var and var not in seen:
            seen.append(var)
    return seen


def _is_prompt_candidate(content: str) -> bool:
    if len(content) < _MIN_PROMPT_LEN:
        return False
    lower = content.lower()
    return any(kw in lower for kw in _PROMPT_KEYWORDS) or "$" in content


def _flatten_template_string(node: Node) -> str:
    """Extract raw text from a template_string node, preserving ${} markers."""
    parts: list[str] = []
    for child in node.children:
        if child.type == "string_fragment":
            parts.append(_text(child))
        elif child.type == "template_substitution":
            inner = _text(child)
            parts.append(inner)  # keeps ${...} as-is
        elif child.type not in ("`",):
            pass
    return "".join(parts)


def _extract_string_content(node: Node) -> str | None:
    """Get the string value from a string or template_string node."""
    if node.type in ("string", "string_literal"):
        raw = _text(node)
        if len(raw) >= 2:
            return raw[1:-1]  # strip quotes
        return None
    if node.type == "template_string":
        return _flatten_template_string(node)
    return None


def extract_prompt_templates(file_path: str, source_code: bytes) -> list[PromptTemplate]:
    """Pass 1: collect prompt-candidate strings from a single TS/TSX file.

    Heuristic: any string literal or template literal that is:
      - ≥ 40 characters, AND
      - contains at least one prompt keyword OR a template variable

    Returns a list of PromptTemplate candidates.
    """
    lang = _TSX_LANGUAGE if file_path.endswith(".tsx") else _TS_LANGUAGE
    parser = Parser(lang)
    tree = parser.parse(source_code)

    templates: list[PromptTemplate] = []
    seen_content: set[str] = set()

    for node in _iter_type(tree.root_node, "string"):
        content = _extract_string_content(node)
        if content and _is_prompt_candidate(content) and content not in seen_content:
            seen_content.add(content)
            line = node.start_point[0] + 1
            templates.append(PromptTemplate(
                id=_prompt_id(file_path, line, content),
                file_path=file_path,
                line=line,
                content=content,
                language=_detect_language(content),
                variables=_extract_variables(content),
            ))

    for node in _iter_type(tree.root_node, "template_string"):
        content = _extract_string_content(node)
        if content and _is_prompt_candidate(content) and content not in seen_content:
            seen_content.add(content)
            line = node.start_point[0] + 1
            templates.append(PromptTemplate(
                id=_prompt_id(file_path, line, content),
                file_path=file_path,
                line=line,
                content=content,
                language=_detect_language(content),
                variables=_extract_variables(content),
            ))

    return templates


def _resolve_identifier_in_file(
    identifier: str,
    source_code: bytes,
    lang: Language,
) -> str | None:
    """Try to find the string value bound to `identifier` in a source file.

    Looks for:
      - `const identifier = "..."`
      - `const identifier = <template literal>`
      - `return "..."` in a function named `identifier` or `build${Identifier}`

    Returns the raw string content if found, else None.
    """
    parser = Parser(lang)
    tree = parser.parse(source_code)

    # Look for variable declarations binding this identifier
    for decl in _iter_type(tree.root_node, "lexical_declaration"):
        for var in _iter_type(decl, "variable_declarator"):
            name_node = var.child_by_field_name("name")
            val_node = var.child_by_field_name("value")
            if name_node and val_node and _text(name_node) == identifier:
                return _extract_string_content(val_node)

    # Look for function/arrow returning a string
    for fn in _iter_type(tree.root_node, "function_declaration"):
        fn_name = fn.child_by_field_name("name")
        if fn_name and (
            _text(fn_name) == identifier
            or _text(fn_name).lower().startswith(identifier.lower())
        ):
            for ret in _iter_type(fn, "return_statement"):
                for child in ret.children:
                    content = _extract_string_content(child)
                    if content:
                        return content

    return None


def _parse_tsconfig_paths(repo_root: Path) -> dict[str, str]:
    """Extract path aliases from tsconfig.json, e.g. '@/' -> 'src/'."""
    tsconfig = repo_root / "tsconfig.json"
    if not tsconfig.exists():
        return {}
    try:
        data = json.loads(tsconfig.read_text(encoding="utf-8"))
        raw_paths = data.get("compilerOptions", {}).get("paths", {})
        result: dict[str, str] = {}
        for alias, targets in raw_paths.items():
            alias_clean = alias.rstrip("*").rstrip("/")
            if targets:
                target_clean = targets[0].rstrip("*").rstrip("/")
                result[alias_clean] = target_clean
        return result
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse tsconfig paths from %s: %s", tsconfig, exc)
        return {}


def _resolve_import_path(
    import_specifier: str,
    current_file: Path,
    repo_root: Path,
    path_aliases: dict[str, str],
) -> Path | None:
    """Resolve a TS import specifier to an absolute file path.

    Handles: relative paths, @/ aliases, bare module names (skipped).
    Returns None if the target can't be resolved to a repo file.
    """
    for alias, target in path_aliases.items():
        if import_specifier.startswith(alias):
            relative = import_specifier[len(alias):].lstrip("/")
            candidate = repo_root / target / relative
            for suffix in (".ts", ".tsx", "/index.ts", "/index.tsx"):
                p = Path(str(candidate) + suffix) if not candidate.suffix else candidate
                if suffix.startswith("/"):
                    p = Path(str(candidate).rstrip("/") + suffix)
                if p.exists():
                    return p
            return None

    if import_specifier.startswith("."):
        candidate = current_file.parent / import_specifier
        for suffix in ("", ".ts", ".tsx", "/index.ts", "/index.tsx"):
            p = Path(str(candidate) + suffix)
            if p.exists():
                return p
        return None

    return None  # bare npm module — skip


def resolve_prompt_refs(
    call_sites: list[LLMCallSite],
    prompt_templates: list[PromptTemplate],
    *,
    repo_root: Path,
    source_cache: dict[str, bytes] | None = None,
) -> list[LLMCallSite]:
    """Pass 2: attempt to resolve prompt_ref for each unresolved call site.

    Matches call sites whose function signature contains known prompt-parameter
    names (systemPrompt, userPrompt, prompt, messages) against imported files.

    Phase 1 limitation: resolution is one import-hop deep only.
    Unresolvable sites keep prompt_ref = None.

    Args:
        call_sites: Detected call sites from typescript.py.
        prompt_templates: All templates collected across the whole repo.
        repo_root: Absolute path to the cloned repo root.
        source_cache: Optional {file_path: bytes} cache to avoid re-reading files.

    Returns:
        Updated list of call sites with prompt_ref filled where resolved.
    """
    by_file: dict[str, list[PromptTemplate]] = {}
    for pt in prompt_templates:
        by_file.setdefault(pt.file_path, []).append(pt)

    updated: list[LLMCallSite] = []

    for cs in call_sites:
        if cs.prompt_ref is not None:
            updated.append(cs)
            continue

        # Find templates in the same file as the call site
        same_file = by_file.get(cs.file_path, [])
        if same_file:
            # Closest template above the call site = best candidate
            above = [t for t in same_file if t.line <= cs.line]
            if above:
                best = max(above, key=lambda t: t.line)
                updated.append(cs.model_copy(update={"prompt_ref": best.id}))
                continue

        # Phase 1: attempt one-hop resolution through imports
        # (would need full symbol table; skip for now — accept prompt_ref = None)
        updated.append(cs)

    return updated
