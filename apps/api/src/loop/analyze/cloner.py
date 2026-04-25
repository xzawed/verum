from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import stat
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from uuid import UUID

logger = logging.getLogger(__name__)

_GITHUB_URL_RE = re.compile(r"^https://github\.com/[\w.\-]+/[\w.\-]+(\.git)?$")
_BRANCH_RE = re.compile(r"^[a-zA-Z0-9._/\-]{1,200}$")
_CLONE_BASE = Path(tempfile.gettempdir()) / "verum-clones"

# Hard limits — tunable via env vars without a code change.
_CLONE_TIMEOUT_SECONDS = int(os.environ.get("VERUM_CLONE_TIMEOUT", "120"))
_CLONE_MAX_DISK_MB = int(os.environ.get("VERUM_CLONE_MAX_DISK_MB", "512"))
_MIN_FREE_DISK_MB = int(os.environ.get("VERUM_MIN_FREE_DISK_MB", "1024"))

_CLONE_ERRORS = {
    "not found": "not_found",
    "repository not found": "not_found",
    "could not read username": "auth",
    "authentication failed": "auth",
    "could not resolve host": "network",
    "error: pathspec": "branch_missing",
}


def _rmtree(path: Path) -> None:
    """Remove a directory tree, handling Windows read-only files in .git."""
    def _on_error(func, fpath, exc_info):  # noqa: ANN001
        os.chmod(fpath, stat.S_IWRITE)
        func(fpath)

    shutil.rmtree(path, onerror=_on_error)


class RepoCloneError(Exception):
    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind  # "not_found" | "auth" | "network" | "branch_missing" | "unknown"


class CloneQuotaError(Exception):
    """Raised when a clone would exceed disk quota or free-space threshold."""


def _classify_error(stderr: str) -> tuple[str, str]:
    lower = stderr.lower()
    for pattern, kind in _CLONE_ERRORS.items():
        if pattern in lower:
            return kind, stderr.strip()
    return "unknown", stderr.strip()


def _validate_url(repo_url: str) -> None:
    """Enforce that repo_url is a github.com HTTPS URL.

    VERUM_ALLOW_INSECURE_CLONE_HOSTS is only honoured when VERUM_TEST_MODE=1.
    Setting it in production has no effect, preventing accidental SSRF exposure.
    """
    if _GITHUB_URL_RE.match(repo_url):
        return

    test_mode = os.environ.get("VERUM_TEST_MODE") == "1"
    allowed = os.environ.get("VERUM_ALLOW_INSECURE_CLONE_HOSTS", "")

    if not (test_mode and allowed):
        raise ValueError(
            f"Invalid GitHub URL: {repo_url!r}. "
            "Only https://github.com/<owner>/<repo> URLs are permitted. "
            "VERUM_ALLOW_INSECURE_CLONE_HOSTS is only active when VERUM_TEST_MODE=1."
        )

    from urllib.parse import urlparse
    parsed = urlparse(repo_url)
    scheme = parsed.scheme
    host = parsed.hostname or ""
    if scheme not in {"http", "https"}:
        raise ValueError(
            f"Invalid URL scheme {scheme!r} in {repo_url!r}: only http/https are allowed"
        )
    allowed_hosts = [h.strip() for h in allowed.split(",")]
    if host not in allowed_hosts:
        raise ValueError(
            f"Host {host!r} is not in VERUM_ALLOW_INSECURE_CLONE_HOSTS; "
            f"allowed: {allowed_hosts}"
        )


def _check_disk_quota() -> None:
    """Raise CloneQuotaError if the filesystem is too full to accept a new clone."""
    _CLONE_BASE.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(_CLONE_BASE)
    free_mb = usage.free // (1024 * 1024)
    if free_mb < _MIN_FREE_DISK_MB:
        raise CloneQuotaError(
            f"Insufficient disk space: {free_mb} MB free, "
            f"need at least {_MIN_FREE_DISK_MB} MB before cloning."
        )


