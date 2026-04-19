"""TypeScript/JavaScript LLM call-site detector using tree-sitter.

Detection patterns:
  A — SDK import (openai, @anthropic-ai/sdk, etc.) + call tracing.
  B — Raw fetch() to known LLM provider hostnames (literal or via class property).
  C — Provider class that implements an AIProvider-like interface.

ArcanaInsight uses pattern B + C (no SDK imports).
Pattern A is future-proof for repos that use official SDKs.
"""
from __future__ import annotations

from pathlib import Path

import tree_sitter_typescript as ts_ts
from tree_sitter import Language, Node, Parser

from .models import LLMCallSite, ModelConfig, PromptTemplate

_TS_LANGUAGE = Language(ts_ts.language_typescript())
_TSX_LANGUAGE = Language(ts_ts.language_tsx())

# --- Known LLM provider: (path fragment, sdk label) ----------------------
# Matched against assembled URL text (template literals partially resolved).

_FETCH_URL_TO_SDK: list[tuple[str, str]] = [
    ("api.openai.com/v1/chat/completions", "openai"),
    ("api.openai.com/v1/responses", "openai"),
    ("api.anthropic.com/v1/messages", "anthropic"),
    ("api.x.ai/v1/chat/completions", "grok"),
    ("api.x.ai/v1/messages", "grok"),
    ("generativelanguage.googleapis.com", "google-generativeai"),
]

# Path-suffix patterns — used when base URL is a variable (e.g. this.baseUrl)
# Matched in order; first match wins.
_PATH_SUFFIX_TO_CANDIDATE: list[tuple[str, list[str]]] = [
    ("/v1/messages", ["anthropic"]),          # anthropic only uses /messages
    ("/chat/completions", ["openai", "grok"]),  # ambiguous — resolve via class name
    ("/v1/responses", ["openai"]),
]

# SDK import specifier → sdk label
_SDK_IMPORT_PATTERNS: list[tuple[str, str]] = [
    ("openai", "openai"),
    ("@anthropic-ai/sdk", "anthropic"),
    ("@google/generative-ai", "google-generativeai"),
    ("@mistralai/mistralai", "mistral"),
]

_AI_PROVIDER_INTERFACE_NAMES = {"AIProvider", "LLMProvider", "ChatProvider"}

_PROVIDER_METHOD_NAMES = {
    "generateReading", "streamReading",
    "chat", "complete", "generate",
    "createChatCompletion", "createMessage",
}


class FileAnalysis:
    def __init__(self) -> None:
        self.call_sites: list[LLMCallSite] = []
        self.model_configs: list[ModelConfig] = []
        self.prompt_candidates: list[PromptTemplate] = []


def _text(node: Node) -> str:
    return node.text.decode(errors="replace") if node.text else ""


def _iter_type(node: Node, kind: str) -> list[Node]:
    """Depth-first collect all descendants of a given type."""
    results: list[Node] = []

    def _walk(n: Node) -> None:
        if n.type == kind:
            results.append(n)
        for child in n.children:
            _walk(child)

    _walk(node)
    return results


def _classify_url(url_text: str) -> str | None:
    """Return sdk label for a full URL, or None if not a known LLM endpoint."""
    for pattern, sdk in _FETCH_URL_TO_SDK:
        if pattern in url_text:
            return sdk
    return None


def _classify_path_suffix(path: str, class_sdk: str | None) -> str | None:
    """Return sdk label from path suffix + optional class context."""
    for suffix, candidates in _PATH_SUFFIX_TO_CANDIDATE:
        if suffix in path:
            if len(candidates) == 1:
                return candidates[0]
            # Ambiguous: use class_sdk if available and it's in candidates
            if class_sdk and class_sdk in candidates:
                return class_sdk
            return candidates[0]  # best guess
    return None


def _extract_fetch_url_text(first_arg: Node) -> str:
    """Flatten a fetch() first argument to a string for URL classification."""
    if first_arg.type in ("string", "string_literal"):
        return _text(first_arg).strip('"\'`')
    if first_arg.type == "template_string":
        parts: list[str] = []
        for child in first_arg.children:
            if child.type == "string_fragment":
                parts.append(_text(child))
            elif child.type == "template_substitution":
                # Try to get the substitution as text (e.g. "this.baseUrl")
                parts.append(f"<{_text(child).strip('${}')}>" )
        return "".join(parts)
    return _text(first_arg)


