"""Unit tests for loop/analyze/cloner.py — URL validation, branch regex, error classification."""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.loop.analyze.cloner import (
    RepoCloneError,
    _BRANCH_RE,
    _GITHUB_URL_RE,
    _classify_error,
    clone_repo,
    cloned_repo,
)


# ---------------------------------------------------------------------------
# Regex validation
# ---------------------------------------------------------------------------


def test_github_url_regex_accepts_valid_url():
    assert _GITHUB_URL_RE.match("https://github.com/owner/repo")


def test_github_url_regex_accepts_dot_git_suffix():
    assert _GITHUB_URL_RE.match("https://github.com/owner/repo.git")


def test_github_url_regex_rejects_non_github():
    assert not _GITHUB_URL_RE.match("https://gitlab.com/owner/repo")


def test_github_url_regex_rejects_http():
    assert not _GITHUB_URL_RE.match("http://github.com/owner/repo")


def test_branch_re_accepts_normal_branch():
    assert _BRANCH_RE.match("main")
    assert _BRANCH_RE.match("feature/some-branch")
    assert _BRANCH_RE.match("release-1.2.3")


def test_branch_re_rejects_empty():
    assert not _BRANCH_RE.match("")


def test_branch_re_rejects_too_long():
    assert not _BRANCH_RE.match("a" * 201)


def test_branch_re_rejects_special_chars():
    assert not _BRANCH_RE.match("branch with spaces")
    assert not _BRANCH_RE.match("branch@special")


# ---------------------------------------------------------------------------
# _classify_error
# ---------------------------------------------------------------------------


def test_classify_error_not_found():
    kind, detail = _classify_error("remote: Repository not found.")
    assert kind == "not_found"


def test_classify_error_auth():
    kind, _ = _classify_error("fatal: could not read Username for 'https://github.com'")
    assert kind == "auth"


def test_classify_error_authentication_failed():
    kind, _ = _classify_error("fatal: Authentication failed for 'https://github.com/x/y'")
    assert kind == "auth"


def test_classify_error_network():
    kind, _ = _classify_error("fatal: unable to access '...': could not resolve host: github.com")
    assert kind == "network"


def test_classify_error_branch_missing():
    kind, _ = _classify_error("error: pathspec 'nonexistent' did not match any file(s) known to git")
    assert kind == "branch_missing"


def test_classify_error_unknown():
    kind, _ = _classify_error("some totally unknown error message")
    assert kind == "unknown"


def test_classify_error_strips_whitespace():
    _, detail = _classify_error("  some error  ")
    assert detail == "some error"


# ---------------------------------------------------------------------------
# RepoCloneError
# ---------------------------------------------------------------------------


def test_repo_clone_error_stores_kind():
    err = RepoCloneError("not_found", "repo not found")
    assert err.kind == "not_found"
    assert "repo not found" in str(err)


# ---------------------------------------------------------------------------
# clone_repo — validation (no subprocess needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clone_repo_rejects_non_github_url():
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        await clone_repo("https://gitlab.com/owner/repo", uuid.uuid4())


@pytest.mark.asyncio
async def test_clone_repo_rejects_invalid_branch():
    with pytest.raises(ValueError, match="Invalid branch name"):
        await clone_repo("https://github.com/owner/repo", uuid.uuid4(), branch="bad branch!")


# ---------------------------------------------------------------------------
# clone_repo — subprocess success
# ---------------------------------------------------------------------------


def _make_mock_proc(returncode: int = 0, stderr: bytes = b"") -> MagicMock:
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", stderr))
    return proc


@pytest.mark.asyncio
async def test_clone_repo_success_returns_path():
    analysis_id = uuid.uuid4()
    mock_proc = _make_mock_proc(returncode=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        with patch("pathlib.Path.exists", return_value=False):
            with patch("pathlib.Path.mkdir"):
                result = await clone_repo("https://github.com/owner/repo", analysis_id)

    mock_exec.assert_awaited_once()
    assert str(analysis_id) in str(result)


@pytest.mark.asyncio
async def test_clone_repo_raises_on_nonzero_exit():
    mock_proc = _make_mock_proc(returncode=128, stderr=b"remote: Repository not found.")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("pathlib.Path.exists", return_value=False):
            with patch("pathlib.Path.mkdir"):
                with pytest.raises(RepoCloneError) as exc_info:
                    await clone_repo("https://github.com/owner/repo", uuid.uuid4())

    assert exc_info.value.kind == "not_found"


@pytest.mark.asyncio
async def test_clone_repo_cleans_up_target_on_failure():
    mock_proc = _make_mock_proc(returncode=128, stderr=b"fatal: Authentication failed")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("pathlib.Path.mkdir"):
            with patch("pathlib.Path.exists", return_value=True) as mock_exists:
                with patch("src.loop.analyze.cloner._rmtree") as mock_rmtree:
                    # First call returns False (before clone), second returns True (after failed clone)
                    mock_exists.side_effect = [False, True]
                    with pytest.raises(RepoCloneError):
                        await clone_repo("https://github.com/owner/repo", uuid.uuid4())
                    mock_rmtree.assert_called_once()


# ---------------------------------------------------------------------------
# cloned_repo context manager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cloned_repo_cleans_up_on_exit():
    analysis_id = uuid.uuid4()
    fake_path = Path(f"/tmp/verum-clones/{analysis_id}")

    with patch("src.loop.analyze.cloner.clone_repo", return_value=fake_path) as mock_clone:
        with patch("pathlib.Path.exists", return_value=True):
            with patch("src.loop.analyze.cloner._rmtree") as mock_rmtree:
                async with cloned_repo("https://github.com/owner/repo", analysis_id) as path:
                    assert path == fake_path
                mock_rmtree.assert_called_once_with(fake_path)


@pytest.mark.asyncio
async def test_cloned_repo_cleans_up_even_after_exception():
    analysis_id = uuid.uuid4()
    fake_path = Path(f"/tmp/verum-clones/{analysis_id}")

    with patch("src.loop.analyze.cloner.clone_repo", return_value=fake_path):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("src.loop.analyze.cloner._rmtree") as mock_rmtree:
                with pytest.raises(RuntimeError):
                    async with cloned_repo("https://github.com/owner/repo", analysis_id):
                        raise RuntimeError("analysis failed")
                mock_rmtree.assert_called_once()
