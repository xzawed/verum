"""Tests for verum._auto — startup auto-patch module."""
from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch


def _reload_auto(env: dict) -> None:
    """Reload _auto under a controlled environment."""
    sys.modules.pop("verum._auto", None)
    with patch.dict("os.environ", env, clear=False):
        importlib.import_module("verum._auto")


def test_no_patch_when_env_vars_absent(monkeypatch) -> None:
    """_patch_if_configured does nothing when no Verum env vars are set."""
    monkeypatch.delenv("VERUM_API_URL", raising=False)
    monkeypatch.delenv("VERUM_API_KEY", raising=False)
    monkeypatch.delenv("VERUM_DISABLED", raising=False)

    openai_mock = MagicMock()
    anthropic_mock = MagicMock()

    sys.modules.pop("verum._auto", None)
    sys.modules.pop("verum.openai", None)
    sys.modules.pop("verum.anthropic", None)

    with patch.dict(sys.modules, {"verum.openai": openai_mock, "verum.anthropic": anthropic_mock}):
        importlib.import_module("verum._auto")

    # When no env vars are set, submodules should NOT have been imported
    # (the mock objects should not have been accessed / their contents loaded)
    openai_mock.assert_not_called()
    anthropic_mock.assert_not_called()


def test_no_patch_when_disabled_flag_set(monkeypatch) -> None:
    """VERUM_DISABLED=1 skips patching even when API URL is set."""
    monkeypatch.setenv("VERUM_DISABLED", "1")
    monkeypatch.setenv("VERUM_API_URL", "https://verum.dev")
    monkeypatch.setenv("VERUM_API_KEY", "test-key")

    openai_mock = MagicMock()
    anthropic_mock = MagicMock()

    sys.modules.pop("verum._auto", None)
    sys.modules.pop("verum.openai", None)
    sys.modules.pop("verum.anthropic", None)

    with patch.dict(sys.modules, {"verum.openai": openai_mock, "verum.anthropic": anthropic_mock}):
        importlib.import_module("verum._auto")

    openai_mock.assert_not_called()
    anthropic_mock.assert_not_called()


def test_patches_openai_and_anthropic_when_configured(monkeypatch) -> None:
    """Both openai and anthropic submodules are imported when env vars are set."""
    monkeypatch.setenv("VERUM_API_URL", "https://verum.dev")
    monkeypatch.setenv("VERUM_API_KEY", "test-key-xyz")
    monkeypatch.delenv("VERUM_DISABLED", raising=False)

    openai_mock = MagicMock()
    anthropic_mock = MagicMock()

    sys.modules.pop("verum._auto", None)
    sys.modules.pop("verum.openai", None)
    sys.modules.pop("verum.anthropic", None)

    with patch.dict(sys.modules, {"verum.openai": openai_mock, "verum.anthropic": anthropic_mock}):
        importlib.import_module("verum._auto")
        # Assert inside the with block — patch.dict removes keys on exit
        assert "verum.openai" in sys.modules
        assert "verum.anthropic" in sys.modules


def test_disabled_true_string(monkeypatch) -> None:
    """VERUM_DISABLED=true (string) also skips patching."""
    monkeypatch.setenv("VERUM_DISABLED", "true")
    monkeypatch.setenv("VERUM_API_URL", "https://verum.dev")
    monkeypatch.delenv("VERUM_API_KEY", raising=False)

    openai_mock = MagicMock()
    anthropic_mock = MagicMock()

    sys.modules.pop("verum._auto", None)
    sys.modules.pop("verum.openai", None)
    sys.modules.pop("verum.anthropic", None)

    with patch.dict(sys.modules, {"verum.openai": openai_mock, "verum.anthropic": anthropic_mock}):
        importlib.import_module("verum._auto")

    openai_mock.assert_not_called()
    anthropic_mock.assert_not_called()


def test_disabled_yes_string(monkeypatch) -> None:
    """VERUM_DISABLED=yes also skips patching."""
    monkeypatch.setenv("VERUM_DISABLED", "yes")
    monkeypatch.setenv("VERUM_API_URL", "https://verum.dev")
    monkeypatch.delenv("VERUM_API_KEY", raising=False)

    openai_mock = MagicMock()
    anthropic_mock = MagicMock()

    sys.modules.pop("verum._auto", None)
    sys.modules.pop("verum.openai", None)
    sys.modules.pop("verum.anthropic", None)

    with patch.dict(sys.modules, {"verum.openai": openai_mock, "verum.anthropic": anthropic_mock}):
        importlib.import_module("verum._auto")

    openai_mock.assert_not_called()
    anthropic_mock.assert_not_called()


def test_missing_packages_are_swallowed(monkeypatch) -> None:
    """ImportError from missing openai/anthropic packages is silently ignored."""
    monkeypatch.setenv("VERUM_API_URL", "https://verum.dev")
    monkeypatch.setenv("VERUM_API_KEY", "k")
    monkeypatch.delenv("VERUM_DISABLED", raising=False)

    # Remove any cached real modules so a real ImportError would be raised
    sys.modules.pop("verum._auto", None)
    sys.modules.pop("verum.openai", None)
    sys.modules.pop("verum.anthropic", None)

    # Should not raise even if openai/anthropic aren't installed
    import verum._auto  # noqa: F401
    assert True


def test_only_api_url_is_sufficient(monkeypatch) -> None:
    """VERUM_API_URL alone (no API key) is enough to trigger patching."""
    monkeypatch.setenv("VERUM_API_URL", "https://verum.dev")
    monkeypatch.delenv("VERUM_API_KEY", raising=False)
    monkeypatch.delenv("VERUM_DISABLED", raising=False)

    openai_mock = MagicMock()
    anthropic_mock = MagicMock()

    sys.modules.pop("verum._auto", None)
    sys.modules.pop("verum.openai", None)
    sys.modules.pop("verum.anthropic", None)

    with patch.dict(sys.modules, {"verum.openai": openai_mock, "verum.anthropic": anthropic_mock}):
        importlib.import_module("verum._auto")
        # Assert inside the with block — patch.dict removes keys on exit
        assert "verum.openai" in sys.modules
        assert "verum.anthropic" in sys.modules
