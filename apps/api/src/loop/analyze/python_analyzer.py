"""Python AST-based LLM call-site detector (F-1.3).

Detection passes:
  1 — Import scan: build sdk_names dict (identifier → sdk label).
  2 — Assignment tracking: extend sdk_names with instance variables.
  3 — Call detection: match method chains against known LLM call patterns.

Supported SDKs:
  openai, anthropic, google-generativeai (google.generativeai / google.genai),
  grok (xai_grok), groq.

Common patterns handled:
  A — Direct module call:
        import openai; openai.chat.completions.create(...)
  B — From-import class instantiation:
        from openai import OpenAI; client = OpenAI(); client.chat.completions.create(...)
  C — Aliased module:
        import anthropic as ant; client = ant.Anthropic(); client.messages.create(...)
  D — Inline instantiation:
        anthropic.Anthropic().messages.create(...)
  E — Google GenerativeModel:
        import google.generativeai as genai; m = genai.GenerativeModel("x"); m.generate_content(...)
"""
from __future__ import annotations

import ast
import hashlib
import logging
from pathlib import Path

from .models import LLMCallSite, ModelConfig, PromptTemplate

logger = logging.getLogger(__name__)

# Top-level module name → sdk label
_MODULE_TO_SDK: dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google.generativeai": "google-generativeai",
    "google.genai": "google-generativeai",
    "xai_grok": "grok",
    "groq": "groq",
}

# Well-known entry-point class names → sdk label (used when from-module is unknown)
_CLASS_TO_SDK: dict[str, str] = {
    "OpenAI": "openai",
    "AsyncOpenAI": "openai",
    "AzureOpenAI": "openai",
    "AsyncAzureOpenAI": "openai",
    "Anthropic": "anthropic",
    "AsyncAnthropic": "anthropic",
    "AnthropicBedrock": "anthropic",
    "GenerativeModel": "google-generativeai",
}

# Method chain suffixes that identify LLM invocations, keyed by sdk label
_LLM_METHODS: dict[str, frozenset[str]] = {
    "openai": frozenset({
        "chat.completions.create",
        "chat.completions.stream",
        "completions.create",
        "beta.messages.stream",
    }),
    "anthropic": frozenset({
        "messages.create",
        "messages.stream",
        "beta.messages.create",
    }),
    "google-generativeai": frozenset({
        "generate_content",
        "generate_content_async",
        "generate_content_stream",
    }),
    "grok": frozenset({
        "chat.completions.create",
    }),
    "groq": frozenset({
        "chat.completions.create",
    }),
}

_MIN_PROMPT_LEN = 10


class FileAnalysis:
    def __init__(self) -> None:
        self.call_sites: list[LLMCallSite] = []
        self.model_configs: list[ModelConfig] = []
        self.prompt_templates: list[PromptTemplate] = []


# ── AST helpers ───────────────────────────────────────────────────────────────

def _attr_chain(node: ast.expr) -> str:
    """Flatten a pure Name/Attribute chain to a dotted string.

    Stops at any non-Name/Attribute node (e.g. a Call node) and uses
    whatever was collected so far.  Returns "" for unresolvable nodes.
    """
    parts: list[str] = []
    cur: ast.expr = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _sdk_for_module(mod: str) -> str | None:
    """Return the sdk label for a module name (exact or prefix match)."""
    label = _MODULE_TO_SDK.get(mod)
    if label:
        return label
    for pattern, lbl in _MODULE_TO_SDK.items():
        if mod.startswith(pattern + "."):
            return lbl
    return None


def _decompose_func(
    func: ast.expr,
    sdk_names: dict[str, str],
) -> tuple[str | None, str]:
    """Decompose a call's func node into (sdk_label, method_suffix).

    Handles:
    - Name / dotted Attribute: chain starts at a known sdk_names key.
    - Attribute whose value is itself a Call (inline instantiation):
        e.g. anthropic.Anthropic().messages.create
          → sdk="anthropic", method_suffix="messages.create"
    """
    suffix_parts: list[str] = []
    cur: ast.expr = func

    # Collect trailing attribute names
    while isinstance(cur, ast.Attribute):
        suffix_parts.append(cur.attr)
        cur = cur.value

    suffix = ".".join(reversed(suffix_parts))

    if isinstance(cur, ast.Name):
        sdk = sdk_names.get(cur.id)
        return sdk, suffix

    if isinstance(cur, ast.Call):
        # Inline call: resolve its own func recursively (one level is enough)
        inner_sdk, _ = _decompose_func(cur.func, sdk_names)
        return inner_sdk, suffix

    return None, suffix


