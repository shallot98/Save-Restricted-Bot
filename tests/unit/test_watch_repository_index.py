"""
Unit tests for JSONWatchRepository source index.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.infrastructure.persistence.repositories.watch_repository import JSONWatchRepository


class TestJSONWatchRepositorySourceIndex:
    def test_get_tasks_for_source_matches_by_task_source(self, tmp_path: Path) -> None:
        config_path = tmp_path / "watch_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "1": {
                        "-100|123": {"source": "-100", "dest": "123", "record_mode": False},
                        "-100|record": {"source": "-100", "dest": None, "record_mode": True},
                        "-200|456": {"source": "-200", "dest": "456", "record_mode": False},
                    }
                }
            ),
            encoding="utf-8",
        )

        repo = JSONWatchRepository(config_path=config_path)
        tasks = repo.get_tasks_for_source("-100")

        keys = {watch_key for _, watch_key, _ in tasks}
        assert keys == {"-100|123", "-100|record"}

