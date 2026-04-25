"""Security-focused tests for the IP-pinned asyncio crawler.

Covers _http_get_pinned (chunked, content-length, gzip, connection-close),
robots.txt TTL cache, _check_robots_allowed, and _check_ssrf return value /
extended address-class blocking.
"""
from __future__ import annotations

import asyncio
import gzip
import socket
import time
import zlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.loop.harvest.crawler import (
    CrawlError,
    _ROBOTS_TTL,
    _VERUM_BOT_UA,
    _check_robots_allowed,
    _check_ssrf,
    _get_robots_parser,
    _http_get_pinned,
    _robots_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stream_reader(data: bytes) -> asyncio.StreamReader:
    """Return a StreamReader pre-loaded with *data* and EOF set."""
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


def _make_writer() -> MagicMock:
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    return writer


def _http_response(
    status: int,
    headers: dict[str, str],
    body: bytes,
    *,
    chunked: bool = False,
) -> bytes:
    """Build a raw HTTP/1.1 response byte string."""
    reason = {200: "OK", 301: "Moved Permanently", 302: "Found", 404: "Not Found"}.get(status, "")
    lines = [f"HTTP/1.1 {status} {reason}"]
    if chunked:
        headers = {**headers, "transfer-encoding": "chunked"}
        body = _chunked(body)
    else:
        headers = {**headers, "content-length": str(len(body))}
    for k, v in headers.items():
        lines.append(f"{k}: {v}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + body


def _chunked(body: bytes) -> bytes:
    """Encode *body* as a minimal chunked transfer stream."""
    size_hex = format(len(body), "x")
    return f"{size_hex}\r\n".encode("ascii") + body + b"\r\n0\r\n\r\n"


def _mock_open_connection(reader: asyncio.StreamReader, writer: MagicMock):
    """Return an AsyncMock that yields (reader, writer) when awaited."""
    return AsyncMock(return_value=(reader, writer))


# ---------------------------------------------------------------------------
# _check_ssrf — return value and additional address classes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_ssrf_returns_first_public_ip():
    """_check_ssrf must return the first public IP as a string."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("1.1.1.1", 0))
        ]
        result = await _check_ssrf("http://example.com/")
    assert result == "1.1.1.1"


@pytest.mark.asyncio
async def test_check_ssrf_strips_ipv4_mapped_prefix():
    """::ffff:1.1.1.1 must be unwrapped to 1.1.1.1 and allowed."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("::ffff:1.1.1.1", 0, 0, 0))
        ]
        result = await _check_ssrf("http://example.com/")
    assert result == "1.1.1.1"


@pytest.mark.asyncio
async def test_check_ssrf_blocks_multicast():
    """224.0.0.1 (multicast) must be blocked."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("224.0.0.1", 0))
        ]
        with pytest.raises(CrawlError) as exc_info:
            await _check_ssrf("http://multicast.example.com/")
        assert exc_info.value.kind == "ssrf"


@pytest.mark.asyncio
async def test_check_ssrf_blocks_reserved():
    """240.0.0.1 (reserved / class E) must be blocked."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("240.0.0.1", 0))
        ]
        with pytest.raises(CrawlError) as exc_info:
            await _check_ssrf("http://reserved.example.com/")
        assert exc_info.value.kind == "ssrf"


@pytest.mark.asyncio
async def test_check_ssrf_no_results_raises():
    """If DNS returns only addresses that fail validation, raise CrawlError."""
    with patch("socket.getaddrinfo") as mock_gai:
        # All results are private
        mock_gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.1", 0))
        ]
        with pytest.raises(CrawlError) as exc_info:
            await _check_ssrf("http://private.internal/")
        assert exc_info.value.kind == "ssrf"


# ---------------------------------------------------------------------------
# _http_get_pinned — body parsing paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_get_pinned_parses_content_length_response():
    """Standard content-length response body is read and returned correctly."""
    body = b"Hello, world!"
    raw = _http_response(200, {"content-type": "text/plain"}, body)
    reader = _make_stream_reader(raw)
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        status, headers, got_body = await _http_get_pinned("http://example.com/", "1.2.3.4")

    assert status == 200
    assert got_body == body


@pytest.mark.asyncio
async def test_http_get_pinned_parses_chunked_response():
    """Chunked transfer-encoding body is reassembled correctly."""
    body = b"chunked body data"
    raw = _http_response(200, {"content-type": "text/plain"}, body, chunked=True)
    reader = _make_stream_reader(raw)
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        status, headers, got_body = await _http_get_pinned("http://example.com/", "1.2.3.4")

    assert status == 200
    assert got_body == body


