"""
Unit tests for JSONWatchRepository Settings backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from src.domain.entities.watch import WatchConfig
from src.infrastructure.persistence.repositories import watch_repository as watch_repository_module
from src.infrastructure.persistence.repositories.watch_repository import JSONWatchRepository


@dataclass
class FakePaths:
    watch_file: Path


class FakeSettings:
    def __init__(self, watch_file: Path, initial: Optional[Dict[str, Any]] = None) -> None:
        self.paths = FakePaths(watch_file=watch_file)
        self._watch_config: Dict[str, Any] = initial or {}
        self._rev = 0
        self.save_calls = 0

    @property
    def watch_config(self) -> Dict[str, Any]:
        return self._watch_config.copy()

    @property
    def watch_config_revision(self) -> int:
        return self._rev

    def save_watch_config(self, config: Dict[str, Any], auto_reload: bool = True) -> None:
        self._watch_config = config.copy()
        self._rev += 1
        self.save_calls += 1

    def reload_watch_config(self) -> Dict[str, Any]:
        self._rev += 1
        return self._watch_config.copy()


class TestJSONWatchRepositorySettingsBackend:
    def test_syncs_when_settings_revision_changes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_settings = FakeSettings(
            tmp_path / "watch_config.json",
            initial={
                "1": {"-100|123": {"source": "-100", "dest": "123", "record_mode": False}}
            },
        )
        monkeypatch.setattr(watch_repository_module, "settings", fake_settings)

        repo = JSONWatchRepository()
        keys1 = {watch_key for _, watch_key, _ in repo.get_tasks_for_source("-100")}
        assert keys1 == {"-100|123"}

        fake_settings.save_watch_config(
            {
                "1": {
                    "-100|123": {"source": "-100", "dest": "123", "record_mode": False},
                    "-100|record": {"source": "-100", "dest": None, "record_mode": True},
                }
            }
        )

        keys2 = {watch_key for _, watch_key, _ in repo.get_tasks_for_source("-100")}
        assert keys2 == {"-100|123", "-100|record"}

    def test_save_user_config_persists_through_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_settings = FakeSettings(tmp_path / "watch_config.json", initial={})
        monkeypatch.setattr(watch_repository_module, "settings", fake_settings)

        repo = JSONWatchRepository()
        config = WatchConfig.from_dict(
            "1",
            {"-100|123": {"source": "-100", "dest": "123", "record_mode": False}},
        )
        repo.save_user_config(config)

        assert fake_settings.watch_config_revision == 1
        assert "1" in fake_settings.watch_config
        assert "-100|123" in fake_settings.watch_config["1"]

    def test_save_config_dict_persists_once_through_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_settings = FakeSettings(tmp_path / "watch_config.json", initial={})
        monkeypatch.setattr(watch_repository_module, "settings", fake_settings)

        repo = JSONWatchRepository()
        repo.save_config_dict(
            {
                "1": {"-100|123": {"source": "-100", "dest": "123", "record_mode": False}},
                "2": {"-200|me": {"source": "-200", "dest": "me", "record_mode": False}},
            }
        )

        assert fake_settings.save_calls == 1
        assert fake_settings.watch_config_revision == 1
        assert "1" in fake_settings.watch_config
        assert "2" in fake_settings.watch_config
