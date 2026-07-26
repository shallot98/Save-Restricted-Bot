"""Unit tests for monitored-source catch-up scanner."""

from __future__ import annotations

import queue
from types import SimpleNamespace
from typing import Any, List

from bot.handlers.auto_forward_pipeline import MessageProgress
from bot.services.watch_catchup_scanner import WatchCatchupScanner


class _FakeHistory:
    def __init__(self, messages: List[object]):
        self._messages = messages

    def __iter__(self):
        return iter(self._messages)


class _FakeClient:
    def __init__(self, messages_by_chat: dict):
        self.messages_by_chat = messages_by_chat
        self.calls = []

    def get_chat_history(self, chat_id, limit=50):
        self.calls.append((chat_id, limit))
        return _FakeHistory(list(self.messages_by_chat.get(chat_id, [])))


def _msg(message_id: int, *, service=None, empty=False):
    return SimpleNamespace(id=message_id, service=service, empty=empty, text=f"m-{message_id}")


def _recording_processor(processed: List[int], progress_by_id: dict | None = None):
    """Fake pipeline: records handled ids and reports MessageProgress back."""

    def _process(message, _queue) -> Any:
        processed.append(message.id)
        if progress_by_id is None:
            return MessageProgress.ENQUEUED
        return progress_by_id.get(message.id, MessageProgress.ENQUEUED)

    return _process


def test_first_scan_initializes_without_enqueue(monkeypatch):
    stored = {}

    def fake_get_cursor(source):
        return stored.get(str(source))

    def fake_ensure(source, latest):
        cursor = SimpleNamespace(
            source_chat_id=str(source),
            last_seen_id=int(latest),
            initialized=True,
        )
        stored[str(source)] = cursor
        return cursor

    monkeypatch.setattr("bot.services.watch_catchup_scanner.get_cursor", fake_get_cursor)
    monkeypatch.setattr(
        "bot.services.watch_catchup_scanner.ensure_cursor_initialized",
        fake_ensure,
    )

    processed = []
    client = _FakeClient({-1001: [_msg(10), _msg(9), _msg(8)]})
    scanner = WatchCatchupScanner(
        client,
        message_queue=object(),
        process_message=_recording_processor(processed),
        get_monitored_sources=lambda: ["-1001"],
        lookback=20,
        max_enqueue_per_source=10,
    )

    result = scanner.scan_once()
    assert result.sources_initialized == 1
    assert result.messages_enqueued == 0
    assert processed == []
    assert stored["-1001"].last_seen_id == 10


def test_scan_enqueues_only_messages_after_cursor(monkeypatch):
    stored = {
        "-1001": SimpleNamespace(
            source_chat_id="-1001",
            last_seen_id=8,
            initialized=True,
        )
    }
    advanced = []

    monkeypatch.setattr(
        "bot.services.watch_catchup_scanner.get_cursor",
        lambda source: stored.get(str(source)),
    )
    monkeypatch.setattr(
        "bot.services.watch_catchup_scanner.advance_cursor",
        lambda source, mid: advanced.append((str(source), int(mid))),
    )

    processed = []
    client = _FakeClient(
        {
            -1001: [
                _msg(12),
                _msg(11),
                _msg(10),
                _msg(9),
                _msg(8),
                _msg(7),
            ]
        }
    )
    scanner = WatchCatchupScanner(
        client,
        message_queue=object(),
        process_message=_recording_processor(processed),
        get_monitored_sources=lambda: ["-1001"],
        lookback=20,
        max_enqueue_per_source=10,
    )

    result = scanner.scan_once()
    assert result.messages_enqueued == 4
    assert processed == [9, 10, 11, 12]
    assert advanced == [
        ("-1001", 9),
        ("-1001", 10),
        ("-1001", 11),
        ("-1001", 12),
    ]


def test_scan_respects_max_enqueue_and_skips_service(monkeypatch):
    stored = {
        "-1001": SimpleNamespace(
            source_chat_id="-1001",
            last_seen_id=1,
            initialized=True,
        )
    }
    advanced = []
    monkeypatch.setattr(
        "bot.services.watch_catchup_scanner.get_cursor",
        lambda source: stored.get(str(source)),
    )
    monkeypatch.setattr(
        "bot.services.watch_catchup_scanner.advance_cursor",
        lambda source, mid: advanced.append(int(mid)),
    )

    processed = []
    client = _FakeClient(
        {
            -1001: [
                _msg(6),
                _msg(5),
                _msg(4, service="pin"),
                _msg(3),
                _msg(2),
            ]
        }
    )
    scanner = WatchCatchupScanner(
        client,
        message_queue=object(),
        process_message=_recording_processor(processed),
        get_monitored_sources=lambda: ["-1001"],
        lookback=20,
        max_enqueue_per_source=2,
    )

    result = scanner.scan_once()
    assert result.messages_enqueued == 2
    # service message excluded; ascending from >1 => 2,3,5,6 then cap 2
    assert processed == [2, 3]
    assert advanced == [2, 3]


def test_select_candidates_sorts_ascending():
    history = [_msg(5), _msg(3), _msg(4)]
    selected = WatchCatchupScanner._select_candidates(history, last_seen_id=3)
    assert [m.id for m in selected] == [4, 5]


