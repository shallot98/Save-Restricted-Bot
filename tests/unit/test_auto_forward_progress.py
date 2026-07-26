"""Unit tests: 「已处理」标记与 catch-up 游标只能在入队成功之后推进。"""

from __future__ import annotations

import queue
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest

from bot.handlers import auto_forward_pipeline as pipeline
from bot.handlers import auto_forward_progress as progress


@dataclass
class _Chat:
    id: int


@dataclass
class _Message:
    id: int
    chat: _Chat
    media_group_id: Optional[str] = None
    text: Optional[str] = "hello"
    caption: Optional[str] = None
    outgoing: bool = False


class _FakeQueue:
    """最小队列替身：full=True 时所有 put_nowait 抛 queue.Full。"""

    def __init__(self, *, full: bool = False) -> None:
        self.full = full
        self.items: list[Any] = []
        self.maxsize = 1

    def put_nowait(self, item: Any) -> None:
        if self.full:
            raise queue.Full()
        self.items.append(item)

    def qsize(self) -> int:
        return len(self.items)


@dataclass
class _FakeWatchService:
    source: str
    tasks: list = field(default_factory=list)

    def get_monitored_sources(self):
        return {self.source}

    def get_tasks_for_source(self, source_chat_id: str):
        assert source_chat_id == self.source
        return self.tasks


class _Recorder:
    def __init__(self) -> None:
        self.cursor_calls: list[tuple[str, int]] = []
        self.marked: list[tuple[int, int]] = []
        self.media_groups: list[str] = []


@pytest.fixture()
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    rec = _Recorder()

    progress._cursor_gaps.clear()

    monkeypatch.setattr(
        "bot.services.watch_catchup_store.advance_cursor",
        lambda source, message_id: rec.cursor_calls.append((str(source), int(message_id))),
    )
    monkeypatch.setattr(
        progress,
        "mark_message_processed",
        lambda message_id, chat_id: rec.marked.append((message_id, chat_id)),
    )
    monkeypatch.setattr(progress, "is_message_processed", lambda message_id, chat_id: False)
    monkeypatch.setattr(
        progress,
        "register_processed_media_group",
        lambda key: rec.media_groups.append(key),
    )
    monkeypatch.setattr(progress, "is_media_group_processed", lambda key: False)
    monkeypatch.setattr(pipeline, "get_auto_forward_metrics", lambda: None)
    monkeypatch.setattr(pipeline, "_dispatch_pt_monitor", lambda message: None)
    return rec


def _watch_service(source: str, tasks: list) -> _FakeWatchService:
    """构造注入用的假 WatchService。

    改造前这里 monkeypatch `pipeline.get_watch_service`——那正是被消除的服务定位。
    现在 `process_auto_forward_message` 以关键字参数接收服务，测试直接传实例即可。
    """
    return _FakeWatchService(source=source, tasks=tasks)


def _single_task(dest: str = "-200") -> list:
    return [("user1", "-100", {"dest": dest, "record_mode": False})]


class TestAutoForwardProgressMarkers:
    def test_successful_enqueue_advances_cursor_and_marks(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        service = _watch_service("-100", _single_task())
        fake_queue = _FakeQueue()

        pipeline.process_auto_forward_message(
            _Message(id=100, chat=_Chat(id=-100)), fake_queue, watch_service=service
        )

        assert len(fake_queue.items) == 1
        assert recorder.cursor_calls == [("-100", 100)]
        assert recorder.marked == [(100, -100)]

    def test_queue_full_keeps_cursor_and_dedup_mark_untouched(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        service = _watch_service("-100", _single_task())
        fake_queue = _FakeQueue(full=True)

        pipeline.process_auto_forward_message(
            _Message(id=100, chat=_Chat(id=-100)), fake_queue, watch_service=service
        )

        assert fake_queue.items == []
        assert recorder.cursor_calls == []
        assert recorder.marked == []

    def test_media_group_registered_only_after_successful_enqueue(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        service = _watch_service("-100", _single_task())
        dropped_message = _Message(id=100, chat=_Chat(id=-100), media_group_id="grp1")

        pipeline.process_auto_forward_message(
            dropped_message, _FakeQueue(full=True), watch_service=service
        )
        assert recorder.media_groups == []

        pipeline.process_auto_forward_message(
            dropped_message, _FakeQueue(), watch_service=service
        )
        assert len(recorder.media_groups) == 1
        assert recorder.media_groups[0].endswith("grp1")

    def test_cursor_never_skips_over_an_earlier_dropped_message(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        service = _watch_service("-100", _single_task())

        # 100 入队失败 → 记录 gap
        pipeline.process_auto_forward_message(
            _Message(id=100, chat=_Chat(id=-100)), _FakeQueue(full=True), watch_service=service
        )
        # 101 入队成功，但不得越过 100 推进游标
        pipeline.process_auto_forward_message(
            _Message(id=101, chat=_Chat(id=-100)), _FakeQueue(), watch_service=service
        )
        assert recorder.cursor_calls == []

        # 补扫重投 100 成功后，游标才可推进
        pipeline.process_auto_forward_message(
            _Message(id=100, chat=_Chat(id=-100)), _FakeQueue(), watch_service=service
        )
        assert recorder.cursor_calls == [("-100", 100)]

    def test_partial_drop_across_tasks_blocks_progress(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        service = _watch_service(
            "-100",
            [
                ("user1", "-100", {"dest": "-200", "record_mode": False}),
                ("user2", "-100", {"dest": "-300", "record_mode": False}),
            ],
        )

        class _OneSlotQueue(_FakeQueue):
            def put_nowait(self, item: Any) -> None:
                if self.items:
                    raise queue.Full()
                self.items.append(item)

        fake_queue = _OneSlotQueue()
        pipeline.process_auto_forward_message(
            _Message(id=100, chat=_Chat(id=-100)), fake_queue, watch_service=service
        )

        assert len(fake_queue.items) == 1
        assert recorder.cursor_calls == []
        assert recorder.marked == []

    def test_non_monitored_source_is_marked_without_cursor_advance(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        service = _watch_service("-999", _single_task())

        pipeline.process_auto_forward_message(
            _Message(id=100, chat=_Chat(id=-100)), _FakeQueue(), watch_service=service
        )

        assert recorder.marked == [(100, -100)]
        assert recorder.cursor_calls == []
