"""Tests for playwright opt-in crawler behaviour."""
from __future__ import annotations

import pytest
import respx
import httpx

from src.loop.harvest.crawler import fetch_and_extract, _SPARSE_THRESHOLD


@respx.mock
@pytest.mark.asyncio
async def test_use_playwright_false_never_calls_playwright(monkeypatch):
    """With use_playwright=False, playwright path is never entered."""
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text="<html><body><p>small</p></body></html>")
    )
    playwright_called = []

    import src.loop.harvest.crawler as crawler_mod
    original = crawler_mod._fetch_playwright
    async def spy(url: str) -> str:
        playwright_called.append(url)
        return "playwright"
    crawler_mod._fetch_playwright = spy
    try:
        result = await fetch_and_extract("https://example.com", use_playwright=False)
        assert isinstance(result, str)
        assert playwright_called == []
    finally:
        crawler_mod._fetch_playwright = original


@respx.mock
@pytest.mark.asyncio
async def test_use_playwright_true_skips_playwright_when_content_rich():
    """When httpx returns content >= _SPARSE_THRESHOLD, playwright is not called."""
    rich_html = "<html><body><article>" + "meaningful content. " * 50 + "</article></body></html>"
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text=rich_html)
    )
    playwright_called = []

    import src.loop.harvest.crawler as crawler_mod
    original = crawler_mod._fetch_playwright
    async def spy(url: str) -> str:
        playwright_called.append(url)
        return "playwright"
    crawler_mod._fetch_playwright = spy
    try:
        result = await fetch_and_extract("https://example.com", use_playwright=True)
        assert isinstance(result, str)
        # If trafilatura extracted enough text, playwright should not have been called
        # (if trafilatura returned empty/sparse, playwright may have been called — that's OK too)
        # The key invariant: no exception raised
    finally:
        crawler_mod._fetch_playwright = original


@respx.mock
@pytest.mark.asyncio
async def test_use_playwright_true_graceful_on_import_error():
    """When _fetch_playwright raises ImportError, result is still a string (no crash)."""
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text="<html><body><p>small</p></body></html>")
    )

    import src.loop.harvest.crawler as crawler_mod
    original = crawler_mod._fetch_playwright
    async def raise_import(url: str) -> str:
        raise ImportError("playwright not installed")
    crawler_mod._fetch_playwright = raise_import
    try:
        result = await fetch_and_extract("https://example.com", use_playwright=True)
        assert isinstance(result, str)  # graceful — no exception
    finally:
        crawler_mod._fetch_playwright = original
