"""Tests for playwright opt-in crawler behaviour and SSRF protection.

Crawler was rewritten (commit 55f5ce8) to use a raw asyncio TCP transport
instead of httpx.  All high-level tests now mock _http_get_pinned (the new
transport layer) and/or _fetch_httpx/_fetch_playwright directly.
"""
from __future__ import annotations

import asyncio
import socket
from unittest.mock import AsyncMock, patch

import pytest

from src.loop.harvest.crawler import (
    CrawlError,
    _check_ssrf,
    _fetch_httpx,
    fetch_and_extract,
    _SPARSE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# SSRF protection — _check_ssrf unit tests (pure socket mock, unchanged)
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
    """A genuine public IP must pass without raising."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))
        ]
        result = await _check_ssrf("http://example.com/page")
    assert result == "93.184.216.34"


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
# fetch_and_extract — playwright opt-in logic
# (mock _fetch_httpx and _fetch_playwright to isolate the routing logic)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_use_playwright_false_never_calls_playwright():
    """With use_playwright=False, playwright path is never entered."""
    playwright_called = []

    async def spy(url: str) -> str:
        playwright_called.append(url)
        return "playwright content"

    with patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch("src.loop.harvest.crawler._fetch_httpx", new_callable=AsyncMock, return_value="httpx content"), \
         patch("src.loop.harvest.crawler._fetch_playwright", spy):
        result = await fetch_and_extract("https://example.com", use_playwright=False)

    assert playwright_called == []
    assert result == "httpx content"


@pytest.mark.asyncio
async def test_use_playwright_true_skips_playwright_when_content_rich():
    """When httpx returns content >= _SPARSE_THRESHOLD, playwright is not called."""
    rich_content = "meaningful content " * 20  # well above 200-char threshold
    playwright_called = []

    async def spy(url: str) -> str:
        playwright_called.append(url)
        return "playwright"

    with patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch("src.loop.harvest.crawler._fetch_httpx", new_callable=AsyncMock, return_value=rich_content), \
         patch("src.loop.harvest.crawler._fetch_playwright", spy):
        result = await fetch_and_extract("https://example.com", use_playwright=True)

    assert playwright_called == []
    assert result == rich_content


@pytest.mark.asyncio
async def test_use_playwright_true_graceful_on_import_error():
    """When _fetch_playwright raises ImportError, httpx result is returned (no crash)."""
    async def raise_import(url: str) -> str:
        raise ImportError("playwright not installed")

    with patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch("src.loop.harvest.crawler._fetch_httpx", new_callable=AsyncMock, return_value="sparse"), \
         patch("src.loop.harvest.crawler._fetch_playwright", raise_import):
        result = await fetch_and_extract("https://example.com", use_playwright=True)

    assert result == "sparse"


@pytest.mark.asyncio
async def test_fetch_and_extract_playwright_success():
    """When playwright returns non-empty text, that result beats the sparse httpx result."""
    async def rich_playwright(url: str) -> str:
        return "detailed content from playwright rendering"

    with patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch("src.loop.harvest.crawler._fetch_httpx", new_callable=AsyncMock, return_value="sparse"), \
         patch("src.loop.harvest.crawler._fetch_playwright", rich_playwright):
        result = await fetch_and_extract("https://example.com/spa", use_playwright=True)

    assert "playwright" in result


@pytest.mark.asyncio
async def test_fetch_and_extract_playwright_crawl_error_fallback():
    """When playwright raises CrawlError, httpx result is returned instead."""
    async def failing_playwright(url: str) -> str:
        raise CrawlError("playwright", "browser crashed")

    with patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch("src.loop.harvest.crawler._fetch_httpx", new_callable=AsyncMock, return_value="sparse"), \
         patch("src.loop.harvest.crawler._fetch_playwright", failing_playwright):
        result = await fetch_and_extract("https://example.com/broken-spa", use_playwright=True)

    assert result == "sparse"


# ---------------------------------------------------------------------------
# _fetch_httpx — error paths (mock _http_get_pinned + _check_ssrf)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_httpx_too_many_redirects():
    """Exceeding _MAX_REDIRECTS raises CrawlError with kind='redirect'."""
    redirect_response = (302, {"location": "https://example.com/hop"}, b"")

    with patch("src.loop.harvest.crawler._check_ssrf", new_callable=AsyncMock, return_value="1.2.3.4"), \
         patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch("src.loop.harvest.crawler._http_get_pinned", new_callable=AsyncMock, return_value=redirect_response):
        with pytest.raises(CrawlError) as exc_info:
            await _fetch_httpx("https://example.com/start")

    assert exc_info.value.kind == "redirect"


@pytest.mark.asyncio
async def test_fetch_httpx_timeout_raises_crawl_error():
    """asyncio.TimeoutError from _http_get_pinned surfaces as CrawlError kind='timeout'."""
    with patch("src.loop.harvest.crawler._check_ssrf", new_callable=AsyncMock, return_value="1.2.3.4"), \
         patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch("src.loop.harvest.crawler._http_get_pinned", new_callable=AsyncMock, side_effect=asyncio.TimeoutError()):
        with pytest.raises(CrawlError) as exc_info:
            await _fetch_httpx("https://example.com/slow")

    assert exc_info.value.kind == "timeout"


@pytest.mark.asyncio
async def test_fetch_httpx_http_status_error_raises_crawl_error():
    """A 404 response raises CrawlError with kind='http_error'."""
    with patch("src.loop.harvest.crawler._check_ssrf", new_callable=AsyncMock, return_value="1.2.3.4"), \
         patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch("src.loop.harvest.crawler._http_get_pinned", new_callable=AsyncMock, return_value=(404, {}, b"Not Found")):
        with pytest.raises(CrawlError) as exc_info:
            await _fetch_httpx("https://example.com/missing")

    assert exc_info.value.kind == "http_error"
    assert "404" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_httpx_request_error_raises_crawl_error():
    """A network-level CrawlError from _http_get_pinned propagates unchanged."""
    net_err = CrawlError("network", "connection refused")

    with patch("src.loop.harvest.crawler._check_ssrf", new_callable=AsyncMock, return_value="1.2.3.4"), \
         patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch("src.loop.harvest.crawler._http_get_pinned", new_callable=AsyncMock, side_effect=net_err):
        with pytest.raises(CrawlError) as exc_info:
            await _fetch_httpx("https://example.com/offline")

    assert exc_info.value.kind == "network"


@pytest.mark.asyncio
async def test_fetch_httpx_blocks_ssrf_redirect():
    """A redirect to a private IP must be blocked before following."""
    import src.loop.harvest.crawler as crawler_mod

    call_count = 0

    async def check_ssrf_spy(url: str) -> str:
        nonlocal call_count
        call_count += 1
        if "169.254" in url:
            raise CrawlError("ssrf", f"Blocked: {url}")
        return "1.2.3.4"

    original_check = crawler_mod._check_ssrf
    crawler_mod._check_ssrf = check_ssrf_spy

    try:
        with patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
             patch(
                 "src.loop.harvest.crawler._http_get_pinned",
                 new_callable=AsyncMock,
                 return_value=(301, {"location": "http://169.254.169.254/latest/meta-data/"}, b""),
             ):
            with pytest.raises(CrawlError) as exc_info:
                await _fetch_httpx("https://example.com/start")
        assert exc_info.value.kind == "ssrf"
    finally:
        crawler_mod._check_ssrf = original_check


# ---------------------------------------------------------------------------
# _fetch_httpx — success path, charset, no-Location redirect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_httpx_success_returns_extracted_text():
    """A 200 response is decoded via charset and returned as extracted text."""
    body = b"<html><body><p>Hello world</p></body></html>"

    with patch("src.loop.harvest.crawler._check_ssrf", new_callable=AsyncMock, return_value="1.2.3.4"), \
         patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch(
             "src.loop.harvest.crawler._http_get_pinned",
             new_callable=AsyncMock,
             return_value=(200, {"content-type": "text/html; charset=utf-8"}, body),
         ), \
         patch("src.loop.harvest.crawler._extract", return_value="Hello world"):
        text = await _fetch_httpx("http://example.com/page")

    assert text == "Hello world"


@pytest.mark.asyncio
async def test_fetch_httpx_returns_empty_string_when_extract_returns_none():
    """When _extract returns None, _fetch_httpx returns empty string."""
    body = b"<html></html>"

    with patch("src.loop.harvest.crawler._check_ssrf", new_callable=AsyncMock, return_value="1.2.3.4"), \
         patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch(
             "src.loop.harvest.crawler._http_get_pinned",
             new_callable=AsyncMock,
             return_value=(200, {}, body),
         ), \
         patch("src.loop.harvest.crawler._extract", return_value=None):
        text = await _fetch_httpx("http://example.com/empty")

    assert text == ""


@pytest.mark.asyncio
async def test_fetch_httpx_redirect_no_location_raises():
    """A redirect with no Location header raises CrawlError kind='redirect'."""
    with patch("src.loop.harvest.crawler._check_ssrf", new_callable=AsyncMock, return_value="1.2.3.4"), \
         patch("src.loop.harvest.crawler._check_robots_allowed", new_callable=AsyncMock), \
         patch(
             "src.loop.harvest.crawler._http_get_pinned",
             new_callable=AsyncMock,
             return_value=(302, {}, b""),
         ):
        with pytest.raises(CrawlError) as exc_info:
            await _fetch_httpx("http://example.com/redirect")

    assert exc_info.value.kind == "redirect"
