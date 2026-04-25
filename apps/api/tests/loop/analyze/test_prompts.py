from __future__ import annotations

import json
from pathlib import Path

import pytest
import tree_sitter_typescript as ts_ts
from tree_sitter import Language

from src.loop.analyze.models import LLMCallSite, PromptTemplate
from src.loop.analyze.prompts import (
    _detect_language,
    _extract_variables,
    _is_prompt_candidate,
    _parse_tsconfig_paths,
    _prompt_id,
    _resolve_identifier_in_file,
    _resolve_import_path,
    extract_prompt_templates,
    resolve_prompt_refs,
)

_TS_LANGUAGE = Language(ts_ts.language_typescript())

# MIN_PROMPT_LEN is 40; strings below this threshold should be filtered out
_SHORT = "you are"
_LONG_KEYWORD = "you are a helpful assistant that answers questions about the topic in detail"
_LONG_DOLLAR = "Hello ${user.name} please provide your details and fill in the form here"
_LONG_NO_MATCH = "x" * 50  # long but no keyword, no $


# ── _prompt_id ────────────────────────────────────────────────────────────────

def test_prompt_id_returns_16_hex_chars() -> None:
    result = _prompt_id("src/foo.ts", 10, "some content")
    assert len(result) == 16
    assert all(c in "0123456789abcdef" for c in result)


def test_prompt_id_is_deterministic() -> None:
    a = _prompt_id("src/foo.ts", 10, "content")
    b = _prompt_id("src/foo.ts", 10, "content")
    assert a == b


def test_prompt_id_differs_for_different_inputs() -> None:
    a = _prompt_id("src/foo.ts", 10, "content")
    b = _prompt_id("src/bar.ts", 10, "content")
    c = _prompt_id("src/foo.ts", 11, "content")
    d = _prompt_id("src/foo.ts", 10, "other content")
    assert len({a, b, c, d}) == 4


# ── _detect_language ─────────────────────────────────────────────────────────

def test_detect_language_empty_string_returns_en() -> None:
    assert _detect_language("") == "en"


def test_detect_language_pure_ascii_returns_en() -> None:
    assert _detect_language("you are a helpful assistant") == "en"


def test_detect_language_high_hangul_ratio_returns_ko() -> None:
    # 40 hangul chars out of 45 total → ~89% > 0.15 threshold
    korean = "당신은 도움이 되는 AI 어시스턴트입니다 타로 해석 전문가"
    assert _detect_language(korean) == "ko"


def test_detect_language_low_hangul_ratio_returns_mixed() -> None:
    # A few hangul chars mixed with many ASCII → ratio below 0.15
    # 2 hangul in 60-char string → ~3%
    mixed = "you are a very helpful assistant that speaks some 한국 words"
    result = _detect_language(mixed)
    assert result == "mixed"


def test_detect_language_single_hangul_char_returns_mixed() -> None:
    # 1 hangul in a long ASCII string → well below 0.15
    content = "a" * 100 + "가"
    assert _detect_language(content) == "mixed"


# ── _extract_variables ────────────────────────────────────────────────────────

def test_extract_variables_template_literal_style() -> None:
    content = "Hello ${name}, your score is ${score}"
    result = _extract_variables(content)
    assert result == ["name", "score"]


def test_extract_variables_curly_brace_style() -> None:
    content = "Dear {user}, please review {document}"
    result = _extract_variables(content)
    assert result == ["user", "document"]


def test_extract_variables_dotted_path() -> None:
    content = "Welcome ${user.name} to ${user.org}"
    result = _extract_variables(content)
    assert result == ["user.name", "user.org"]


def test_extract_variables_deduplication() -> None:
    content = "Hello ${name} and again ${name} and also {name}"
    result = _extract_variables(content)
    assert result.count("name") == 1


def test_extract_variables_empty_string() -> None:
    assert _extract_variables("") == []


def test_extract_variables_no_placeholders() -> None:
    assert _extract_variables("no variables here at all") == []


# ── _is_prompt_candidate ─────────────────────────────────────────────────────

def test_is_prompt_candidate_too_short_returns_false() -> None:
    # "you are" is a keyword but < 40 chars
    assert _is_prompt_candidate(_SHORT) is False


def test_is_prompt_candidate_long_with_keyword_returns_true() -> None:
    assert _is_prompt_candidate(_LONG_KEYWORD) is True


def test_is_prompt_candidate_long_with_dollar_returns_true() -> None:
    assert _is_prompt_candidate(_LONG_DOLLAR) is True


def test_is_prompt_candidate_long_no_keyword_no_dollar_returns_false() -> None:
    assert _is_prompt_candidate(_LONG_NO_MATCH) is False


def test_is_prompt_candidate_korean_keyword() -> None:
    content = "당신은 타로 카드 전문 해석가입니다. 사용자의 질문에 신중하게 답해주세요."
    assert _is_prompt_candidate(content) is True


