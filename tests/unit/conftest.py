from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def captured_watch_config_saves(monkeypatch: pytest.MonkeyPatch) -> List[Dict[str, Any]]:
    """Regression guard: nothing may write the operator's live watch config.

    History: ``SQLiteWatchRepository`` used to mirror its whole in-memory cache
    to ``$DATA_DIR/config/watch_config.json`` after every mutation
    (``_sync_to_json``), resolving ``settings`` lazily *inside* that method so
    patching the module attribute did not intercept it. A repository test's
    ``repo.add_task(...)`` therefore replaced the real file with fixture data.

    That double-write has been removed — ``watch_config.json`` is now a
    read-only legacy migration source and SQLite ``watch_tasks`` is the only
    backend. This fixture stays as defence in depth: if any write path starts
    calling ``settings.save_watch_config`` again, it is captured here instead
    of hitting the real file, and
    ``test_sqlite_watch_repository_writes_never_touch_watch_json`` fails.

    The captured payloads are returned so a test can still assert on them.
    """
    from src.core.config import settings

    saved: List[Dict[str, Any]] = []

    def _capture(config: Dict[str, Any], auto_reload: bool = True) -> None:
        saved.append(config)

    monkeypatch.setattr(settings, "save_watch_config", _capture, raising=False)
    return saved