def _extract_json_body_params(body_arg: Node) -> dict[str, object]:
    """Pull model/temperature/max_tokens from JSON.stringify({...}) argument."""
    result: dict[str, object] = {}
    for call in _iter_type(body_arg, "call_expression"):
        func = call.child_by_field_name("function")
        if func and "stringify" in _text(func):
            args = call.child_by_field_name("arguments")
            if not args:
                continue
            obj_nodes = [c for c in args.children if c.type == "object"]
            if not obj_nodes:
                continue
            for pair in obj_nodes[0].children:
                if pair.type != "pair":
                    continue
                k = pair.child_by_field_name("key")
                v = pair.child_by_field_name("value")
                if not k or not v:
                    continue
                key = _text(k).strip('"\'')
                val = _text(v)
                if key == "model":
                    result["model"] = val.strip('"\'`')
                elif key == "temperature":
                    try:
                        result["temperature"] = float(val)
                    except ValueError:
                        pass
                elif key == "max_tokens":
                    try:
                        result["max_tokens"] = int(val)
                    except ValueError:
                        pass
    return result


def _sdk_from_class_name(name: str) -> str:
    n = name.lower()
    if "grok" in n:
        return "grok"
    if "claude" in n or "anthropic" in n:
        return "anthropic"
    if "openai" in n or "gpt" in n:
        return "openai"
    if "google" in n or "gemini" in n:
        return "google-generativeai"
    return "raw-fetch"


def _resolve_class_base_url(class_body: Node) -> str | None:
    """Extract baseUrl / BASE_URL string literal from a class body (field or member assign)."""
    for field in _iter_type(class_body, "public_field_definition"):
        name_node = field.child_by_field_name("name")
        val_node = field.child_by_field_name("value")
        if name_node and val_node:
            name = _text(name_node)
            if "baseurl" in name.lower() or "base_url" in name.lower():
                val = _text(val_node).strip('"\'` ')
                if val.startswith("http"):
                    return val
    # Also check private fields (accessibility_modifier + field)
    for field in _iter_type(class_body, "field_definition"):
        name_node = field.child_by_field_name("name")
        val_node = field.child_by_field_name("value")
        if name_node and val_node:
            name = _text(name_node)
            if "baseurl" in name.lower() or "base_url" in name.lower():
                val = _text(val_node).strip('"\'` ')
                if val.startswith("http"):
                    return val
    return None


