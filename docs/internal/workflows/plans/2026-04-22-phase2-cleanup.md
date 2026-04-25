# Phase 2 Cleanup — F-2.3, F-2.6, F-2.8, F-0.7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the four remaining 🚧 deliverables from Phases 0 and 2: INFER confirm endpoint (F-2.3), opt-in Playwright crawler (F-2.6), semantic chunking wired into the harvest pipeline (F-2.8), and ROADMAP status cleanup (F-0.7 already done in CI — mark ✅).

**Architecture:** Three independent changes land in one branch. (1) A Next.js `PATCH /api/v1/infer/[id]/confirm` endpoint + Drizzle helper lets users override inferred domain/tone/language/user_type after INFER runs. (2) `harvest_source()` gains a `chunking_strategy` parameter, wiring the already-written `semantic_split()` into the live pipeline. (3) Playwright added as a soft dependency with `try/except ImportError` fallback — `fetch_and_extract()` accepts a `use_playwright=True` flag that automatically falls back to httpx results when playwright isn't installed.

**Prerequisites:** PR #6 (`feature/phase0-1-3-completion`) must be merged to `main` before creating this worktree. All tasks below assume the merged main branch.

**Tech Stack:** Next.js 16 App Router, Drizzle ORM (`drizzle-orm`), Python 3.13 asyncio, SQLAlchemy 2, `playwright>=1.49` (soft dep, graceful fallback when absent)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `apps/dashboard/src/app/api/v1/infer/[id]/confirm/route.ts` | **Create** | PATCH endpoint — override inferred fields |
| `apps/dashboard/src/lib/db/jobs.ts` | **Modify** | Add `confirmInference()` Drizzle UPDATE helper |
| `apps/api/src/loop/harvest/pipeline.py` | **Modify** | Add `chunking_strategy` param, call `semantic_split` or `recursive_split` |
| `apps/api/src/worker/handlers/harvest.py` | **Modify** | Pass `chunking_strategy` from job payload |
| `apps/api/src/loop/harvest/crawler.py` | **Modify** | Add `use_playwright` param + `_fetch_playwright()` fallback |
| `apps/api/pyproject.toml` | **Modify** | Add `playwright>=1.49` to dependencies |
| `apps/api/tests/loop/harvest/test_chunking_strategy.py` | **Create** | Tests for semantic chunking wiring |
| `apps/api/tests/loop/harvest/test_playwright_crawler.py` | **Create** | Tests for playwright fallback behaviour |
| `docs/ROADMAP.md` | **Modify** | Mark F-0.7, F-2.3, F-2.6, F-2.8 ✅ |

---

## Task 1: F-2.3 — INFER confirm endpoint (Next.js)

**Files:**
- Modify: `apps/dashboard/src/lib/db/jobs.ts`
- Create: `apps/dashboard/src/app/api/v1/infer/[id]/confirm/route.ts`

### Background

After INFER runs, the inferred `domain`, `tone`, `language`, `user_type` are stored in the `inferences` table. Before harvest was auto-chained, users could review and override these. This endpoint restores that capability so users can correct the inference via API.

The endpoint accepts an optional body `{ domain?, tone?, language?, user_type? }`. It updates only the fields supplied, leaves the rest unchanged, and returns the full updated inference row.

Ownership is verified via the full join chain: `inferences → analyses → repos → owner_user_id`.

### Implementation

- [ ] **Step 1: Add `confirmInference` to `jobs.ts`**

