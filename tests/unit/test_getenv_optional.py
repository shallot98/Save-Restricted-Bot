"""
Unit tests for getenv_optional helper.
"""

from __future__ import annotations

import pytest

from src.compat.config_compat import getenv_optional


class TestGetenvOptional:
    def test_returns_none_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("STRING", raising=False)
        assert getenv_optional("STRING", {}) is None

    def test_returns_none_when_blank_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("STRING", "   ")
        assert getenv_optional("STRING", {}) is None

    def test_prefers_config_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("STRING", "env_value")
        assert getenv_optional("STRING", {"STRING": " config_value "}) == "config_value"

    def test_strips_env_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("STRING", "  abc  ")
        assert getenv_optional("STRING", {}) == "abc"
