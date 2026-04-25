from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from src.loop.analyze.models import AnalysisResult
from src.loop.analyze.pipeline import _analyze_sync, _count_languages, run_analysis

_GROK_PROVIDER = b"""
import { AIProvider } from "@/types/service";
export class GrokProvider implements AIProvider {
  private baseUrl = "https://api.x.ai/v1";
  async generateReading(sp: string, up: string): Promise<string> {
    const r = await fetch(`${this.baseUrl}/chat/completions`, {
      body: JSON.stringify({ model: "grok-3", temperature: 0.7, max_tokens: 4000 }),
    });
    return "";
  }
}
"""


class TestCountLanguages:
    def test_empty_directory(self, tmp_path: Path) -> None:
        result = _count_languages(tmp_path)
        assert result == {}

    def test_typescript_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.ts").write_text("const x = 1;")
        (tmp_path / "b.tsx").write_text("export default () => null;")
        result = _count_languages(tmp_path)
        assert result["typescript"] == 2
        assert "python" not in result

    def test_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("x = 1")
        (tmp_path / "utils.py").write_text("y = 2")
        result = _count_languages(tmp_path)
        assert result["python"] == 2
        assert "typescript" not in result

    def test_node_modules_skipped(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules" / "some-pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {};")
        (tmp_path / "app.ts").write_text("const x = 1;")
        result = _count_languages(tmp_path)
        assert result.get("typescript") == 1

    def test_next_dir_skipped(self, tmp_path: Path) -> None:
        next_dir = tmp_path / ".next" / "static"
        next_dir.mkdir(parents=True)
        (next_dir / "chunk.js").write_text("(()=>{})();")
        result = _count_languages(tmp_path)
        assert result == {}

    def test_mixed_languages(self, tmp_path: Path) -> None:
        (tmp_path / "handler.ts").write_text("export {};")
        (tmp_path / "script.py").write_text("pass")
        (tmp_path / "helper.js").write_text("const x = 1;")
        result = _count_languages(tmp_path)
        assert result["typescript"] == 2
        assert result["python"] == 1

    def test_other_extensions_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# hello")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        result = _count_languages(tmp_path)
        assert result == {}

    def test_all_ts_extensions_counted(self, tmp_path: Path) -> None:
        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            (tmp_path / f"file{ext}").write_text("x = 1;")
        result = _count_languages(tmp_path)
        assert result["typescript"] == 6


class TestAnalyzeSync:
    def test_returns_analysis_result(self, tmp_path: Path) -> None:
        (tmp_path / "ai.ts").write_bytes(_GROK_PROVIDER)
        rid = uuid4()
        result = _analyze_sync(tmp_path, rid)
        assert isinstance(result, AnalysisResult)

    def test_repo_id_set_correctly(self, tmp_path: Path) -> None:
        (tmp_path / "ai.ts").write_bytes(b"const x = 1;")
        rid = uuid4()
        result = _analyze_sync(tmp_path, rid)
        assert result.repo_id == rid

    def test_language_breakdown_includes_typescript(self, tmp_path: Path) -> None:
        (tmp_path / "ai.ts").write_bytes(_GROK_PROVIDER)
        result = _analyze_sync(tmp_path, uuid4())
        assert result.language_breakdown.get("typescript") == 1

    def test_node_modules_files_ignored(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.ts").write_bytes(_GROK_PROVIDER)
        result = _analyze_sync(tmp_path, uuid4())
        assert result.language_breakdown.get("typescript", 0) == 0

    def test_analyzed_at_is_utc(self, tmp_path: Path) -> None:
        (tmp_path / "x.ts").write_bytes(b"const x = 1;")
        result = _analyze_sync(tmp_path, uuid4())
        assert result.analyzed_at.tzinfo is not None

    def test_empty_repo_no_crash(self, tmp_path: Path) -> None:
        result = _analyze_sync(tmp_path, uuid4())
        assert result.call_sites == []
        assert result.prompt_templates == []
        assert result.language_breakdown == {}


@pytest.mark.asyncio
async def test_run_analysis_returns_result(tmp_path: Path) -> None:
    (tmp_path / "ai.ts").write_bytes(b"const x = 1;")

    @asynccontextmanager
    async def _fake_clone(url: str, analysis_id: object, *, branch: str = "main"):
        yield tmp_path

    with patch("src.loop.analyze.pipeline.cloned_repo", side_effect=_fake_clone):
        result = await run_analysis("https://github.com/example/repo")

    assert isinstance(result, AnalysisResult)


@pytest.mark.asyncio
async def test_run_analysis_uses_provided_repo_id(tmp_path: Path) -> None:
    (tmp_path / "ai.ts").write_bytes(b"const x = 1;")
    rid = uuid4()

    @asynccontextmanager
    async def _fake_clone(url: str, analysis_id: object, *, branch: str = "main"):
        yield tmp_path

    with patch("src.loop.analyze.pipeline.cloned_repo", side_effect=_fake_clone):
        result = await run_analysis("https://github.com/example/repo", repo_id=rid)

    assert result.repo_id == rid


@pytest.mark.asyncio
async def test_run_analysis_generates_repo_id_when_none(tmp_path: Path) -> None:
    (tmp_path / "ai.ts").write_bytes(b"const x = 1;")

    @asynccontextmanager
    async def _fake_clone(url: str, analysis_id: object, *, branch: str = "main"):
        yield tmp_path

    with patch("src.loop.analyze.pipeline.cloned_repo", side_effect=_fake_clone):
        result = await run_analysis("https://github.com/example/repo")

    assert isinstance(result.repo_id, uuid.UUID)
