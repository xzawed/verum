"""Unit tests for loop/analyze/cloner.py — URL validation, branch regex, error classification."""
from __future__ import annotations

import asyncio
from collections import namedtuple
from contextlib import contextmanager
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.loop.analyze.cloner import (
    CloneQuotaError,
    RepoCloneError,
    _BRANCH_RE,
    _GITHUB_URL_RE,
    _classify_error,
    clone_repo,
    cloned_repo,
)


# ---------------------------------------------------------------------------
# Disk-quota mock helper
# ---------------------------------------------------------------------------

_FakeUsage = namedtuple("_FakeUsage", ["total", "used", "free"])


@contextmanager
def _mock_disk_quota(free_mb: int = 8192):
    """Patch shutil.disk_usage so _check_disk_quota() doesn't hit a real /tmp path."""
    with patch(
        "src.loop.analyze.cloner.shutil.disk_usage",
        return_value=_FakeUsage(total=0, used=0, free=free_mb * 1024 * 1024),
    ):
        yield


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

    with _mock_disk_quota():
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            with patch("pathlib.Path.exists", return_value=False):
                with patch("pathlib.Path.mkdir"):
                    result = await clone_repo("https://github.com/owner/repo", analysis_id)

    mock_exec.assert_awaited_once()
    assert str(analysis_id) in str(result)


@pytest.mark.asyncio
async def test_clone_repo_raises_on_nonzero_exit():
    mock_proc = _make_mock_proc(returncode=128, stderr=b"remote: Repository not found.")

    with _mock_disk_quota():
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("pathlib.Path.exists", return_value=False):
                with patch("pathlib.Path.mkdir"):
                    with pytest.raises(RepoCloneError) as exc_info:
                        await clone_repo("https://github.com/owner/repo", uuid.uuid4())

    assert exc_info.value.kind == "not_found"


@pytest.mark.asyncio
async def test_clone_repo_cleans_up_target_on_failure():
    mock_proc = _make_mock_proc(returncode=128, stderr=b"fatal: Authentication failed")

    with _mock_disk_quota():
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


# ---------------------------------------------------------------------------
# _check_disk_quota — direct coverage of security additions
# ---------------------------------------------------------------------------


def test_check_disk_quota_passes_when_free_above_threshold():
    from src.loop.analyze.cloner import _check_disk_quota
    with _mock_disk_quota(free_mb=8192):
        with patch("pathlib.Path.mkdir"):
            _check_disk_quota()  # must not raise


def test_check_disk_quota_raises_when_free_below_threshold():
    from src.loop.analyze.cloner import _check_disk_quota
    with _mock_disk_quota(free_mb=10):  # 10 MB < MIN_FREE_DISK_MB default (1024)
        with patch("pathlib.Path.mkdir"):
            with pytest.raises(CloneQuotaError, match="Insufficient disk space"):
                _check_disk_quota()


# ---------------------------------------------------------------------------
# _get_dir_size_mb
# ---------------------------------------------------------------------------


def test_get_dir_size_mb_sums_files(tmp_path):
    from src.loop.analyze.cloner import _get_dir_size_mb
    (tmp_path / "a.bin").write_bytes(b"x" * 512 * 1024)  # 0.5 MB
    (tmp_path / "b.bin").write_bytes(b"x" * 512 * 1024)  # 0.5 MB
    assert _get_dir_size_mb(tmp_path) == 1


def test_get_dir_size_mb_returns_zero_on_oserror(tmp_path):
    from src.loop.analyze.cloner import _get_dir_size_mb
    with patch.object(Path, "rglob", side_effect=OSError("no access")):
        assert _get_dir_size_mb(tmp_path) == 0


# ---------------------------------------------------------------------------
# _validate_url — TEST_MODE branches (security additions)
# ---------------------------------------------------------------------------


def test_validate_url_test_mode_allows_listed_host(monkeypatch):
    from src.loop.analyze.cloner import _validate_url
    monkeypatch.setenv("VERUM_TEST_MODE", "1")
    monkeypatch.setenv("VERUM_ALLOW_INSECURE_CLONE_HOSTS", "localhost")
    _validate_url("https://localhost/owner/repo")  # must not raise


def test_validate_url_non_test_mode_rejects_non_github(monkeypatch):
    from src.loop.analyze.cloner import _validate_url
    monkeypatch.delenv("VERUM_TEST_MODE", raising=False)
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        _validate_url("https://gitlab.com/owner/repo")


def test_validate_url_test_mode_rejects_unknown_host(monkeypatch):
    from src.loop.analyze.cloner import _validate_url
    monkeypatch.setenv("VERUM_TEST_MODE", "1")
    monkeypatch.setenv("VERUM_ALLOW_INSECURE_CLONE_HOSTS", "allowed.example.com")
    with pytest.raises(ValueError, match="not in VERUM_ALLOW_INSECURE_CLONE_HOSTS"):
        _validate_url("https://notallowed.example.com/owner/repo")