@pytest.mark.asyncio
async def test_http_get_pinned_decompresses_gzip():
    """gzip content-encoding body is transparently decompressed."""
    original = b"uncompressed content for testing"
    compressed = gzip.compress(original)
    raw = _http_response(200, {"content-encoding": "gzip"}, compressed)
    reader = _make_stream_reader(raw)
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        status, headers, got_body = await _http_get_pinned("http://example.com/", "1.2.3.4")

    assert status == 200
    assert got_body == original


@pytest.mark.asyncio
async def test_http_get_pinned_connection_close_reads_until_eof():
    """Without content-length or chunked, body is read until server closes connection."""
    body = b"close-delimited body"
    # No content-length, no chunked — simulate connection-close
    raw = b"HTTP/1.1 200 OK\r\ncontent-type: text/plain\r\n\r\n" + body
    reader = _make_stream_reader(raw)
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        status, headers, got_body = await _http_get_pinned("http://example.com/", "1.2.3.4")

    assert status == 200
    assert got_body == body


@pytest.mark.asyncio
async def test_http_get_pinned_raises_on_connection_failure():
    """OSError from open_connection surfaces as CrawlError kind='network'."""
    with patch(
        "src.loop.harvest.crawler.asyncio.open_connection",
        side_effect=OSError("connection refused"),
    ):
        with pytest.raises(CrawlError) as exc_info:
            await _http_get_pinned("http://example.com/", "1.2.3.4")
    assert exc_info.value.kind == "network"


@pytest.mark.asyncio
async def test_http_get_pinned_raises_on_timeout():
    """asyncio.TimeoutError from open_connection surfaces as CrawlError kind='network'."""
    with patch(
        "src.loop.harvest.crawler.asyncio.open_connection",
        side_effect=asyncio.TimeoutError(),
    ):
        with pytest.raises(CrawlError) as exc_info:
            await _http_get_pinned("http://example.com/", "1.2.3.4")
    assert exc_info.value.kind == "network"


@pytest.mark.asyncio
async def test_http_get_pinned_raises_on_malformed_status_line():
    """A malformed HTTP status line raises CrawlError kind='network'."""
    raw = b"GARBAGE\r\ncontent-length: 0\r\n\r\n"
    reader = _make_stream_reader(raw)
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        with pytest.raises(CrawlError) as exc_info:
            await _http_get_pinned("http://example.com/", "1.2.3.4")
    assert exc_info.value.kind == "network"


@pytest.mark.asyncio
async def test_http_get_pinned_decompresses_deflate():
    """deflate (zlib) content-encoding body is transparently decompressed."""
    original = b"deflate content for testing"
    compressed = zlib.compress(original)
    raw = _http_response(200, {"content-encoding": "deflate"}, compressed)
    reader = _make_stream_reader(raw)
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        status, headers, got_body = await _http_get_pinned("http://example.com/", "1.2.3.4")

    assert status == 200
    assert got_body == original


@pytest.mark.asyncio
async def test_http_get_pinned_handles_https_path():
    """HTTPS URL triggers ssl_ctx creation; hostname used for SNI."""
    body = b"secure content"
    raw = _http_response(200, {"content-type": "text/plain"}, body)
    reader = _make_stream_reader(raw)
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)), \
         patch("src.loop.harvest.crawler.ssl.create_default_context", return_value=None):
        status, _headers, got_body = await _http_get_pinned("https://example.com/page", "1.2.3.4")

    assert status == 200
    assert got_body == body


# ---------------------------------------------------------------------------
# _get_robots_parser — TTL caching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_robots_parser_is_cached_within_ttl():
    """Second call for the same base URL within TTL hits cache, not network."""
    _robots_cache.clear()
    base = "http://cache-test.example.com"
    ok_response = (200, {}, b"User-agent: *\nDisallow:")

    with patch("src.loop.harvest.crawler._check_ssrf", new_callable=AsyncMock, return_value="1.2.3.4"), \
         patch("src.loop.harvest.crawler._http_get_pinned", new_callable=AsyncMock, return_value=ok_response) as mock_get:
        _ = await _get_robots_parser(base)
        _ = await _get_robots_parser(base)

    # Network only called once; second call served from cache
    assert mock_get.await_count == 1
    _robots_cache.clear()


