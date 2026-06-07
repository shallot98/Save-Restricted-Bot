from __future__ import annotations

import threading
from pathlib import Path

from bot.services.history_copy_models import HistoryCopySettings, HistoryCopyStats
from bot.services.history_copy_task_manager import HistoryCopyTaskManager
from bot.services.history_copy_task_models import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_INTERRUPTED,
    STATUS_RUNNING,
)
from bot.services.history_copy_task_storage import HistoryCopyTaskStorage


def _settings_for(task) -> HistoryCopySettings:
    return HistoryCopySettings(
        source_chat_ref=task.source_chat_ref,
        dest_chat_ref=task.dest_chat_ref,
        source_chat_id="-100001",
        dest_chat_id="-100002",
        state_db_path=Path(task.state_db_path),
        history_limit=task.history_limit,
    )


def test_manager_completes_task_and_updates_counts(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def executor(_client, task, _progress_callback=None):
        started.set()
        release.wait(timeout=2)
        stats = HistoryCopyStats(scanned_count=10, copied_count=8, skipped_count=1, failed_count=1)
        return _settings_for(task), stats

    storage = HistoryCopyTaskStorage(tmp_path / "history_copy_tasks.json")
    manager = HistoryCopyTaskManager(storage=storage, executor=executor)
    manager.bind_client(object())

    task = manager.add_task(
        user_id="1001",
        source_chat_ref="@source",
        source_name="源群",
        dest_chat_ref="@dest",
        dest_name="目标群",
        history_limit=500,
    )

    assert started.wait(timeout=2) is True
    assert manager.count_running_user_tasks("1001") == 1

    release.set()
    worker = manager._workers[task.task_id]
    worker.join(timeout=2)

    updated = manager.get_user_task("1001", task.task_id)
    assert updated is not None
    assert updated.status == STATUS_COMPLETED
    assert updated.copied_count == 8
    assert manager.count_running_user_tasks("1001") == 0


def test_manager_blocks_second_running_task(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def executor(_client, task, _progress_callback=None):
        started.set()
        release.wait(timeout=2)
        return _settings_for(task), HistoryCopyStats()

    storage = HistoryCopyTaskStorage(tmp_path / "history_copy_tasks.json")
    manager = HistoryCopyTaskManager(storage=storage, executor=executor)
    manager.bind_client(object())
    first = manager.add_task(
        user_id="1002",
        source_chat_ref="@source",
        source_name="源群",
        dest_chat_ref="@dest",
        dest_name="目标群",
        history_limit=None,
    )

    assert started.wait(timeout=2) is True
    try:
        manager.add_task(
            user_id="1002",
            source_chat_ref="@source2",
            source_name="源群2",
            dest_chat_ref="@dest2",
            dest_name="目标群2",
            history_limit=100,
        )
    except ValueError as exc:
        assert "已有历史复制任务正在运行" in str(exc)
    else:
        raise AssertionError("expected running-task guard")
    finally:
        release.set()
        manager._workers[first.task_id].join(timeout=2)


def test_manager_marks_failures_and_can_remove_finished_task(tmp_path: Path) -> None:
    def executor(_client, _task, _progress_callback=None):
        raise RuntimeError("boom")

    storage = HistoryCopyTaskStorage(tmp_path / "history_copy_tasks.json")
    manager = HistoryCopyTaskManager(storage=storage, executor=executor)
    manager.bind_client(object())

    task = manager.add_task(
        user_id="1003",
        source_chat_ref="@source",
        source_name="源群",
        dest_chat_ref="@dest",
        dest_name="目标群",
        history_limit=None,
    )
    manager._workers[task.task_id].join(timeout=2)

    failed = manager.get_user_task("1003", task.task_id)
    assert failed is not None
    assert failed.status == STATUS_FAILED
    assert "RuntimeError: boom" in failed.error_message

    removed = manager.remove_task("1003", task.task_id)
    assert removed.task_id == task.task_id
    assert manager.count_user_tasks("1003") == 0


def test_manager_marks_persisted_running_task_as_interrupted(tmp_path: Path) -> None:
    storage = HistoryCopyTaskStorage(tmp_path / "history_copy_tasks.json")
    task = storage.load()
    assert task == {}

    stale_task = {
        "1004": {
            "task-1": {
                "source_chat_ref": "@source",
                "source_name": "源群",
                "dest_chat_ref": "@dest",
                "dest_name": "目标群",
                "state_db_path": str(tmp_path / "state.db"),
                "history_limit": None,
                "status": "running",
                "created_at": 1.0,
                "started_at": 1.0,
            }
        }
    }
    storage._atomic_write(stale_task)

    manager = HistoryCopyTaskManager(
        storage=storage,
        executor=lambda client, task, _progress_callback=None: (
            _settings_for(task),
            HistoryCopyStats(),
        ),
    )
    loaded = manager.get_user_task("1004", "task-1")
    assert loaded is not None
    assert loaded.status == STATUS_INTERRUPTED


def test_manager_restarts_failed_task_with_same_checkpoint_db(tmp_path: Path) -> None:
    clock_values = iter([10.0, 20.0, 30.0, 40.0])
    calls: list[tuple[str, str, float]] = []

    def executor(_client, task, _progress_callback=None):
        calls.append((task.task_id, task.state_db_path, task.started_at))
        if len(calls) == 1:
            raise RuntimeError("boom")
        return _settings_for(task), HistoryCopyStats(copied_count=2)

    storage = HistoryCopyTaskStorage(tmp_path / "history_copy_tasks.json")
    manager = HistoryCopyTaskManager(
        storage=storage,
        executor=executor,
        clock=lambda: next(clock_values),
    )
    manager.bind_client(object())

    task = manager.add_task(
        user_id="1005",
        source_chat_ref="@source",
        source_name="源群",
        dest_chat_ref="@dest",
        dest_name="目标群",
        history_limit=100,
    )
    manager._workers[task.task_id].join(timeout=2)

    failed = manager.get_user_task("1005", task.task_id)
    assert failed is not None
    assert failed.status == STATUS_FAILED

    restarted = manager.restart_task("1005", task.task_id)
    assert restarted.status == STATUS_RUNNING
    assert restarted.task_id == task.task_id
    assert restarted.state_db_path == task.state_db_path
    assert restarted.started_at == 30.0

    manager._workers[task.task_id].join(timeout=2)
    updated = manager.get_user_task("1005", task.task_id)
    assert updated is not None
    assert updated.status == STATUS_COMPLETED
    assert calls == [
        (task.task_id, task.state_db_path, 10.0),
        (task.task_id, task.state_db_path, 30.0),
    ]


def test_manager_updates_running_counts_from_progress_callback(tmp_path: Path) -> None:
    progress_published = threading.Event()
    release = threading.Event()

    def executor(_client, task, progress_callback=None):
        assert progress_callback is not None
        progress_callback(
            HistoryCopyStats(scanned_count=5, copied_count=3, skipped_count=1, failed_count=1)
        )
        progress_published.set()
        release.wait(timeout=2)
        return _settings_for(task), HistoryCopyStats(
            scanned_count=6,
            copied_count=4,
            skipped_count=1,
            failed_count=1,
        )

    storage = HistoryCopyTaskStorage(tmp_path / "history_copy_tasks.json")
    manager = HistoryCopyTaskManager(storage=storage, executor=executor)
    manager.bind_client(object())

    task = manager.add_task(
        user_id="1006",
        source_chat_ref="@source",
        source_name="源群",
        dest_chat_ref="@dest",
        dest_name="目标群",
        history_limit=None,
    )

    assert progress_published.wait(timeout=2) is True
    running = manager.get_user_task("1006", task.task_id)
    assert running is not None
    assert running.status == STATUS_RUNNING
    assert running.status_message == "scanned=5 copied=3 skipped=1 failed=1"
    assert running.scanned_count == 5
    assert running.copied_count == 3

    release.set()
    manager._workers[task.task_id].join(timeout=2)


def test_manager_updates_running_counts_from_progress_callback(tmp_path: Path) -> None:
    progress_published = threading.Event()
    release = threading.Event()

    def executor(_client, task, progress_callback=None):
        assert progress_callback is not None
        progress_callback(
            HistoryCopyStats(scanned_count=5, copied_count=3, skipped_count=1, failed_count=1)
        )
        progress_published.set()
        release.wait(timeout=2)
        return _settings_for(task), HistoryCopyStats(
            scanned_count=6,
            copied_count=4,
            skipped_count=1,
            failed_count=1,
        )

    storage = HistoryCopyTaskStorage(tmp_path / "history_copy_tasks.json")
    manager = HistoryCopyTaskManager(storage=storage, executor=executor)
    manager.bind_client(object())

    task = manager.add_task(
        user_id="1006",
        source_chat_ref="@source",
        source_name="源群",
        dest_chat_ref="@dest",
        dest_name="目标群",
        history_limit=None,
    )

    assert progress_published.wait(timeout=2) is True
    running = manager.get_user_task("1006", task.task_id)
    assert running is not None
    assert running.status == STATUS_RUNNING
    assert running.status_message == "scanned=5 copied=3 skipped=1 failed=1"
    assert running.scanned_count == 5
    assert running.copied_count == 3

    release.set()
    manager._workers[task.task_id].join(timeout=2)