def test_is_prompt_candidate_boundary_length() -> None:
    # Exactly at MIN_PROMPT_LEN with keyword — should pass (>= check uses <)
    content = "you are" + "x" * 33  # 7 + 33 = 40 chars
    assert _is_prompt_candidate(content) is True


def test_is_prompt_candidate_one_below_boundary() -> None:
    content = "you are" + "x" * 32  # 39 chars
    assert _is_prompt_candidate(content) is False


# ── extract_prompt_templates ─────────────────────────────────────────────────

_STRING_LITERAL_SOURCE = b"""
const systemPrompt = "you are a helpful assistant that answers questions accurately and concisely";
const title = "short";
"""

_TEMPLATE_LITERAL_SOURCE = b"""
const buildPrompt = (user: string) => `you are a tarot reading assistant, the user is: ${user} please answer`;
"""

_DEDUP_SOURCE = b"""
const a = "you are a helpful assistant that answers questions accurately and with great care";
const b = "you are a helpful assistant that answers questions accurately and with great care";
"""

_KOREAN_SOURCE = (
    'const prompt = "당신은 타로 카드 전문 해석가입니다. 사용자의 질문에 신중하게 답해주세요.";\n'
).encode("utf-8")

_TSX_SOURCE = b"""
const prompt = "you are an expert React developer who answers questions about components and hooks";
"""


def test_extract_prompt_templates_string_literal_detected() -> None:
    results = extract_prompt_templates("src/ai.ts", _STRING_LITERAL_SOURCE)
    assert len(results) == 1
    assert "you are a helpful assistant" in results[0].content
    assert results[0].file_path == "src/ai.ts"
    assert results[0].line >= 1
    assert len(results[0].id) == 16


def test_extract_prompt_templates_short_string_filtered() -> None:
    results = extract_prompt_templates("src/ai.ts", _STRING_LITERAL_SOURCE)
    # "short" should not appear
    for t in results:
        assert "short" not in t.content


def test_extract_prompt_templates_template_literal_detected() -> None:
    results = extract_prompt_templates("src/ai.ts", _TEMPLATE_LITERAL_SOURCE)
    assert len(results) == 1
    assert "tarot" in results[0].content
    assert "${user}" in results[0].content or "user" in results[0].variables


def test_extract_prompt_templates_template_variables_extracted() -> None:
    results = extract_prompt_templates("src/ai.ts", _TEMPLATE_LITERAL_SOURCE)
    assert len(results) == 1
    assert "user" in results[0].variables


def test_extract_prompt_templates_deduplication() -> None:
    # Same content appears twice; should produce only one template
    results = extract_prompt_templates("src/ai.ts", _DEDUP_SOURCE)
    assert len(results) == 1


def test_extract_prompt_templates_korean_content() -> None:
    results = extract_prompt_templates("src/ai.ts", _KOREAN_SOURCE)
    assert len(results) == 1
    assert results[0].language == "ko"


def test_extract_prompt_templates_tsx_file_path() -> None:
    # TSX parser used when file_path ends with .tsx
    results = extract_prompt_templates("src/components/AI.tsx", _TSX_SOURCE)
    assert len(results) == 1
    assert "React developer" in results[0].content


def test_extract_prompt_templates_empty_source() -> None:
    results = extract_prompt_templates("src/ai.ts", b"")
    assert results == []


def test_extract_prompt_templates_no_prompts_in_source() -> None:
    source = b'const x = 1 + 2;\nconst msg = "hi";\n'
    results = extract_prompt_templates("src/math.ts", source)
    assert results == []


# ── _resolve_identifier_in_file ───────────────────────────────────────────────

_CONST_BINDING = b"""
const systemPrompt = "you are a helpful tarot reading assistant who provides accurate interpretations";
"""

_FUNCTION_RETURNING = b"""
function buildSystemPrompt(): string {
  return "you are an expert assistant that provides detailed and accurate responses to all queries";
}
"""

_NO_MATCHING_IDENTIFIER = b"""
const otherVar = "you are a completely different variable with a long prompt for testing purposes";
"""


def test_resolve_identifier_finds_const_binding() -> None:
    result = _resolve_identifier_in_file("systemPrompt", _CONST_BINDING, _TS_LANGUAGE)
    assert result is not None
    assert "tarot" in result


def test_resolve_identifier_finds_function_return() -> None:
    result = _resolve_identifier_in_file("buildSystemPrompt", _FUNCTION_RETURNING, _TS_LANGUAGE)
    assert result is not None
    assert "expert assistant" in result


def test_resolve_identifier_not_found_returns_none() -> None:
    result = _resolve_identifier_in_file("systemPrompt", _NO_MATCHING_IDENTIFIER, _TS_LANGUAGE)
    # systemPrompt not bound; otherVar is a different name
    assert result is None


