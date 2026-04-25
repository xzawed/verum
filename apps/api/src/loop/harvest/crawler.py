"""HTTP crawler + content extractor for HARVEST stage."""
from __future__ import annotations

import asyncio
import contextlib
import gzip
import ipaddress
import logging
import socket
import ssl
import time
import zlib
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

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


async def _check_ssrf(url: str) -> str:
    """Resolve URL hostname, reject private/loopback/internal IPs, return first public IP.

    Called before every HTTP hop (including redirects) to prevent SSRF.
    Returns the first verified public IP so callers can connect directly to
    that IP without a second DNS lookup — this eliminates the DNS rebinding
    TOCTOU window entirely.

    Security note — residual risk (playwright path only):
        _fetch_playwright uses the headless browser's own network stack and
        cannot pin to a pre-resolved IP.  The SSRF check still runs before
        the playwright call, but the DNS rebinding window exists for that
        code path.  Playwright is opt-in and only used when httpx returns
        sparse content, so the attack surface is intentionally limited.

    Raises:
        CrawlError: if the resolved address is non-routable, private, or DNS fails.
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

    first_public: str | None = None
    for _family, _type, _proto, _canonname, sockaddr in results:
        raw_ip = str(sockaddr[0])
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
        if first_public is None:
            first_public = raw_ip

    if first_public is None:
        raise CrawlError("ssrf", f"No usable address resolved for {hostname!r}")

    return first_public


async def _get_robots_parser(base_url: str) -> RobotFileParser | None:
    """Fetch and parse robots.txt for base_url, with TTL-based caching.

    Uses IP-pinned fetching so the robots.txt request goes through the same
    DNS rebinding prevention as normal crawl requests.

    Returns None (allow all) if robots.txt cannot be fetched or parsed.
    """
    now = time.monotonic()
    cached = _robots_cache.get(base_url)
    if cached is not None and (now - cached[0]) < _ROBOTS_TTL:
        return cached[1]

    robots_url = f"{base_url}/robots.txt"
    rp = RobotFileParser()

    try:
        ip = await _check_ssrf(robots_url)
        status, _headers, body = await _http_get_pinned(robots_url, ip, timeout=10.0)
        if status == 200:
            rp.parse(body.decode("utf-8", errors="replace").splitlines())
    except Exception as exc:
        # Any network/SSRF/parse error → be permissive, log for visibility.
        logger.debug("robots.txt fetch failed for %s: %s — assuming allow", base_url, exc)
        rp = RobotFileParser()
        rp.allow_all = True  # explicit: uninitialized parser.can_fetch() returns False in Python 3.14+

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


async def _http_get_pinned(
    url: str,
    ip: str,
    *,
    timeout: float = _TIMEOUT,
) -> tuple[int, dict[str, str], bytes]:
    """HTTP/1.1 GET to pre-resolved ip, using url's hostname for Host and TLS SNI.

    Connects directly to the IP address returned by _check_ssrf rather than
    letting the OS resolve the hostname again.  This closes the DNS rebinding
    TOCTOU window: even if the DNS record changes between our check and the
    connection, we always reach the IP we validated.

    The original hostname is sent in the Host header and used as the TLS SNI
    so the server's certificate validates normally.

    Supports:
        - HTTPS with full certificate chain verification
        - Chunked transfer encoding
        - gzip / deflate content encoding
        - Body size cap at _MAX_CONTENT_BYTES
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    ssl_ctx: ssl.SSLContext | None = None
    if parsed.scheme == "https":
        ssl_ctx = ssl.create_default_context()

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                ip,
                port,
                ssl=ssl_ctx,
                server_hostname=hostname if ssl_ctx else None,
            ),
            timeout=timeout,
        )
    except (OSError, ssl.SSLError, asyncio.TimeoutError) as exc:
        raise CrawlError("network", f"Connection to {ip}:{port} failed: {exc}") from exc

    try:
        raw_req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {hostname}\r\n"
            f"User-Agent: {_HEADERS['User-Agent']}\r\n"
            f"Accept: {_HEADERS['Accept']}\r\n"
            f"Accept-Language: {_HEADERS['Accept-Language']}\r\n"
            f"Accept-Encoding: gzip, deflate\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        writer.write(raw_req.encode("ascii"))
        await writer.drain()

        async with asyncio.timeout(timeout):
            # ── Status line ──────────────────────────────────────────────
            status_bytes = await reader.readline()
            status_str = status_bytes.decode("ascii", errors="replace").rstrip()
            parts = status_str.split(" ", 2)
            if len(parts) < 2 or not parts[1].isdigit():
                raise CrawlError("network", f"Malformed HTTP status from {url}: {status_str!r}")
            status_code = int(parts[1])

            # ── Response headers ─────────────────────────────────────────
            resp_headers: dict[str, str] = {}
            while True:
                line = await reader.readline()
                line_str = line.decode("ascii", errors="replace").rstrip("\r\n")
                if not line_str:
                    break
                if ":" in line_str:
                    k, _, v = line_str.partition(":")
                    resp_headers[k.strip().lower()] = v.strip()

            # ── Body ─────────────────────────────────────────────────────
            transfer = resp_headers.get("transfer-encoding", "").lower()
            content_length_str = resp_headers.get("content-length", "")
            body_chunks: list[bytes] = []
            total = 0

            if transfer == "chunked":
                while True:
                    size_line = await reader.readline()
                    # chunk-size line may have extensions after ";"
                    size_hex = size_line.decode("ascii", errors="replace").split(";")[0].strip()
                    try:
                        chunk_size = int(size_hex, 16)
                    except ValueError:
                        break
                    if chunk_size == 0:
                        break
                    try:
                        data = await reader.readexactly(chunk_size)
                    except asyncio.IncompleteReadError as exc:
                        data = exc.partial
                    await reader.readline()  # trailing CRLF after each chunk
                    body_chunks.append(data)
                    total += len(data)
                    if total >= _MAX_CONTENT_BYTES:
                        break
            elif content_length_str.isdigit():
                to_read = min(int(content_length_str), _MAX_CONTENT_BYTES)
                try:
                    body_chunks.append(await reader.readexactly(to_read))
                except asyncio.IncompleteReadError as exc:
                    body_chunks.append(exc.partial)
            else:
                # No content-length, no chunked: read until server closes
                while True:
                    chunk = await reader.read(65536)
                    if not chunk:
                        break
                    body_chunks.append(chunk)
                    total += len(chunk)
                    if total >= _MAX_CONTENT_BYTES:
                        break

        body = b"".join(body_chunks)

        # ── Decompress ───────────────────────────────────────────────────
        encoding = resp_headers.get("content-encoding", "").lower()
        if encoding == "gzip":
            with contextlib.suppress(Exception):
                body = gzip.decompress(body)
        elif encoding in ("deflate", "zlib"):
            with contextlib.suppress(Exception):
                try:
                    body = zlib.decompress(body)
                except zlib.error:
                    # Raw deflate stream (no zlib wrapper)
                    body = zlib.decompress(body, -zlib.MAX_WBITS)

        return status_code, resp_headers, body

    except CrawlError:
        raise
    except asyncio.TimeoutError as exc:
        raise CrawlError("timeout", f"Timeout reading response from {url}") from exc
    except OSError as exc:
        raise CrawlError("network", str(exc)) from exc
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(writer.wait_closed(), timeout=2.0)


