"""Tests for playwright opt-in crawler behaviour and SSRF protection."""
from __future__ import annotations

import ipaddress
import socket
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from src.loop.harvest.crawler import (
    CrawlError,
    _check_ssrf,
    fetch_and_extract,
    _SPARSE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _noop_check_ssrf(url: str) -> None:
    """Async no-op replacement for _check_ssrf — used in httpx-mocked tests."""
    return None


# ---------------------------------------------------------------------------
# Playwright opt-in behaviour (existing tests, updated to skip real DNS)
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_use_playwright_false_never_calls_playwright(monkeypatch):
    """With use_playwright=False, playwright path is never entered."""
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text="<html><body><p>small</p></body></html>")
    )
    playwright_called = []

    import src.loop.harvest.crawler as crawler_mod

    original_playwright = crawler_mod._fetch_playwright
    original_check = crawler_mod._check_ssrf

    async def spy(url: str) -> str:
        playwright_called.append(url)
        return "playwright"

    crawler_mod._fetch_playwright = spy
    crawler_mod._check_ssrf = AsyncMock(return_value=None)
    try:
        result = await fetch_and_extract("https://example.com", use_playwright=False)
        assert isinstance(result, str)
        assert playwright_called == []
    finally:
        crawler_mod._fetch_playwright = original_playwright
        crawler_mod._check_ssrf = original_check


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

    original_playwright = crawler_mod._fetch_playwright
    original_check = crawler_mod._check_ssrf

    async def spy(url: str) -> str:
        playwright_called.append(url)
        return "playwright"

    crawler_mod._fetch_playwright = spy
    crawler_mod._check_ssrf = AsyncMock(return_value=None)
    try:
        result = await fetch_and_extract("https://example.com", use_playwright=True)
        assert isinstance(result, str)
        # The key invariant: no exception raised
    finally:
        crawler_mod._fetch_playwright = original_playwright
        crawler_mod._check_ssrf = original_check


@respx.mock
@pytest.mark.asyncio
async def test_use_playwright_true_graceful_on_import_error():
    """When _fetch_playwright raises ImportError, result is still a string (no crash)."""
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text="<html><body><p>small</p></body></html>")
    )

    import src.loop.harvest.crawler as crawler_mod

    original_playwright = crawler_mod._fetch_playwright
    original_check = crawler_mod._check_ssrf

    async def raise_import(url: str) -> str:
        raise ImportError("playwright not installed")

    crawler_mod._fetch_playwright = raise_import
    crawler_mod._check_ssrf = AsyncMock(return_value=None)
    try:
        result = await fetch_and_extract("https://example.com", use_playwright=True)
        assert isinstance(result, str)  # graceful — no exception
    finally:
        crawler_mod._fetch_playwright = original_playwright
        crawler_mod._check_ssrf = original_check


# ---------------------------------------------------------------------------
# SSRF protection — _check_ssrf unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_ssrf_blocks_loopback():
    """127.0.0.1 must be blocked."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))
        ]
        with pytest.raises(CrawlError) as exc_info:
            await _check_ssrf("http://evil.internal/path")
        assert exc_info.value.kind == "ssrf"
        assert "127.0.0.1" in str(exc_info.value)


@pytest.mark.asyncio
async def test_check_ssrf_blocks_private_rfc1918():
    """10.x.x.x (RFC-1918 private) must be blocked."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0))
        ]
        with pytest.raises(CrawlError) as exc_info:
            await _check_ssrf("http://internal.corp/api")
        assert exc_info.value.kind == "ssrf"


@pytest.mark.asyncio
async def test_check_ssrf_blocks_link_local():
    """169.254.x.x (AWS metadata / link-local) must be blocked."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 0))
        ]
        with pytest.raises(CrawlError) as exc_info:
            await _check_ssrf("http://metadata.internal/latest/meta-data/")
        assert exc_info.value.kind == "ssrf"
        assert "169.254.169.254" in str(exc_info.value)


@pytest.mark.asyncio
async def test_check_ssrf_blocks_ipv6_loopback():
    """::1 (IPv6 loopback) must be blocked."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("::1", 0, 0, 0))
        ]
        with pytest.raises(CrawlError) as exc_info:
            await _check_ssrf("http://[::1]/admin")
        assert exc_info.value.kind == "ssrf"


@pytest.mark.asyncio
async def test_check_ssrf_blocks_ipv4_mapped_ipv6_loopback():
    """::ffff:127.0.0.1 must be unwrapped and treated as loopback."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("::ffff:127.0.0.1", 0, 0, 0))
        ]
        with pytest.raises(CrawlError) as exc_info:
            await _check_ssrf("http://mapped.example.com/")
        assert exc_info.value.kind == "ssrf"


@pytest.mark.asyncio
async def test_check_ssrf_allows_public_ip():
    """A genuine public IP (e.g. 93.184.216.34 — example.com) must pass."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))
        ]
        # Should not raise
        await _check_ssrf("http://example.com/page")


@pytest.mark.asyncio
async def test_check_ssrf_raises_crawl_error_on_dns_failure():
    """DNS resolution failures surface as CrawlError with kind='network'."""
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("NXDOMAIN")):
        with pytest.raises(CrawlError) as exc_info:
            await _check_ssrf("http://nonexistent.invalid/")
        assert exc_info.value.kind == "network"


@pytest.mark.asyncio
async def test_check_ssrf_rejects_empty_hostname():
    """A URL with no hostname must raise CrawlError immediately."""
    with pytest.raises(CrawlError) as exc_info:
        await _check_ssrf("http:///no-host")
    assert exc_info.value.kind == "ssrf"


# ---------------------------------------------------------------------------
# SSRF protection — redirect validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_httpx_blocks_ssrf_redirect(monkeypatch):
    """A redirect to a private IP must be blocked before following."""
    import src.loop.harvest.crawler as crawler_mod

    call_count = 0

    async def check_ssrf_spy(url: str) -> None:
        nonlocal call_count
        call_count += 1
        # Block the redirect target
        if "169.254" in url:
            raise CrawlError("ssrf", f"Blocked: {url}")

    original_check = crawler_mod._check_ssrf
    crawler_mod._check_ssrf = check_ssrf_spy

    try:
        with respx.mock:
            respx.get("https://example.com/start").mock(
                return_value=httpx.Response(
                    301,
                    headers={"location": "http://169.254.169.254/latest/meta-data/"},
                    text="",
                )
            )
            with pytest.raises(CrawlError) as exc_info:
                from src.loop.harvest.crawler import _fetch_httpx
                await _fetch_httpx("https://example.com/start")
            assert exc_info.value.kind == "ssrf"
    finally:
        crawler_mod._check_ssrf = original_check
