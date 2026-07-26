from __future__ import annotations

from pathlib import Path

from bot.services.pt_pay_manager import PTPayMonitorManager
from bot.services.pt_pay_storage import PTPayMonitorStorage


class FakeRuntime:
    def __init__(self, client, task):
        self.client = client
        self.task = task
        self.start_calls = 0
        self.stop_calls = 0

    def start(self):
        self.start_calls += 1

    def stop(self):
        self.stop_calls += 1


def test_manager_add_toggle_remove_lifecycle(tmp_path: Path):
    created: list[FakeRuntime] = []

    def runtime_factory(client, task):
        runtime = FakeRuntime(client, task)
        created.append(runtime)
        return runtime

    storage = PTPayMonitorStorage(tmp_path / "pt_pay.json")
    manager = PTPayMonitorManager(storage=storage, runtime_factory=runtime_factory)
    manager.bind_client(object())

    task = manager.add_task("100", "-1001", "测试群", 2001, "pay_bot")
    assert task.enabled is True
    assert len(created) == 1
    assert created[0].start_calls == 1

    disabled = manager.toggle_task("100", task.task_id)
    assert disabled.enabled is False
    assert created[0].stop_calls == 1

    enabled = manager.toggle_task("100", task.task_id)
    assert enabled.enabled is True
    assert len(created) == 2
    assert created[1].start_calls == 1

    removed = manager.remove_task("100", task.task_id)
    assert removed.task_id == task.task_id
    assert created[1].stop_calls == 1
    assert manager.count_user_tasks("100") == 0


def test_storage_round_trip_preserves_task_fields(tmp_path: Path):
    storage = PTPayMonitorStorage(tmp_path / "pt_pay.json")
    manager = PTPayMonitorManager(storage=storage, runtime_factory=lambda client, task: FakeRuntime(client, task))
    task = manager.add_task("200", "-1002", "群A", 3002, "botA")
    manager.shutdown()

    reloaded = PTPayMonitorManager(storage=storage, runtime_factory=lambda client, task: FakeRuntime(client, task))
    tasks = reloaded.list_user_tasks("200")

    assert len(tasks) == 1
    assert tasks[0].task_id == task.task_id
    assert tasks[0].source_chat_id == "-1002"
    assert tasks[0].target_bot_id == 3002


def test_manager_update_delay_restarts_enabled_runtime(tmp_path: Path):
    created: list[FakeRuntime] = []

    def runtime_factory(client, task):
        runtime = FakeRuntime(client, task)
        created.append(runtime)
        return runtime

    storage = PTPayMonitorStorage(tmp_path / "pt_pay.json")
    manager = PTPayMonitorManager(storage=storage, runtime_factory=runtime_factory)
    manager.bind_client(object())

    task = manager.add_task("300", "-1003", "群B", 3003, "botB")
    updated = manager.update_delay_spec("300", task.task_id, "0-100")

    assert updated.trigger_delay_spec == "0-100"
    assert created[0].stop_calls == 1
    assert len(created) == 2
    assert created[1].task.trigger_delay_spec == "0-100"


def test_manager_warms_source_peer_before_start(monkeypatch, tmp_path: Path):
    created: list[FakeRuntime] = []
    warmed: list[tuple[int, str]] = []

    def runtime_factory(client, task):
        runtime = FakeRuntime(client, task)
        created.append(runtime)
        return runtime

    def fake_cache_peer_if_needed(client, peer_id, peer_type="频道"):
        warmed.append((peer_id, peer_type))
        return True

    monkeypatch.setattr('bot.services.peer_cache.cache_peer_if_needed', fake_cache_peer_if_needed)

    storage = PTPayMonitorStorage(tmp_path / "pt_pay.json")
    manager = PTPayMonitorManager(storage=storage, runtime_factory=runtime_factory)
    manager.bind_client(object())
    manager.add_task('400', '-100400', '群C', 4004, 'botC')

    assert warmed == [(-100400, '脚本源群')]
    assert created[0].start_calls == 1