def test_validate_url_test_mode_rejects_non_http_scheme(monkeypatch):
    from src.loop.analyze.cloner import _validate_url
    monkeypatch.setenv("VERUM_TEST_MODE", "1")
    monkeypatch.setenv("VERUM_ALLOW_INSECURE_CLONE_HOSTS", "internal.host")
    with pytest.raises(ValueError, match="only http/https are allowed"):
        _validate_url("git://internal.host/repo.git")


# ---------------------------------------------------------------------------
# clone_repo — timeout + oversized-clone branches (security additions)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clone_repo_timeout_kills_proc_and_raises():
    mock_proc = AsyncMock()
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock()

    with _mock_disk_quota():
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("pathlib.Path.exists", return_value=False):
                with patch("pathlib.Path.mkdir"):
                    with patch(
                        "src.loop.analyze.cloner.asyncio.wait_for",
                        side_effect=asyncio.TimeoutError(),
                    ):
                        with pytest.raises(asyncio.TimeoutError):
                            await clone_repo("https://github.com/owner/repo", uuid.uuid4())

    mock_proc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_clone_repo_oversized_clone_raises_quota_error():
    mock_proc = _make_mock_proc(returncode=0)

    with _mock_disk_quota():
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("pathlib.Path.exists", return_value=False):
                with patch("pathlib.Path.mkdir"):
                    with patch("src.loop.analyze.cloner._get_dir_size_mb", return_value=9999):
                        with patch("src.loop.analyze.cloner._rmtree"):
                            with pytest.raises(CloneQuotaError, match="exceeding the"):
                                await clone_repo("https://github.com/owner/repo", uuid.uuid4())


# ---------------------------------------------------------------------------
# _rmtree — direct coverage (lines 39-43) and onerror callback (lines 40-41)
# ---------------------------------------------------------------------------


def test_rmtree_calls_shutil_rmtree(tmp_path):
    """Calling _rmtree on a real path removes it — covers def _on_error and shutil.rmtree call."""
    from src.loop.analyze.cloner import _rmtree
    (tmp_path / "file.txt").write_text("test content")
    assert tmp_path.exists()
    _rmtree(tmp_path)
    assert not tmp_path.exists()


def test_rmtree_onerror_callback_chmod_and_retry(tmp_path):
    """When shutil.rmtree calls onerror, the callback calls os.chmod then retries func."""
    import sys
    from src.loop.analyze.cloner import _rmtree

    chmod_calls: list = []
    retry_calls: list = []

    def fake_rmtree(path, onerror=None, **kwargs):
        if onerror is not None:
            def retry_fn(p: str) -> None:
                retry_calls.append(p)
            onerror(retry_fn, str(tmp_path / "locked.file"), (None, None, None))

    with patch("src.loop.analyze.cloner.shutil.rmtree", side_effect=fake_rmtree):
        with patch("src.loop.analyze.cloner.os.chmod", side_effect=lambda p, m: chmod_calls.append(p)):
            _rmtree(tmp_path)

    assert len(chmod_calls) == 1
    assert len(retry_calls) == 1


# ---------------------------------------------------------------------------
# clone_repo — pre-existing target cleanup (line 159) and exception cleanup (201-204)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clone_repo_timeout_cleanup_when_target_exists():
    """On TimeoutError with existing target, _rmtree is called before re-raising (line 191)."""
    mock_proc = AsyncMock()
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock()

    with _mock_disk_quota():
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("pathlib.Path.mkdir"):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("src.loop.analyze.cloner._rmtree") as mock_rmtree:
                        with patch(
                            "src.loop.analyze.cloner.asyncio.wait_for",
                            side_effect=asyncio.TimeoutError(),
                        ):
                            with pytest.raises(asyncio.TimeoutError):
                                await clone_repo("https://github.com/owner/repo", uuid.uuid4())

    mock_rmtree.assert_called()


@pytest.mark.asyncio
async def test_clone_repo_general_exception_cleanup():
    """OSError from create_subprocess_exec → except Exception catches it, cleans up, re-raises."""
    with _mock_disk_quota():
        with patch("asyncio.create_subprocess_exec", side_effect=OSError("exec failed")):
            with patch("pathlib.Path.mkdir"):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("src.loop.analyze.cloner._rmtree") as mock_rmtree:
                        with pytest.raises(OSError, match="exec failed"):
                            await clone_repo("https://github.com/owner/repo", uuid.uuid4())

    # _rmtree called at line 159 (pre-existing target) and line 203 (exception cleanup)
    assert mock_rmtree.call_count == 2
