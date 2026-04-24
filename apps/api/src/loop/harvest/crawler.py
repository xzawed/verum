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
            is not installed, the httpx result is returned with a warning logged.

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
    except CrawlError as exc:
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
        CrawlError: on browser-level network or navigation failure.
    """
    from playwright.async_api import Error as PlaywrightError  # soft import
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30_000)
                html = await page.content()
            finally:
                await browser.close()
    except PlaywrightError as exc:
        raise CrawlError("playwright", str(exc)) from exc

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
