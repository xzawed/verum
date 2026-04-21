from __future__ import annotations

import asyncio
import os
import re
import shutil
import stat
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from uuid import UUID

_GITHUB_URL_RE = re.compile(r"^https://github\.com/[\w.\-]+/[\w.\-]+(\.git)?$")
_CLONE_BASE = Path(tempfile.gettempdir()) / "verum-clones"

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


def _classify_error(stderr: str) -> tuple[str, str]:
    lower = stderr.lower()
    for pattern, kind in _CLONE_ERRORS.items():
        if pattern in lower:
            return kind, stderr.strip()
    return "unknown", stderr.strip()


async def clone_repo(
    repo_url: str,
    analysis_id: UUID,
    *,
    branch: str = "main",
    depth: int = 1,
) -> Path:
    """Shallow-clone a public GitHub repo to /tmp/verum-clones/{analysis_id}/.

    Only GitHub HTTPS URLs are accepted. The caller must delete the clone when
    finished — use cloned_repo() context manager for automatic cleanup.

    Raises:
        ValueError: repo_url fails validation.
        RepoCloneError: clone fails (auth, not found, network, branch mismatch).
    """
    if not _GITHUB_URL_RE.match(repo_url):
        raise ValueError(f"Invalid GitHub URL: {repo_url!r}")

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

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr_bytes = await proc.communicate()

    if proc.returncode != 0:
        stderr = stderr_bytes.decode(errors="replace")
        kind, detail = _classify_error(stderr)
        if target.exists():
            _rmtree(target)
        raise RepoCloneError(kind, detail)

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