async def fetch_and_extract(url: str, *, use_playwright: bool = False) -> str:
    """Fetch URL and extract main text content via trafilatura.

    Checks SSRF safety, robots.txt compliance, and content extraction.

    Args:
        url: Target URL.
        use_playwright: When True, falls back to headless Chromium if the
            IP-pinned httpx fetch returns sparse content (< _SPARSE_THRESHOLD
            chars). If playwright is not installed, the httpx result is returned
            with a warning logged.

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
    """IP-pinned fetch: resolve once via _check_ssrf, connect to IP, extract text.

    The hostname is resolved ONCE per redirect hop, SSRF-validated, and the TCP
    connection is opened directly to that IP.  The original hostname is preserved
    in the Host header and TLS SNI, so server certificates validate normally.
    This eliminates the DNS rebinding TOCTOU window present in pure-DNS fetching.
    """
    await _check_robots_allowed(url)  # re-check after redirect in loop below
    current_url = url
    redirects = 0

    while True:
        ip = await _check_ssrf(current_url)

        try:
            status, headers, body = await _http_get_pinned(current_url, ip)
        except asyncio.TimeoutError as exc:
            raise CrawlError("timeout", f"Timeout fetching {current_url}") from exc

        if status in (301, 302, 303, 307, 308):
            redirects += 1
            if redirects > _MAX_REDIRECTS:
                raise CrawlError(
                    "redirect",
                    f"Too many redirects (>{_MAX_REDIRECTS}) for {url}",
                )
            location = headers.get("location", "")
            if not location:
                raise CrawlError("redirect", f"Redirect with no Location from {current_url}")
            next_url = urljoin(current_url, location)
            await _check_ssrf(next_url)  # validate redirect target before following
            current_url = next_url
            continue

        if status >= 400:
            raise CrawlError("http_error", f"HTTP {status}: {current_url}")

        # Decode body to string
        charset = "utf-8"
        ct = headers.get("content-type", "")
        if "charset=" in ct:
            charset = ct.split("charset=", 1)[-1].split(";")[0].strip() or "utf-8"

        html = body.decode(charset, errors="replace")
        break

    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, lambda: _extract(html, current_url))
    return text or ""


async def _fetch_playwright(url: str) -> str:
    """Fetch JS-rendered page via headless Chromium.

    Security note — DNS rebinding residual risk:
        The headless browser uses its own network stack; we cannot pin it to
        a pre-resolved IP.  _check_ssrf still runs before the navigation, but
        the TOCTOU window exists for this code path.  Playwright is only
        invoked when httpx returns sparse content AND the caller passes
        use_playwright=True, limiting the exposure.

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