def _scanner_with_cursor(monkeypatch, *, last_seen_id: int, history: list, process_message):
    """Wire a scanner against a fixed cursor; returns (scanner, advanced_ids)."""
    stored = {
        "-100": SimpleNamespace(source_chat_id="-100", last_seen_id=last_seen_id, initialized=True)
    }
    advanced: List[int] = []
    monkeypatch.setattr(
        "bot.services.watch_catchup_scanner.get_cursor",
        lambda source: stored.get(str(source)),
    )
    monkeypatch.setattr(
        "bot.services.watch_catchup_scanner.advance_cursor",
        lambda source, mid: advanced.append(int(mid)),
    )
    scanner = WatchCatchupScanner(
        _FakeClient({-100: history}),
        message_queue=object(),
        process_message=process_message,
        get_monitored_sources=lambda: ["-100"],
        lookback=20,
        max_enqueue_per_source=10,
    )
    return scanner, advanced


class TestCatchupCursorRespectsEnqueueOutcome:
    """补扫游标必须与 pipeline 的入队结果一致，否则被丢弃的消息永不再补扫。"""

    def test_dropped_message_stops_cursor_at_the_gap(self, monkeypatch):
        processed: List[int] = []
        scanner, advanced = _scanner_with_cursor(
            monkeypatch,
            last_seen_id=8,
            history=[_msg(11), _msg(10), _msg(9)],
            process_message=_recording_processor(
                processed, {10: MessageProgress.BLOCKED}
            ),
        )

        result = scanner.scan_once()

        # 9 成功推进；10 被丢弃 → 游标停住，11 留待下轮（仍在游标之后）
        assert advanced == [9]
        assert processed == [9, 10]
        assert result.messages_enqueued == 1

    def test_skipped_message_still_advances_cursor(self, monkeypatch):
        processed: List[int] = []
        scanner, advanced = _scanner_with_cursor(
            monkeypatch,
            last_seen_id=8,
            history=[_msg(10), _msg(9)],
            process_message=_recording_processor(
                processed, {9: MessageProgress.SKIPPED}
            ),
        )

        scanner.scan_once()

        # 非监控源 / 已处理过的消息无需入队，游标可以安全越过
        assert advanced == [9, 10]

    def test_processor_without_progress_report_blocks_cursor(self, monkeypatch):
        scanner, advanced = _scanner_with_cursor(
            monkeypatch,
            last_seen_id=8,
            history=[_msg(9)],
            process_message=lambda message, q: None,
        )

        result = scanner.scan_once()

        assert advanced == []
        assert result.messages_enqueued == 0


class _PipelineQueue:
    """最小队列替身：full=True 时所有 put_nowait 抛 queue.Full。"""

    def __init__(self, *, full: bool = False) -> None:
        self.full = full
        self.items: List[Any] = []

    def put_nowait(self, item: Any) -> None:
        if self.full:
            raise queue.Full()
        self.items.append(item)

    def qsize(self) -> int:
        return len(self.items)


def _pipeline_msg(message_id: int):
    return SimpleNamespace(
        id=message_id,
        chat=SimpleNamespace(id=-100),
        media_group_id=None,
        text=f"m-{message_id}",
        caption=None,
        outgoing=False,
        service=None,
        empty=False,
    )


def test_catchup_with_real_pipeline_holds_cursor_until_enqueue_succeeds(monkeypatch):
    """端到端：补扫 → 真实 pipeline。队列满时游标不动，重试成功后才推进。"""
    from bot.handlers import auto_forward_pipeline as pipeline
    from bot.handlers import auto_forward_progress as progress

    progress._cursor_gaps.clear()
    watch_service = SimpleNamespace(
        get_monitored_sources=lambda: {"-100"},
        get_tasks_for_source=lambda source: [("user1", "-100", {"dest": "-200", "record_mode": False})],
    )
    # 服务改为参数注入：pipeline 不再有可 monkeypatch 的模块级 get_watch_service
    monkeypatch.setattr(progress, "is_message_processed", lambda message_id, chat_id: False)
    monkeypatch.setattr(progress, "mark_message_processed", lambda message_id, chat_id: None)
    monkeypatch.setattr(pipeline, "get_auto_forward_metrics", lambda: None)
    monkeypatch.setattr(pipeline, "_dispatch_pt_monitor", lambda message: None)

    pipeline_advanced: List[int] = []
    monkeypatch.setattr(
        "bot.services.watch_catchup_store.advance_cursor",
        lambda source, mid: pipeline_advanced.append(int(mid)),
    )

    history = [_pipeline_msg(10), _pipeline_msg(9)]
    full_queue = _PipelineQueue(full=True)
    scanner, scanner_advanced = _scanner_with_cursor(
        monkeypatch,
        last_seen_id=8,
        history=history,
        process_message=lambda message, _q: pipeline.process_auto_forward_message(
            message, full_queue, watch_service=watch_service
        ),
    )

    result = scanner.scan_once()
    assert full_queue.items == []
    assert scanner_advanced == []
    assert pipeline_advanced == []
    assert result.messages_enqueued == 0

    open_queue = _PipelineQueue()
    scanner._process_message = lambda message, _q: pipeline.process_auto_forward_message(
        message, open_queue, watch_service=watch_service
    )

    scanner.scan_once()
    assert [m.message_id for m in open_queue.items] == [9, 10]
    assert scanner_advanced == [9, 10]
    assert pipeline_advanced == [9, 10]