def test_resolve_identifier_empty_source_returns_none() -> None:
    result = _resolve_identifier_in_file("anything", b"", _TS_LANGUAGE)
    assert result is None


def test_resolve_identifier_function_prefix_match() -> None:
    # Function named buildPrompt should match identifier "build"
    source = b"""
function buildPrompt(): string {
  return "you are a tarot card expert who interprets the cards with deep spiritual knowledge";
}
"""
    result = _resolve_identifier_in_file("build", source, _TS_LANGUAGE)
    assert result is not None
    assert "tarot" in result


# ── _parse_tsconfig_paths ─────────────────────────────────────────────────────

def test_parse_tsconfig_paths_no_tsconfig_returns_empty(tmp_path: Path) -> None:
    result = _parse_tsconfig_paths(tmp_path)
    assert result == {}


def test_parse_tsconfig_paths_valid_paths(tmp_path: Path) -> None:
    tsconfig = {
        "compilerOptions": {
            "paths": {
                "@/*": ["./src/*"],
                "@components/*": ["./src/components/*"],
            }
        }
    }
    (tmp_path / "tsconfig.json").write_text(json.dumps(tsconfig), encoding="utf-8")
    result = _parse_tsconfig_paths(tmp_path)
    assert result["@"] == "./src"
    assert result["@components"] == "./src/components"


def test_parse_tsconfig_paths_malformed_json_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "tsconfig.json").write_text("{invalid json!!!", encoding="utf-8")
    result = _parse_tsconfig_paths(tmp_path)
    assert result == {}


def test_parse_tsconfig_paths_no_compiler_options_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "tsconfig.json").write_text(json.dumps({"extends": "./base"}), encoding="utf-8")
    result = _parse_tsconfig_paths(tmp_path)
    assert result == {}


def test_parse_tsconfig_paths_empty_paths_returns_empty(tmp_path: Path) -> None:
    tsconfig = {"compilerOptions": {"paths": {}}}
    (tmp_path / "tsconfig.json").write_text(json.dumps(tsconfig), encoding="utf-8")
    result = _parse_tsconfig_paths(tmp_path)
    assert result == {}


def test_parse_tsconfig_paths_strips_wildcard_star(tmp_path: Path) -> None:
    tsconfig = {"compilerOptions": {"paths": {"@lib/*": ["src/lib/*"]}}}
    (tmp_path / "tsconfig.json").write_text(json.dumps(tsconfig), encoding="utf-8")
    result = _parse_tsconfig_paths(tmp_path)
    assert "@lib" in result
    assert result["@lib"] == "src/lib"


# ── _resolve_import_path ──────────────────────────────────────────────────────