def _analyze_class(node: Node, rel_path: str, result: FileAnalysis) -> None:
    """Process a class_declaration node for patterns B (fetch) and C (provider)."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return
    class_name = _text(name_node)
    class_sdk = _sdk_from_class_name(class_name)

    # class_heritage is not a named field — search by node type
    heritage = next((c for c in node.children if c.type == "class_heritage"), None)
    is_provider = False
    if heritage:
        for impl_clause in _iter_type(heritage, "implements_clause"):
            for type_id in _iter_type(impl_clause, "type_identifier"):
                if _text(type_id) in _AI_PROVIDER_INTERFACE_NAMES:
                    is_provider = True

    body = node.child_by_field_name("body")
    if not body:
        return

    # Resolve class-level baseUrl for template URL enrichment
    base_url = _resolve_class_base_url(body)

    # Pattern C — emit a call site per matching method on provider classes
    if is_provider:
        for method in _iter_type(body, "method_definition"):
            mn = method.child_by_field_name("name")
            if mn and _text(mn) in _PROVIDER_METHOD_NAMES:
                line = method.start_point[0] + 1
                result.call_sites.append(LLMCallSite(
                    file_path=rel_path,
                    line=line,
                    sdk=class_sdk,
                    function=f"{class_name}.{_text(mn)}",
                    prompt_ref=None,
                ))

    # Pattern B — scan fetch() calls inside the class body
    for call in _iter_type(body, "call_expression"):
        func = call.child_by_field_name("function")
        if not func or _text(func) != "fetch":
            continue

        args = call.child_by_field_name("arguments")
        if not args:
            continue
        arg_list = [c for c in args.children if c.type not in ("(", ")", ",")]
        if not arg_list:
            continue

        url_text = _extract_fetch_url_text(arg_list[0])

        # Try full-URL match first
        sdk = _classify_url(url_text)

        # Try enriching template variable with resolved baseUrl
        if sdk is None and base_url:
            # Replace <this.baseUrl> or <this.baseURL> placeholders with the resolved value
            enriched = url_text
            for placeholder in (
                "<this.baseUrl>", "<this.baseURL>",
                "<this._baseUrl>", "<this._baseURL>",
            ):
                enriched = enriched.replace(placeholder, base_url)
            sdk = _classify_url(enriched)
            url_text = enriched

        # Try path-suffix match with class context
        if sdk is None:
            sdk = _classify_path_suffix(url_text, class_sdk)

        if sdk is None:
            continue  # not a known LLM endpoint

        line = call.start_point[0] + 1
        result.call_sites.append(LLMCallSite(
            file_path=rel_path,
            line=line,
            sdk=sdk,
            function=f"fetch->{url_text}",
            prompt_ref=None,
        ))

        if len(arg_list) >= 2:
            params = _extract_json_body_params(arg_list[1])
            if params:
                result.model_configs.append(ModelConfig(
                    file_path=rel_path,
                    line=line,
                    model=str(params["model"]) if "model" in params else None,
                    temperature=float(str(params["temperature"])) if "temperature" in params else None,
                    max_tokens=int(str(params["max_tokens"])) if "max_tokens" in params else None,
                ))


def _analyze_top_level(
    node: Node,
    rel_path: str,
    result: FileAnalysis,
    sdk_symbols: dict[str, str],
) -> None:
    """Pattern A — top-level fetch() calls and SDK symbol calls."""
    if node.type != "call_expression":
        return
    func = node.child_by_field_name("function")
    if not func:
        return

    func_text = _text(func)

    # Top-level fetch (not inside a class)
    if func_text == "fetch":
        args = node.child_by_field_name("arguments")
        if not args:
            return
        arg_list = [c for c in args.children if c.type not in ("(", ")", ",")]
        if not arg_list:
            return
        url_text = _extract_fetch_url_text(arg_list[0])
        sdk = _classify_url(url_text) or _classify_path_suffix(url_text, None)
        if sdk:
            line = node.start_point[0] + 1
            result.call_sites.append(LLMCallSite(
                file_path=rel_path,
                line=line,
                sdk=sdk,
                function=f"fetch->{url_text}",
                prompt_ref=None,
            ))
        return

    # SDK symbol call (e.g. openaiClient.chat.completions.create)
    root_sym = func_text.split(".")[0]
    if root_sym in sdk_symbols:
        line = node.start_point[0] + 1
        result.call_sites.append(LLMCallSite(
            file_path=rel_path,
            line=line,
            sdk=sdk_symbols[root_sym],
            function=func_text,
            prompt_ref=None,
        ))


def _analyze_file(file_path: str, source: bytes, language: Language) -> FileAnalysis:
    parser = Parser(language)
    tree = parser.parse(source)
    result = FileAnalysis()
    rel_path = file_path
    sdk_symbols: dict[str, str] = {}

    # First pass: collect SDK import symbols (Pattern A)
    for imp in _iter_type(tree.root_node, "import_statement"):
        from_node = imp.child_by_field_name("source")
        if not from_node:
            continue
        specifier = _text(from_node).strip('"\'')
        for sdk_spec, sdk_label in _SDK_IMPORT_PATTERNS:
            if specifier == sdk_spec:
                for clause in _iter_type(imp, "import_clause"):
                    for ident in _iter_type(clause, "identifier"):
                        sdk_symbols[_text(ident)] = sdk_label

    # Second pass: class declarations (Patterns B + C)
    for cls in _iter_type(tree.root_node, "class_declaration"):
        _analyze_class(cls, rel_path, result)

    # Third pass: top-level call expressions (Pattern A + B outside classes)
    # Skip any statement that is, or directly wraps, a class declaration.
    def _is_class_stmt(n: Node) -> bool:
        if n.type == "class_declaration":
            return True
        if n.type in ("export_statement", "export_default_declaration"):
            return any(c.type == "class_declaration" for c in n.children)
        return False

    for stmt in tree.root_node.children:
        if _is_class_stmt(stmt):
            continue
        for call in _iter_type(stmt, "call_expression"):
            _analyze_top_level(call, rel_path, result, sdk_symbols)

    return result


def analyze_file(file_path: str, source_code: bytes) -> FileAnalysis:
    """Analyze a single TypeScript or TSX file. Returns call sites + model configs."""
    lang = _TSX_LANGUAGE if file_path.endswith(".tsx") else _TS_LANGUAGE
    return _analyze_file(file_path, source_code, lang)


def analyze_directory(root: Path, *, repo_root: Path | None = None) -> FileAnalysis:
    """Walk a directory tree and analyze all .ts / .tsx / .js files.

    Skips node_modules and .next build output.
    """
    aggregate = FileAnalysis()
    base = repo_root or root

    for ext in ("*.ts", "*.tsx", "*.js"):
        for path in root.rglob(ext):
            if "node_modules" in path.parts or ".next" in path.parts:
                continue
            rel = str(path.relative_to(base))
            try:
                source = path.read_bytes()
            except OSError:
                continue
            file_result = analyze_file(rel, source)
            aggregate.call_sites.extend(file_result.call_sites)
            aggregate.model_configs.extend(file_result.model_configs)
            aggregate.prompt_candidates.extend(file_result.prompt_candidates)

    return aggregate
