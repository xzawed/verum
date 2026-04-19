"""HTTP crawler + content extractor for HARVEST stage."""
from __future__ import annotations

import asyncio

import httpx
import trafilatura

_HEADERS = {
    "User-Agent": "Verum-Bot/1.0 (https://github.com/xzawed/verum; bot@verum.dev)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
}
_TIMEOUT = 30.0
_MAX_CONTENT_BYTES = 2 * 1024 * 1024  # 2 MB cap


class CrawlError(Exception):
    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind


async def fetch_and_extract(url: str) -> str:
    """Fetch URL and extract main text content via trafilatura.

    Returns:
        Extracted plain text (may be empty string if extraction fails).

    Raises:
        CrawlError: on network or HTTP errors.
    """
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

    # Run trafilatura in executor to avoid blocking the event loop
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