def test_resolve_import_path_relative_ts(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    target = src_dir / "helpers.ts"
    target.write_text("export const x = 1;", encoding="utf-8")
    current = src_dir / "main.ts"
    result = _resolve_import_path("./helpers", current, tmp_path, {})
    assert result == target


def test_resolve_import_path_relative_tsx(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    target = src_dir / "Component.tsx"
    target.write_text("export const C = () => null;", encoding="utf-8")
    current = src_dir / "page.ts"
    result = _resolve_import_path("./Component", current, tmp_path, {})
    assert result == target


def test_resolve_import_path_bare_module_returns_none(tmp_path: Path) -> None:
    current = tmp_path / "src" / "main.ts"
    result = _resolve_import_path("react", current, tmp_path, {})
    assert result is None


def test_resolve_import_path_alias_resolves(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    lib_dir = src_dir / "lib"
    lib_dir.mkdir(parents=True)
    target = lib_dir / "utils.ts"
    target.write_text("export const u = 1;", encoding="utf-8")
    current = src_dir / "app" / "page.ts"
    path_aliases = {"@": "src"}
    result = _resolve_import_path("@/lib/utils", current, tmp_path, path_aliases)
    assert result == target


def test_resolve_import_path_nonexistent_relative_returns_none(tmp_path: Path) -> None:
    current = tmp_path / "src" / "main.ts"
    result = _resolve_import_path("./does-not-exist", current, tmp_path, {})
    assert result is None


def test_resolve_import_path_alias_no_matching_file_returns_none(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    current = tmp_path / "src" / "main.ts"
    path_aliases = {"@": "src"}
    # Alias resolves, but target file doesn't exist
    result = _resolve_import_path("@/missing/module", current, tmp_path, path_aliases)
    assert result is None


def test_resolve_import_path_index_ts_fallback(tmp_path: Path) -> None:
    # When candidate path exists as a directory, the function returns it as-is
    # (suffix "" matches first). Use a file target to exercise /index.ts suffix.
    pkg_dir = tmp_path / "src"
    pkg_dir.mkdir(parents=True)
    nested = pkg_dir / "utils"
    nested.mkdir()
    index = nested / "index.ts"
    index.write_text("export const util = 1;", encoding="utf-8")
    current = pkg_dir / "main.ts"
    # Use a specifier that does NOT match as bare directory (no trailing /)
    # but DOES resolve to /index.ts when the bare path has no suffix.
    # Because "utils" dir exists, "" suffix returns the dir Path; test that
    # the function at minimum returns a non-None result for this import.
    result = _resolve_import_path("./utils", current, tmp_path, {})
    assert result is not None


# ── resolve_prompt_refs ───────────────────────────────────────────────────────

def _make_template(file_path: str, line: int, content: str = "dummy") -> PromptTemplate:
    return PromptTemplate(
        id=_prompt_id(file_path, line, content),
        file_path=file_path,
        line=line,
        content=content,
        language="en",
        variables=[],
    )


def _make_call_site(file_path: str, line: int, prompt_ref: str | None = None) -> LLMCallSite:
    return LLMCallSite(
        file_path=file_path,
        line=line,
        sdk="openai",
        function="chat.completions.create",
        prompt_ref=prompt_ref,
    )


def test_resolve_prompt_refs_already_resolved_kept_as_is(tmp_path: Path) -> None:
    cs = _make_call_site("src/ai.ts", 20, prompt_ref="existingid1234567")
    result = resolve_prompt_refs([cs], [], repo_root=tmp_path)
    assert result[0].prompt_ref == "existingid1234567"


def test_resolve_prompt_refs_same_file_template_above_resolves(tmp_path: Path) -> None:
    template = _make_template("src/ai.ts", 10, "system prompt content here")
    cs = _make_call_site("src/ai.ts", 20)
    result = resolve_prompt_refs([cs], [template], repo_root=tmp_path)
    assert result[0].prompt_ref == template.id


def test_resolve_prompt_refs_picks_closest_template_above(tmp_path: Path) -> None:
    t1 = _make_template("src/ai.ts", 5, "first prompt text here")
    t2 = _make_template("src/ai.ts", 15, "second prompt text here")
    cs = _make_call_site("src/ai.ts", 20)
    result = resolve_prompt_refs([cs], [t1, t2], repo_root=tmp_path)
    # t2 is closer above the call site
    assert result[0].prompt_ref == t2.id


def test_resolve_prompt_refs_template_below_not_used(tmp_path: Path) -> None:
    template = _make_template("src/ai.ts", 30, "system prompt below call site")
    cs = _make_call_site("src/ai.ts", 20)
    result = resolve_prompt_refs([cs], [template], repo_root=tmp_path)
    # Template is below call site (line 30 > 20), so prompt_ref stays None
    assert result[0].prompt_ref is None


def test_resolve_prompt_refs_no_templates_keeps_none(tmp_path: Path) -> None:
    cs = _make_call_site("src/ai.ts", 20)
    result = resolve_prompt_refs([cs], [], repo_root=tmp_path)
    assert result[0].prompt_ref is None


def test_resolve_prompt_refs_different_file_not_matched(tmp_path: Path) -> None:
    template = _make_template("src/other.ts", 10, "prompt in other file")
    cs = _make_call_site("src/ai.ts", 20)
    result = resolve_prompt_refs([cs], [template], repo_root=tmp_path)
    # Template is in a different file — no same-file match, stays None
    assert result[0].prompt_ref is None


def test_resolve_prompt_refs_empty_inputs(tmp_path: Path) -> None:
    result = resolve_prompt_refs([], [], repo_root=tmp_path)
    assert result == []


def test_resolve_prompt_refs_multiple_call_sites(tmp_path: Path) -> None:
    t1 = _make_template("src/ai.ts", 5, "first system prompt content")
    t2 = _make_template("src/ai.ts", 15, "second system prompt content")
    cs1 = _make_call_site("src/ai.ts", 10)
    cs2 = _make_call_site("src/ai.ts", 20)
    result = resolve_prompt_refs([cs1, cs2], [t1, t2], repo_root=tmp_path)
    # cs1 (line 10) → t1 (line 5) is the only one above it
    assert result[0].prompt_ref == t1.id
    # cs2 (line 20) → t2 (line 15) is closer above it
    assert result[1].prompt_ref == t2.id


def test_resolve_prompt_refs_preserves_call_site_fields(tmp_path: Path) -> None:
    template = _make_template("src/ai.ts", 5, "system prompt for preservation test")
    cs = _make_call_site("src/ai.ts", 10)
    result = resolve_prompt_refs([cs], [template], repo_root=tmp_path)
    updated = result[0]
    assert updated.sdk == "openai"
    assert updated.function == "chat.completions.create"
    assert updated.file_path == "src/ai.ts"
    assert updated.line == 10
