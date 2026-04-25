"""HTTP crawler + content extractor for HARVEST stage."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import time
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

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
_MAX_REDIRECTS = 5
_ROBOTS_TTL = 3600.0  # seconds; re-fetch robots.txt after 1 hour
_VERUM_BOT_UA = "Verum-Bot"

# Cache: base_url → (fetched_at, RobotFileParser)
_robots_cache: dict[str, tuple[float, RobotFileParser]] = {}


class CrawlError(Exception):
    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind


async def _check_ssrf(url: str) -> None:
    """Resolve URL hostname and reject private/loopback/internal IPs.

    Called before every HTTP hop (including redirects) to prevent SSRF.

    Security note — TOCTOU residual risk:
        There is a narrow time-of-check-to-time-of-use window between this DNS
        resolution and the TCP connection made by httpx.  A DNS rebinding attack
        could exploit this window by switching the record to a private IP after
        the check passes.  The risk is low in practice because:
          (a) the window is <10 ms on the same host,
          (b) an attacker would need to control the target domain's DNS *and* set
              an extremely short TTL to race within that window,
          (c) this check is re-run at every redirect hop, not just once.
        Full mitigation would require connecting directly to the resolved IP and
        passing the original hostname via the Host header + TLS SNI — a
        future enhancement tracked in docs/BACKLOG.md.

    Raises:
        CrawlError: if the resolved address is non-routable or private.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise CrawlError("ssrf", f"Cannot resolve empty hostname in {url!r}")

    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(
            None,
            lambda: socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM),
        )
    except socket.gaierror as exc:
        raise CrawlError("network", f"DNS resolution failed for {hostname!r}: {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in results:
        raw_ip = str(sockaddr[0])
        # Unwrap IPv4-mapped IPv6 addresses (e.g. "::ffff:127.0.0.1")
        if raw_ip.startswith("::ffff:"):
            raw_ip = raw_ip[7:]
        try:
            addr = ipaddress.ip_address(raw_ip)
        except ValueError:
            continue
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
            or addr.is_unspecified
        ):
            raise CrawlError(
                "ssrf",
                f"Blocked request to non-public IP {addr!s} (resolved from {hostname!r})",
            )


async def _get_robots_parser(base_url: str) -> RobotFileParser | None:
    """Fetch and parse robots.txt for base_url, with TTL-based caching.

    Uses our own SSRF-safe httpx fetch so the robots.txt request itself
    goes through the same security checks as normal crawl requests.

    Returns None (allow all) if robots.txt cannot be fetched or parsed.
    """
    now = time.monotonic()
    cached = _robots_cache.get(base_url)
    if cached is not None and (now - cached[0]) < _ROBOTS_TTL:
        return cached[1]

    robots_url = f"{base_url}/robots.txt"
    rp = RobotFileParser()

    try:
        await _check_ssrf(robots_url)
        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=10.0,
            follow_redirects=False,
        ) as client:
            resp = await client.get(robots_url)
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
    except Exception as exc:
        # Any network/SSRF/parse error → be permissive, log for visibility.
        logger.debug("robots.txt fetch failed for %s: %s — assuming allow", base_url, exc)
        rp = RobotFileParser()  # empty parser → allows everything

    _robots_cache[base_url] = (now, rp)
    return rp


async def _check_robots_allowed(url: str) -> None:
    """Raise CrawlError if robots.txt disallows crawling url for Verum-Bot.

    Raises:
        CrawlError: with kind="robots" if the URL is disallowed.
    """
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = await _get_robots_parser(base)
    if rp is not None and not rp.can_fetch(_VERUM_BOT_UA, url):
        raise CrawlError("robots", f"robots.txt disallows {url!r} for {_VERUM_BOT_UA}")


async def fetch_and_extract(url: str, *, use_playwright: bool = False) -> str:
    """Fetch URL and extract main text content via trafilatura.

    Checks SSRF safety, robots.txt compliance, and content extraction.

    Args:
        url: Target URL.
        use_playwright: When True, falls back to headless Chromium if httpx
            returns sparse content (< _SPARSE_THRESHOLD chars). If playwright
            is not installed, the httpx result is returned with a warning logged.

    Returns:
        Extracted plain text (may be empty string if extraction fails).

    Raises:
        CrawlError: on network, SSRF, robots.txt, or HTTP errors.
    """
    await _check_robots_allowed(url)
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
    """Fetch with httpx and extract text via trafilatura.

    Manually follows redirects with SSRF validation at each hop.
    """
    await _check_ssrf(url)
    current_url = url
    redirects = 0

    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=_TIMEOUT,
            follow_redirects=False,
        ) as client:
            while True:
                response = await client.get(current_url)
                if response.is_redirect:
                    redirects += 1
                    if redirects > _MAX_REDIRECTS:
                        raise CrawlError(
                            "redirect",
                            f"Too many redirects (>{_MAX_REDIRECTS}) for {url}",
                        )
                    location = response.headers.get("location", "")
                    next_url = urljoin(current_url, location)
                    await _check_ssrf(next_url)
                    current_url = next_url
                    continue
                response.raise_for_status()
                break

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
    text = await loop.run_in_executor(None, lambda: _extract(html, current_url))
    return text or ""


async def _fetch_playwright(url: str) -> str:
    """Fetch JS-rendered page via headless Chromium.

    Raises:
        ImportError: if playwright package is not installed.
        CrawlError: on browser-level network or navigation failure.
    """
    from playwright.async_api import Error as PlaywrightError  # soft import
    from playwright.async_api import async_playwright

    await _check_ssrf(url)

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
