"""Unit tests: 关闭路径必须真正停止并 join 消息工作线程。"""

from __future__ import annotations

import queue

import pytest

from bot.core.queue import (
    initialize_message_queue,
    normalize_message_workers,
    shutdown_message_workers,
)
from bot.workers.message_worker import MessageWorker


class _DummyAcc:
    """占位 user client：worker 空转时不会调用它。"""

    def get_messages(self, chat_id, message_id: int):  # pragma: no cover - 不应被调用
        raise AssertionError("worker should stay idle in this test")


@pytest.fixture(autouse=True)
def _no_storage_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MessageWorker, "_init_storage_manager", lambda self: None)


class TestMessageWorkerShutdown:
    def test_shutdown_stops_and_joins_all_worker_threads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MESSAGE_WORKER_COUNT", "2")
        _message_queue, workers = initialize_message_queue(_DummyAcc())

        worker_list = normalize_message_workers(workers)
        assert len(worker_list) == 2
        assert all(worker.thread is not None and worker.thread.is_alive() for worker in worker_list)

        assert shutdown_message_workers(workers, timeout=5.0) is True

        for worker in worker_list:
            assert worker.running is False
            assert worker.thread.is_alive() is False

    def test_shutdown_handles_single_worker_return_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MESSAGE_WORKER_COUNT", "1")
        _message_queue, worker = initialize_message_queue(_DummyAcc())

        assert not isinstance(worker, list)
        assert shutdown_message_workers(worker, timeout=5.0) is True
        assert worker.thread.is_alive() is False

    def test_shutdown_without_workers_is_noop(self) -> None:
        assert shutdown_message_workers(None) is True
        assert normalize_message_workers(None) == []

    def test_join_thread_returns_true_when_never_started(self) -> None:
        worker = MessageWorker(queue.Queue(), _DummyAcc())

        assert worker.thread is None
        assert worker.stop_and_join(timeout=0.1) is True
        assert worker.running is False