@pytest.mark.asyncio
async def test_robots_parser_refetches_after_ttl_expires():
    """A stale cache entry (past TTL) triggers a fresh network fetch."""
    _robots_cache.clear()
    base = "http://ttl-test.example.com"
    ok_response = (200, {}, b"User-agent: *\nDisallow:")

    from unittest.mock import MagicMock as MM
    _robots_cache[base] = (time.monotonic() - _ROBOTS_TTL - 1, MM())  # stale

    with patch("src.loop.harvest.crawler._check_ssrf", new_callable=AsyncMock, return_value="1.2.3.4"), \
         patch("src.loop.harvest.crawler._http_get_pinned", new_callable=AsyncMock, return_value=ok_response) as mock_get:
        _ = await _get_robots_parser(base)

    assert mock_get.await_count == 1  # fresh fetch happened
    _robots_cache.clear()


@pytest.mark.asyncio
async def test_robots_parser_returns_permissive_on_fetch_failure():
    """If robots.txt fetch throws, the parser is permissive (allows all)."""
    _robots_cache.clear()
    base = "http://unreachable.example.com"

    with patch("src.loop.harvest.crawler._check_ssrf", new_callable=AsyncMock, side_effect=CrawlError("network", "down")):
        rp = await _get_robots_parser(base)

    # Empty RobotFileParser allows everything
    assert rp is not None
    assert rp.can_fetch(_VERUM_BOT_UA, f"{base}/any/path")
    _robots_cache.clear()


# ---------------------------------------------------------------------------
# _check_robots_allowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_robots_allowed_raises_when_disallowed():
    """A robots.txt Disallow for our UA raises CrawlError kind='robots'."""
    from urllib.robotparser import RobotFileParser
    rp = RobotFileParser()
    rp.parse(["User-agent: Verum-Bot", "Disallow: /private/"])

    with patch("src.loop.harvest.crawler._get_robots_parser", new_callable=AsyncMock, return_value=rp):
        with pytest.raises(CrawlError) as exc_info:
            await _check_robots_allowed("http://example.com/private/data")
    assert exc_info.value.kind == "robots"


@pytest.mark.asyncio
async def test_check_robots_allowed_permits_when_allowed():
    """A robots.txt Allow for our UA does not raise."""
    from urllib.robotparser import RobotFileParser
    rp = RobotFileParser()
    rp.parse(["User-agent: *", "Allow: /"])

    with patch("src.loop.harvest.crawler._get_robots_parser", new_callable=AsyncMock, return_value=rp):
        await _check_robots_allowed("http://example.com/public/page")  # must not raise


@pytest.mark.asyncio
async def test_check_robots_allowed_permits_when_parser_is_none():
    """If _get_robots_parser returns None, all URLs are allowed."""
    with patch("src.loop.harvest.crawler._get_robots_parser", new_callable=AsyncMock, return_value=None):
        await _check_robots_allowed("http://example.com/any/path")  # must not raise