def _str_value(node: ast.expr) -> str | None:
    """Return the string value of a constant or simple f-string node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            else:
                parts.append("{...}")
        joined = "".join(parts)
        return joined if joined else None
    return None


def _messages_prompts(messages_node: ast.expr) -> list[str]:
    """Extract content strings from messages=[{"role":..., "content":...}, ...]."""
    prompts: list[str] = []
    if not isinstance(messages_node, ast.List):
        return prompts
    for elt in messages_node.elts:
        if not isinstance(elt, ast.Dict):
            continue
        for k, v in zip(elt.keys, elt.values, strict=True):
            if v is not None and isinstance(k, ast.Constant) and k.value == "content":
                s = _str_value(v)
                if s:
                    prompts.append(s)
    return prompts


def _extract_call_params(
    call: ast.Call,
) -> tuple[str | None, float | None, int | None, list[str]]:
    """Return (model, temperature, max_tokens, prompt_strings) from a call."""
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    prompts: list[str] = []

    for kw in call.keywords:
        if kw.arg == "model":
            model = _str_value(kw.value)
        elif kw.arg == "temperature":
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, (int, float)):
                temperature = float(kw.value.value)
        elif kw.arg == "max_tokens":
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
                max_tokens = kw.value.value
        elif kw.arg == "messages":
            prompts.extend(_messages_prompts(kw.value))

    # First positional arg on single-prompt calls (google-generativeai style)
    if call.args:
        s = _str_value(call.args[0])
        if s:
            prompts.append(s)

    return model, temperature, max_tokens, prompts


def _prompt_id(file_path: str, line: int, content: str) -> str:
    raw = f"{file_path}:{line}:{content}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Core analysis ─────────────────────────────────────────────────────────────

def _analyze_source(rel_path: str, source: bytes) -> FileAnalysis:
    result = FileAnalysis()

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError:
        logger.debug("Skipping %s: syntax error", rel_path)
        return result

    # Pass 1 — collect SDK-related names from imports
    sdk_names: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                lbl = _sdk_for_module(alias.name)
                if lbl:
                    name = alias.asname if alias.asname else alias.name.split(".")[0]
                    sdk_names[name] = lbl

        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            mod_lbl = _sdk_for_module(mod)
            for alias in node.names:
                out_name = alias.asname if alias.asname else alias.name
                if mod_lbl:
                    # Module is a known SDK — every imported name gets that label
                    sdk_names[out_name] = mod_lbl
                elif alias.name in _CLASS_TO_SDK:
                    # Unknown module but known class name (fallback)
                    sdk_names[out_name] = _CLASS_TO_SDK[alias.name]

    # Pass 2 — track assignments: client = SDK() or client = mod.SDK(...)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        var_name = node.targets[0].id
        val = node.value
        if not isinstance(val, ast.Call):
            continue

        # Resolve the constructor chain
        chain = _attr_chain(val.func)
        root = chain.split(".")[0] if chain else ""
        if root in sdk_names:
            sdk_names[var_name] = sdk_names[root]
        elif chain in _CLASS_TO_SDK:
            sdk_names[var_name] = _CLASS_TO_SDK[chain]

    # Pass 3 — detect LLM call sites
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        sdk, method_suffix = _decompose_func(node.func, sdk_names)
        if sdk is None:
            continue

        sdk_methods = _LLM_METHODS.get(sdk, frozenset())
        if method_suffix not in sdk_methods:
            continue

        line: int = node.lineno
        full_chain = _attr_chain(node.func)
        function_label = full_chain if full_chain else method_suffix

        model, temperature, max_tokens, prompts = _extract_call_params(node)

        result.call_sites.append(LLMCallSite(
            file_path=rel_path,
            line=line,
            sdk=sdk,
            function=function_label,
            prompt_ref=None,
        ))

        if model or temperature is not None or max_tokens is not None:
            result.model_configs.append(ModelConfig(
                file_path=rel_path,
                line=line,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            ))

        for content in prompts:
            if len(content) >= _MIN_PROMPT_LEN:
                result.prompt_templates.append(PromptTemplate(
                    id=_prompt_id(rel_path, line, content),
                    file_path=rel_path,
                    line=line,
                    content=content,
                    language="en",
                    variables=[],
                ))

    return result


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_file(file_path: str, source_code: bytes) -> FileAnalysis:
    """Analyze a single Python file for LLM call sites."""
    return _analyze_source(file_path, source_code)


def analyze_directory(root: Path, *, repo_root: Path | None = None) -> FileAnalysis:
    """Walk a directory tree and analyze all .py files.

    Skips __pycache__, .venv, venv, and site-packages directories.
    """
    aggregate = FileAnalysis()
    base = repo_root or root

    _SKIP_DIRS = {"__pycache__", ".venv", "venv", "site-packages", ".git"}

    for path in root.rglob("*.py"):
        if any(p in _SKIP_DIRS for p in path.parts):
            continue
        rel = str(path.relative_to(base))
        try:
            source = path.read_bytes()
        except OSError:
            continue
        file_result = analyze_file(rel, source)
        aggregate.call_sites.extend(file_result.call_sites)
        aggregate.model_configs.extend(file_result.model_configs)
        aggregate.prompt_templates.extend(file_result.prompt_templates)

    return aggregate