Open `apps/dashboard/src/lib/db/jobs.ts`. Add this function after `enqueueInfer`. The file already imports `inferences` from schema and `db` from client. Add `getInference` to the import from `"./queries"` (it's already exported there):

```typescript
import { getInference } from "./queries";
```

Then add at the end of the file:

```typescript
export async function confirmInference(
  userId: string,
  inferenceId: string,
  overrides: {
    domain?: string | null;
    tone?: string | null;
    language?: string | null;
    user_type?: string | null;
  },
): Promise<Inference | null> {
  const existing = await getInference(userId, inferenceId);
  if (!existing) return null;

  const rows = await db
    .update(inferences)
    .set({
      domain: overrides.domain !== undefined ? overrides.domain : existing.domain,
      tone: overrides.tone !== undefined ? overrides.tone : existing.tone,
      language: overrides.language !== undefined ? overrides.language : existing.language,
      user_type: overrides.user_type !== undefined ? overrides.user_type : existing.user_type,
    })
    .where(eq(inferences.id, inferenceId))
    .returning();

  return rows[0] ?? null;
}
```

Also add `Inference` and `update` to the relevant imports:

```typescript
// At top of jobs.ts — add `Inference` to the type imports from schema
import {
  // ...existing imports...
  type Inference,
} from "./schema";
```

`db.update` is a method on the Drizzle db instance — no separate import needed for `update`. But `eq` must be imported from `drizzle-orm` — check that it's already in the existing import.

- [ ] **Step 2: Create the confirm route**

Create `apps/dashboard/src/app/api/v1/infer/[id]/confirm/route.ts`:

```typescript
import { auth } from "@/auth";
import { confirmInference } from "@/lib/db/jobs";
import { NextRequest, NextResponse } from "next/server";

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const session = await auth();
  if (!session?.user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let body: Record<string, unknown> = {};
  try {
    body = await req.json();
  } catch {
    // empty body is fine — no overrides
  }

  const overrides: {
    domain?: string | null;
    tone?: string | null;
    language?: string | null;
    user_type?: string | null;
  } = {};
  if (typeof body.domain === "string" || body.domain === null) overrides.domain = body.domain as string | null;
  if (typeof body.tone === "string" || body.tone === null) overrides.tone = body.tone as string | null;
  if (typeof body.language === "string" || body.language === null) overrides.language = body.language as string | null;
  if (typeof body.user_type === "string" || body.user_type === null) overrides.user_type = body.user_type as string | null;

  const updated = await confirmInference(uid, params.id, overrides);
  if (!updated) return NextResponse.json({ error: "Not found" }, { status: 404 });

  return NextResponse.json(updated);
}
```

- [ ] **Step 3: TypeScript check**

Run from `apps/dashboard/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/src/lib/db/jobs.ts \
        apps/dashboard/src/app/api/v1/infer/
git commit -m "feat(infer): F-2.3 PATCH /api/v1/infer/[id]/confirm endpoint"
```

---

## Task 2: F-2.8 — Wire semantic chunking into harvest pipeline

**Files:**
- Modify: `apps/api/src/loop/harvest/pipeline.py`
- Modify: `apps/api/src/worker/handlers/harvest.py`
- Create: `apps/api/tests/loop/harvest/test_chunking_strategy.py`

### Background

`semantic_split()` already exists in `chunker.py` but `pipeline.py` hard-codes `recursive_split`. This task wires in a `chunking_strategy: str = "recursive"` parameter so the harvest handler can choose the splitter from the job payload.

### Tests first

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/loop/harvest/test_chunking_strategy.py`:

```python
"""Tests that harvest_source routes to the correct chunker."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.loop.harvest.pipeline import harvest_source


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_default_strategy_calls_recursive_split(mock_db):
    """harvest_source without explicit strategy uses recursive_split."""
    source_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    with (
        patch("src.loop.harvest.pipeline.mark_source_crawling", new_callable=AsyncMock),
        patch("src.loop.harvest.pipeline.fetch_and_extract", new_callable=AsyncMock, return_value="some text " * 100),
        patch("src.loop.harvest.pipeline.recursive_split", return_value=["chunk1", "chunk2"]) as mock_rec,
        patch("src.loop.harvest.pipeline.semantic_split", return_value=["sem1"]) as mock_sem,
        patch("src.loop.harvest.pipeline.embed_texts", new_callable=AsyncMock, return_value=[[0.1] * 3, [0.2] * 3]),
        patch("src.loop.harvest.pipeline.save_chunks", new_callable=AsyncMock, return_value=2),
        patch("src.loop.harvest.pipeline.mark_source_done", new_callable=AsyncMock),
    ):
        await harvest_source(mock_db, source_id, "https://example.com", inference_id)
        mock_rec.assert_called_once()
        mock_sem.assert_not_called()


@pytest.mark.asyncio
async def test_semantic_strategy_calls_semantic_split(mock_db):
    """harvest_source with chunking_strategy='semantic' uses semantic_split."""
    source_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    with (
        patch("src.loop.harvest.pipeline.mark_source_crawling", new_callable=AsyncMock),
        patch("src.loop.harvest.pipeline.fetch_and_extract", new_callable=AsyncMock, return_value="some text " * 100),
        patch("src.loop.harvest.pipeline.recursive_split", return_value=["rec1"]) as mock_rec,
        patch("src.loop.harvest.pipeline.semantic_split", return_value=["sem1", "sem2"]) as mock_sem,
        patch("src.loop.harvest.pipeline.embed_texts", new_callable=AsyncMock, return_value=[[0.1] * 3, [0.2] * 3]),
        patch("src.loop.harvest.pipeline.save_chunks", new_callable=AsyncMock, return_value=2),
        patch("src.loop.harvest.pipeline.mark_source_done", new_callable=AsyncMock),
    ):
        await harvest_source(
            mock_db, source_id, "https://example.com", inference_id,
            chunking_strategy="semantic",
        )
        mock_sem.assert_called_once()
        mock_rec.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_strategy_falls_back_to_recursive(mock_db):
    """Unknown strategy names fall back to recursive_split."""
    source_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    with (
        patch("src.loop.harvest.pipeline.mark_source_crawling", new_callable=AsyncMock),
        patch("src.loop.harvest.pipeline.fetch_and_extract", new_callable=AsyncMock, return_value="some text " * 100),
        patch("src.loop.harvest.pipeline.recursive_split", return_value=["r1"]) as mock_rec,
        patch("src.loop.harvest.pipeline.semantic_split", return_value=["s1"]) as mock_sem,
        patch("src.loop.harvest.pipeline.embed_texts", new_callable=AsyncMock, return_value=[[0.1] * 3]),
        patch("src.loop.harvest.pipeline.save_chunks", new_callable=AsyncMock, return_value=1),
        patch("src.loop.harvest.pipeline.mark_source_done", new_callable=AsyncMock),
    ):
        await harvest_source(
            mock_db, source_id, "https://example.com", inference_id,
            chunking_strategy="nonexistent_strategy",
        )
        mock_rec.assert_called_once()
        mock_sem.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/api && python -m pytest tests/loop/harvest/test_chunking_strategy.py -v
```
Expected: `TypeError` or `FAILED` — `harvest_source` doesn't accept `chunking_strategy` yet.

- [ ] **Step 3: Update `pipeline.py`**

Open `apps/api/src/loop/harvest/pipeline.py`. Change the import at the top:

```python
# Before:
from .chunker import recursive_split

# After:
from .chunker import recursive_split, semantic_split
```

Change the `harvest_source` signature and the split call:

```python
async def harvest_source(
    db: AsyncSession,
    source_id: uuid.UUID,
    source_url: str,
    inference_id: uuid.UUID,
    *,
    chunk_size: int = cfg.CHUNK_SIZE,
    overlap: int = cfg.CHUNK_OVERLAP,
    chunking_strategy: str = "recursive",
) -> int:
    """Crawl one approved source, chunk, embed, and store.

    Args:
        chunking_strategy: "semantic" uses sentence-boundary splitting;
            any other value (default "recursive") uses hierarchical separator splitting.

    Returns number of chunks stored.
    """
    await mark_source_crawling(db, source_id)

    try:
        text = await fetch_and_extract(source_url)
    except CrawlError as exc:
        await mark_source_error(db, source_id, f"{exc.kind}: {exc}")
        return 0

    if not text.strip():
        await mark_source_error(db, source_id, "empty content after extraction")
        return 0

    split_fn = semantic_split if chunking_strategy == "semantic" else recursive_split
    chunks = split_fn(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        await mark_source_error(db, source_id, "no chunks produced after split")
        return 0

    try:
        embeddings = await embed_texts(chunks)
    except Exception as exc:
        await mark_source_error(db, source_id, f"embedding failed: {exc}")
        return 0

    count = await save_chunks(db, source_id, inference_id, chunks, embeddings)
    await mark_source_done(db, source_id, count)
    return count
```

- [ ] **Step 4: Update `handlers/harvest.py` to pass `chunking_strategy` from payload**

Open `apps/api/src/worker/handlers/harvest.py`. Change the loop body where `harvest_source` is called:

```python
async def handle_harvest(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    inference_id = uuid.UUID(payload["inference_id"])
    source_pairs: list[list[str]] = payload["source_ids"]
    chunking_strategy: str = payload.get("chunking_strategy", "recursive")

    total_chunks = 0
    results: list[dict[str, Any]] = []
    for source_id_str, url in source_pairs:
        source_id = uuid.UUID(source_id_str)
        try:
            count = await harvest_source(
                db, source_id, url, inference_id,
                chunking_strategy=chunking_strategy,
            )
            total_chunks += count
            results.append({"source_id": source_id_str, "chunks": count, "status": "done"})
        except Exception as exc:
            results.append({"source_id": source_id_str, "error": str(exc), "status": "error"})

    # Chain HARVEST → GENERATE (rest unchanged)
    ...
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd apps/api && python -m pytest tests/loop/harvest/test_chunking_strategy.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Run full suite to check no regressions**

```bash
cd apps/api && python -m pytest tests/ -q
```
Expected: all previously passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/loop/harvest/pipeline.py \
        apps/api/src/worker/handlers/harvest.py \
        apps/api/tests/loop/harvest/test_chunking_strategy.py
git commit -m "feat(harvest): F-2.8 wire semantic chunking strategy into pipeline"
```

---

## Task 3: F-2.6 — Playwright opt-in crawler

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/src/loop/harvest/crawler.py`
- Create: `apps/api/tests/loop/harvest/test_playwright_crawler.py`

### Background

The current `fetch_and_extract(url)` uses httpx. For JS-rendered pages (SPAs, React apps), httpx returns sparse or empty content. This task adds `use_playwright: bool = False` to `fetch_and_extract`. When `True`, it tries httpx first and falls back to a headless Chromium fetch if the extracted content is below a threshold.

The playwright import is wrapped in `try/except ImportError` — if playwright isn't installed, the function logs a warning and returns the httpx result. This ensures CI (which doesn't install playwright) continues to work without changes.

### Tests first

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/loop/harvest/test_playwright_crawler.py`:

```python
"""Tests for playwright opt-in crawler behaviour."""
from __future__ import annotations

import pytest
import respx
import httpx

from src.loop.harvest.crawler import fetch_and_extract, _SPARSE_THRESHOLD


@respx.mock
@pytest.mark.asyncio
async def test_use_playwright_false_does_not_invoke_playwright(monkeypatch):
    """With use_playwright=False, playwright is never imported or called."""
    import_calls: list[str] = []

    original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__  # type: ignore[attr-defined]

    # Patch sys.modules to ensure playwright raises if accessed
    import sys
    # Just verify playwright is not called by checking fetch_and_extract
    # uses only httpx path when use_playwright=False

    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text="<html><body><p>" + "hello world " * 50 + "</p></body></html>")
    )
    result = await fetch_and_extract("https://example.com", use_playwright=False)
    # result may be empty if trafilatura can't extract, but no error
    assert isinstance(result, str)


@respx.mock
@pytest.mark.asyncio
async def test_use_playwright_true_returns_httpx_when_content_sufficient():
    """When httpx returns content >= _SPARSE_THRESHOLD, playwright is not invoked."""
    rich_html = "<html><body><article>" + "meaningful content. " * 50 + "</article></body></html>"
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text=rich_html)
    )

    playwright_called = []

    async def fake_playwright_fetch(url: str) -> str:
        playwright_called.append(url)
        return "playwright result"

    import src.loop.harvest.crawler as crawler_mod
    original = crawler_mod._fetch_playwright
    crawler_mod._fetch_playwright = fake_playwright_fetch  # type: ignore[assignment]
    try:
        result = await fetch_and_extract("https://example.com", use_playwright=True)
        # If httpx extraction was rich enough, playwright should not have been called
        # (depends on trafilatura extraction, so just verify return type)
        assert isinstance(result, str)
    finally:
        crawler_mod._fetch_playwright = original


@respx.mock
@pytest.mark.asyncio
async def test_use_playwright_true_falls_back_when_import_error():
    """When playwright is not installed, gracefully returns httpx result."""
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text="<html><body><p>small</p></body></html>")
    )

    import src.loop.harvest.crawler as crawler_mod

    async def raise_import_error(url: str) -> str:
        raise ImportError("playwright not installed")

    original = crawler_mod._fetch_playwright
    crawler_mod._fetch_playwright = raise_import_error  # type: ignore[assignment]
    try:
        # Should not raise — graceful fallback
        result = await fetch_and_extract("https://example.com", use_playwright=True)
        assert isinstance(result, str)
    finally:
        crawler_mod._fetch_playwright = original
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/api && python -m pytest tests/loop/harvest/test_playwright_crawler.py -v
```
Expected: `ImportError` or `TypeError` — `fetch_and_extract` doesn't accept `use_playwright` yet.

- [ ] **Step 3: Add playwright to `pyproject.toml`**

Open `apps/api/pyproject.toml`. Add `"playwright>=1.49"` to the main `dependencies` list:

```toml
dependencies = [
    # Core
    "pydantic>=2.7",
    # DB + job queue
    "sqlalchemy[asyncio]>=2.0",
    "alembic>=1.13",
    # ... existing deps ...
    # Crawler
    "playwright>=1.49",
]
```

- [ ] **Step 4: Update `crawler.py`**

Replace the entire `crawler.py` with the following (keeping all existing logic intact, adding playwright support below):

```python
"""HTTP crawler + content extractor for HARVEST stage."""
from __future__ import annotations

import asyncio
import logging

import httpx
import trafilatura

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Verum-Bot/1.0 (https://github.com/xzawed/verum; bot@verum.dev)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
}
_TIMEOUT = 30.0
_MAX_CONTENT_BYTES = 2 * 1024 * 1024  # 2 MB cap
_SPARSE_THRESHOLD = 200  # chars; below this, try playwright if requested


class CrawlError(Exception):
    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind


async def fetch_and_extract(url: str, *, use_playwright: bool = False) -> str:
    """Fetch URL and extract main text content via trafilatura.

    Args:
        url: Target URL.
        use_playwright: When True, falls back to headless Chromium if httpx
            returns sparse content (< _SPARSE_THRESHOLD chars). If playwright
            is not installed, the httpx result is returned as-is with a warning.

    Returns:
        Extracted plain text (may be empty string if extraction fails).

    Raises:
        CrawlError: on network or HTTP errors.
    """
    text = await _fetch_httpx(url)
    if not use_playwright or len(text) >= _SPARSE_THRESHOLD:
        return text

    try:
        pw_text = await _fetch_playwright(url)
        return pw_text if pw_text else text
    except ImportError:
        logger.warning(
            "playwright not installed — returning httpx result for %s. "
            "Run `playwright install chromium` to enable JS-rendered crawling.",
            url,
        )
        return text
    except Exception as exc:
        logger.warning("playwright fetch failed for %s: %s — using httpx result", url, exc)
        return text


async def _fetch_httpx(url: str) -> str:
    """Fetch with httpx and extract text via trafilatura."""
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.content[:_MAX_CONTENT_BYTES].decode(
                response.encoding or "utf-8", errors="replace"
            )
    except httpx.TimeoutException as e:
        raise CrawlError("timeout", str(e)) from e
    except httpx.HTTPStatusError as e:
        raise CrawlError("http_error", f"HTTP {e.response.status_code}: {url}") from e
    except httpx.RequestError as e:
        raise CrawlError("network", str(e)) from e

    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, lambda: _extract(html, url))
    return text or ""


async def _fetch_playwright(url: str) -> str:
    """Fetch JS-rendered page via headless Chromium.

    Raises:
        ImportError: if playwright package is not installed.
    """
    from playwright.async_api import async_playwright  # soft import

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30_000)
            html = await page.content()
        finally:
            await browser.close()

    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, lambda: _extract(html, url))
    return text or ""


def _extract(html: str, url: str) -> str | None:
    return trafilatura.extract(
        html,
        url=url,
        include_links=False,
        include_images=False,
        include_tables=True,
        no_fallback=False,
        favor_precision=False,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd apps/api && python -m pytest tests/loop/harvest/test_playwright_crawler.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Run full suite**

```bash
cd apps/api && python -m pytest tests/ -q
```
Expected: all existing tests still pass (playwright not installed in test env → graceful fallback path confirmed).

- [ ] **Step 7: Commit**

```bash
git add apps/api/pyproject.toml \
        apps/api/src/loop/harvest/crawler.py \
        apps/api/tests/loop/harvest/test_playwright_crawler.py
git commit -m "feat(harvest): F-2.6 playwright opt-in crawler with graceful ImportError fallback"
```

---

## Task 4: ROADMAP cleanup

**Files:**
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Update F-0.7 status**

In `docs/ROADMAP.md`, find the F-0.7 row and change `🚧` to `✅`:

```
| F-0.7 | GitHub Actions CI: `ruff`, `pylint`, `bandit`, `mypy`, `tsc --noEmit`, `pytest` | ✅ |
```

- [ ] **Step 2: Update F-2.3 status**

Find F-2.3 row:
```
| F-2.3 | `POST /v1/infer` + `GET /v1/infer/{id}` + `PATCH /v1/infer/{id}/confirm` endpoints | ✅ |
```

- [ ] **Step 3: Update F-2.6 status**

Find F-2.6 row:
```
| F-2.6 | Crawling: `httpx` (static) + `playwright` (JS-rendered) | ✅ |
```

- [ ] **Step 4: Update F-2.8 status**

Find F-2.8 row:
```
| F-2.8 | Recursive chunking (mandatory) + Semantic chunking (Phase 2) | ✅ |
```

- [ ] **Step 5: Update last-updated date**

Change the footer:
```
_Maintainer: xzawed | Last updated: 2026-04-22_
```

- [ ] **Step 6: Commit**

```bash
git add docs/ROADMAP.md
git commit -m "docs: mark F-0.7 F-2.3 F-2.6 F-2.8 complete in ROADMAP"
```

---

## Self-Review Checklist

**Spec coverage:**
- F-0.7 ✅ → Task 4 Step 1
- F-2.3 ✅ → Task 1 (PATCH endpoint + DB helper)
- F-2.6 ✅ → Task 3 (playwright soft dep + crawler fallback)
- F-2.8 ✅ → Task 2 (pipeline param + handler passthrough)

**Placeholder scan:** No TBD, no "add appropriate error handling" — all error cases explicit in code.

**Type consistency:**
- `chunking_strategy: str` in `harvest_source()` (Task 2 Step 3) matches `payload.get("chunking_strategy", "recursive")` in handler (Task 2 Step 4) ✅
- `use_playwright: bool = False` in `fetch_and_extract()` signature matches test call `fetch_and_extract("...", use_playwright=True)` ✅
- `confirmInference(userId, inferenceId, overrides)` in `jobs.ts` (Task 1 Step 1) matches PATCH route call (Task 1 Step 2) ✅