# ---------------------------------------------------------------------------
# _check_ssrf — ValueError / empty-results edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_ssrf_skips_malformed_ip_and_uses_next_valid():
    """Addresses that fail ipaddress.ip_address() parsing are skipped silently."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("not-an-ip", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 0)),
        ]
        result = await _check_ssrf("http://example.com/")
    assert result == "8.8.8.8"


@pytest.mark.asyncio
async def test_check_ssrf_empty_results_raises_ssrf_error():
    """Empty getaddrinfo results raise CrawlError kind='ssrf'."""
    with patch("socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = []
        with pytest.raises(CrawlError) as exc_info:
            await _check_ssrf("http://example.com/")
    assert exc_info.value.kind == "ssrf"


# ---------------------------------------------------------------------------
# _http_get_pinned — query string, raw deflate, incomplete reads, size cap,
#                    response-phase exceptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_get_pinned_includes_query_string_in_request():
    """A URL with a query string appends it to the GET request path."""
    body = b"query result"
    raw = _http_response(200, {}, body)
    reader = _make_stream_reader(raw)
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        status, _, got_body = await _http_get_pinned(
            "http://example.com/search?q=test&page=1", "1.2.3.4"
        )

    assert status == 200
    assert got_body == body
    written = b"".join(call[0][0] for call in writer.write.call_args_list)
    assert b"/search?q=test&page=1" in written


@pytest.mark.asyncio
async def test_http_get_pinned_decompresses_raw_deflate():
    """Raw deflate (no zlib wrapper) falls through to -MAX_WBITS decompression."""
    import zlib as _zlib

    original = b"raw deflate test data"
    comp = _zlib.compressobj(wbits=-_zlib.MAX_WBITS)
    raw_deflate = comp.compress(original) + comp.flush()

    raw = _http_response(200, {"content-encoding": "deflate"}, raw_deflate)
    reader = _make_stream_reader(raw)
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        status, _, got_body = await _http_get_pinned("http://example.com/", "1.2.3.4")

    assert status == 200
    assert got_body == original


@pytest.mark.asyncio
async def test_http_get_pinned_chunked_handles_incomplete_read():
    """IncompleteReadError during a chunk read stores the partial bytes."""
    raw = (
        b"HTTP/1.1 200 OK\r\n"
        b"transfer-encoding: chunked\r\n"
        b"\r\n"
        b"64\r\n"   # chunk size 100
        b"hello"   # only 5 bytes before EOF
    )
    reader = asyncio.StreamReader()
    reader.feed_data(raw)
    reader.feed_eof()
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        status, _, got_body = await _http_get_pinned("http://example.com/", "1.2.3.4")

    assert status == 200
    assert b"hello" in got_body


@pytest.mark.asyncio
async def test_http_get_pinned_content_length_handles_incomplete_read():
    """IncompleteReadError when body is shorter than content-length stores partial bytes."""
    raw = (
        b"HTTP/1.1 200 OK\r\n"
        b"content-length: 100\r\n"
        b"\r\n"
        b"hello"   # only 5 bytes, content-length claims 100
    )
    reader = asyncio.StreamReader()
    reader.feed_data(raw)
    reader.feed_eof()
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        status, _, got_body = await _http_get_pinned("http://example.com/", "1.2.3.4")

    assert status == 200
    assert got_body == b"hello"


@pytest.mark.asyncio
async def test_http_get_pinned_chunked_size_cap_truncates_body():
    """Body is truncated when total bytes exceed _MAX_CONTENT_BYTES in chunked mode."""
    import src.loop.harvest.crawler as crawler_mod

    original = crawler_mod._MAX_CONTENT_BYTES
    crawler_mod._MAX_CONTENT_BYTES = 5
    try:
        body = b"0123456789"  # 10 bytes > 5-byte cap
        raw = _http_response(200, {}, body, chunked=True)
        reader = _make_stream_reader(raw)
        writer = _make_writer()
        with patch(
            "src.loop.harvest.crawler.asyncio.open_connection",
            _mock_open_connection(reader, writer),
        ):
            status, _, _ = await _http_get_pinned("http://example.com/", "1.2.3.4")
    finally:
        crawler_mod._MAX_CONTENT_BYTES = original

    assert status == 200


@pytest.mark.asyncio
async def test_http_get_pinned_connection_close_size_cap_truncates_body():
    """Body is truncated at _MAX_CONTENT_BYTES in connection-close (no header) mode."""
    import src.loop.harvest.crawler as crawler_mod

    original = crawler_mod._MAX_CONTENT_BYTES
    crawler_mod._MAX_CONTENT_BYTES = 5
    try:
        body = b"0123456789"  # 10 bytes > 5-byte cap
        raw = b"HTTP/1.1 200 OK\r\ncontent-type: text/plain\r\n\r\n" + body
        reader = _make_stream_reader(raw)
        writer = _make_writer()
        with patch(
            "src.loop.harvest.crawler.asyncio.open_connection",
            _mock_open_connection(reader, writer),
        ):
            status, _, _ = await _http_get_pinned("http://example.com/", "1.2.3.4")
    finally:
        crawler_mod._MAX_CONTENT_BYTES = original

    assert status == 200


@pytest.mark.asyncio
async def test_http_get_pinned_response_oserror_raises_crawl_error():
    """OSError during writer.drain() surfaces as CrawlError kind='network'."""
    body = b"ignored"
    raw = _http_response(200, {}, body)
    reader = _make_stream_reader(raw)
    writer = _make_writer()
    writer.drain = AsyncMock(side_effect=OSError("connection reset by peer"))

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        with pytest.raises(CrawlError) as exc_info:
            await _http_get_pinned("http://example.com/", "1.2.3.4")

    assert exc_info.value.kind == "network"


@pytest.mark.asyncio
async def test_http_get_pinned_response_read_timeout_raises_crawl_error():
    """asyncio.TimeoutError raised during response reading surfaces as CrawlError kind='timeout'."""
    from unittest.mock import MagicMock as MM

    reader = MM()
    reader.readline = AsyncMock(side_effect=asyncio.TimeoutError())
    writer = _make_writer()

    with patch("src.loop.harvest.crawler.asyncio.open_connection", _mock_open_connection(reader, writer)):
        with pytest.raises(CrawlError) as exc_info:
            await _http_get_pinned("http://example.com/", "1.2.3.4")

    assert exc_info.value.kind == "timeout"
