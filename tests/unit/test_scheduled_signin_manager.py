from __future__ import annotations

from pathlib import Path

import pytest

from bot.services.signin_manager import ScheduledSigninManager
from bot.services.signin_models import (
    ScheduledSigninTaskConfig,
    describe_interval_spec,
    normalize_interval_spec,
    resolve_interval_seconds,
)
from bot.services.signin_storage import ScheduledSigninStorage


class FakeRuntime:
    def __init__(self, client: object, task: ScheduledSigninTaskConfig) -> None:
        self.client = client
        self.task = task
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_normalize_interval_spec_supports_units() -> None:
    assert normalize_interval_spec("3600") == "3600s"
    assert normalize_interval_spec("30m") == "30m"
    assert normalize_interval_spec("8H") == "8h"
    assert normalize_interval_spec("1d") == "1d"
    assert resolve_interval_seconds("1.5h") == 5400.0
    assert describe_interval_spec("30m") == "每 30 分钟"


@pytest.mark.parametrize("value", ["0", "-1", "abc", "10w"])
def test_normalize_interval_spec_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_interval_spec(value)


def test_scheduled_signin_manager_persists_and_restarts_runtime(tmp_path: Path) -> None:
    storage = ScheduledSigninStorage(tmp_path / "scheduled_signin.json")
    runtimes: list[FakeRuntime] = []

    def runtime_factory(client: object, task: ScheduledSigninTaskConfig) -> FakeRuntime:
        runtime = FakeRuntime(client, task)
        runtimes.append(runtime)
        return runtime

    manager = ScheduledSigninManager(storage=storage, runtime_factory=runtime_factory)
    client = object()
    manager.bind_client(client)

    task = manager.add_task(
        user_id="10001",
        chat_id="-1001234567890",
        chat_name="签到群",
        chat_ref="-1001234567890",
        message_text="司机人，签到",
        interval_spec="8h",
    )

    assert task.interval_spec == "8h"
    assert manager.count_user_tasks("10001") == 1
    assert len(runtimes) == 1
    assert runtimes[0].started is True

    updated = manager.update_interval_spec("10001", task.task_id, "12h")
    assert updated.interval_spec == "12h"
    assert runtimes[0].stopped is True
    assert len(runtimes) == 2
    assert runtimes[1].started is True

    reloaded = ScheduledSigninManager(storage=storage, runtime_factory=runtime_factory)
    persisted = reloaded.get_user_task("10001", task.task_id)
    assert persisted is not None
    assert persisted.interval_spec == "12h"
    assert persisted.message_text == "司机人，签到"

    with pytest.raises(ValueError):
        reloaded.add_task(
            user_id="10001",
            chat_id="-1001234567890",
            chat_name="签到群",
            chat_ref="-1001234567890",
            message_text="司机人，签到",
            interval_spec="1d",
        )

    removed = reloaded.remove_task("10001", task.task_id)
    assert removed.task_id == task.task_id
    assert reloaded.count_user_tasks("10001") == 0