def _get_dir_size_mb(path: Path) -> int:
    """Return approximate directory size in MB (best-effort)."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        pass
    return total // (1024 * 1024)


async def clone_repo(
    repo_url: str,
    analysis_id: UUID,
    *,
    branch: str = "main",
    depth: int = 1,
) -> Path:
    """Shallow-clone a public GitHub repo to /tmp/verum-clones/{analysis_id}/.

    Security controls:
    - URL must match github.com HTTPS regex (ALLOW_INSECURE only in TEST_MODE=1)
    - Branch name validated against safe character set
    - Free disk space checked before clone starts (VERUM_MIN_FREE_DISK_MB, default 1 GB)
    - Process killed if clone exceeds VERUM_CLONE_TIMEOUT seconds (default 120 s)
    - Directory deleted if post-clone size exceeds VERUM_CLONE_MAX_DISK_MB (default 512 MB)
    - All clone events emitted as structured [AUDIT] log lines

    Raises:
        ValueError: URL or branch fails validation.
        CloneQuotaError: Disk quota or free-space threshold exceeded.
        RepoCloneError: git clone process failed.
        asyncio.TimeoutError: Clone exceeded the configured timeout.
    """
    _validate_url(repo_url)

    if not _BRANCH_RE.match(branch):
        raise ValueError(
            f"Invalid branch name {branch!r}: must match ^[a-zA-Z0-9._/\\-]{{1,200}}$"
        )

    _check_disk_quota()

    target = _CLONE_BASE / str(analysis_id)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        _rmtree(target)

    cmd = [
        "git", "clone",
        "--depth", str(depth),
        "--branch", branch,
        "--single-branch",
        repo_url,
        str(target),
    ]

    logger.info(
        "[AUDIT] clone_start repo_url=%r analysis_id=%s branch=%r",
        repo_url, analysis_id, branch,
    )
    t0 = time.monotonic()

    try:
        proc = await asyncio.create_subprocess_exec(  # NOSONAR — cmd is validated by _validate_url + branch regex
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(_CLONE_TIMEOUT_SECONDS),
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            if target.exists():
                _rmtree(target)
            logger.warning(
                "[AUDIT] clone_timeout repo_url=%r analysis_id=%s timeout=%ds",
                repo_url, analysis_id, _CLONE_TIMEOUT_SECONDS,
            )
            raise asyncio.TimeoutError(
                f"git clone of {repo_url!r} exceeded {_CLONE_TIMEOUT_SECONDS}s timeout"
            )
    except asyncio.TimeoutError:
        raise
    except Exception:
        if target.exists():
            _rmtree(target)
        raise

    elapsed = time.monotonic() - t0

    if proc.returncode != 0:
        stderr = stderr_bytes.decode(errors="replace")
        kind, detail = _classify_error(stderr)
        if target.exists():
            _rmtree(target)
        logger.warning(
            "[AUDIT] clone_failed repo_url=%r analysis_id=%s kind=%s elapsed=%.1fs",
            repo_url, analysis_id, kind, elapsed,
        )
        raise RepoCloneError(kind, detail)

    size_mb = _get_dir_size_mb(target)
    if size_mb > _CLONE_MAX_DISK_MB:
        _rmtree(target)
        logger.warning(
            "[AUDIT] clone_oversized repo_url=%r analysis_id=%s size_mb=%d limit_mb=%d",
            repo_url, analysis_id, size_mb, _CLONE_MAX_DISK_MB,
        )
        raise CloneQuotaError(
            f"Clone of {repo_url!r} is {size_mb} MB, exceeding the "
            f"{_CLONE_MAX_DISK_MB} MB limit."
        )

    logger.info(
        "[AUDIT] clone_success repo_url=%r analysis_id=%s size_mb=%d elapsed=%.1fs",
        repo_url, analysis_id, size_mb, elapsed,
    )
    return target


@asynccontextmanager
async def cloned_repo(
    repo_url: str,
    analysis_id: UUID,
    *,
    branch: str = "main",
) -> AsyncIterator[Path]:
    """Context manager that clones a repo and deletes it on exit."""
    path = await clone_repo(repo_url, analysis_id, branch=branch)
    try:
        yield path
    finally:
        if path.exists():
            _rmtree(path)
