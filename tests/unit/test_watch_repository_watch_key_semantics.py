"""
Unit tests for JSONWatchRepository watch key semantics.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.domain.entities.watch import WatchTask
from src.infrastructure.persistence.repositories.watch_repository import JSONWatchRepository


class TestJSONWatchRepositoryWatchKeySemantics:
    def test_add_task_canonicalizes_source_key_to_composite(self, tmp_path: Path) -> None:
        repo = JSONWatchRepository(config_path=tmp_path / "watch_config.json")
        repo.add_task("1", "-100", WatchTask(source="-100", dest="123"))

        config = repo.get_user_config("1")
        assert config is not None
        assert "-100|123" in config.tasks

    def test_get_and_remove_by_source_when_unique(self, tmp_path: Path) -> None:
        config_path = tmp_path / "watch_config.json"
        config_path.write_text(
            json.dumps({"1": {"-100|123": {"source": "-100", "dest": "123", "record_mode": False}}}),
            encoding="utf-8",
        )

        repo = JSONWatchRepository(config_path=config_path)
        task = repo.get_task("1", "-100")
        assert task is not None
        assert task.dest == "123"

        assert repo.remove_task("1", "-100") is True
        assert repo.get_user_config("1") is None

    def test_lookup_by_source_is_ambiguous_when_multiple_targets(self, tmp_path: Path) -> None:
        config_path = tmp_path / "watch_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "1": {
                        "-100|123": {"source": "-100", "dest": "123", "record_mode": False},
                        "-100|456": {"source": "-100", "dest": "456", "record_mode": False},
                    }
                }
            ),
            encoding="utf-8",
        )

        repo = JSONWatchRepository(config_path=config_path)
        assert repo.get_task("1", "-100") is None
        assert repo.remove_task("1", "-100") is False

        assert repo.remove_task("1", "-100|123") is True
