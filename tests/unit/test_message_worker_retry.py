"""
Unit tests for MessageWorker retry behavior (replayable payload).
"""

from __future__ import annotations

import queue
from dataclasses import dataclass
from typing import Optional

import pytest

from bot.workers.message_worker import Message, MessageWorker, UnrecoverableError


@dataclass
class _DummyFetchedMessage:
    text: Optional[str] = None
    caption: Optional[str] = None
    media_group_id: Optional[str] = None


class _DummyAcc:
    def __init__(
        self,
        fetched: Optional[_DummyFetchedMessage] = None,
        media_group_caption: str = "group_caption",
    ) -> None:
        self.calls: list[tuple[object, int]] = []
        self.media_group_calls: list[tuple[object, int]] = []
        self._fetched = fetched or _DummyFetchedMessage(text="fetched")
        self._media_group_caption = media_group_caption

    def get_messages(self, chat_id, message_id: int):
        self.calls.append((chat_id, message_id))
        return self._fetched

    def get_media_group(self, chat_id, message_id: int):
        self.media_group_calls.append((chat_id, message_id))
        return [_DummyFetchedMessage(caption=self._media_group_caption)]


class TestMessageWorkerRetry:
    def test_ensure_message_loaded_fetches_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(MessageWorker, "_init_storage_manager", lambda self: None)
        worker = MessageWorker(queue.Queue(), _DummyAcc())

        msg = Message(
            user_id="1",
            watch_key="k",
            source_chat_id="-100",
            message_id=123,
            watch_data={},
            dest_chat_id=None,
            message_text="",
            message=None,
        )

        fetched = worker._ensure_message_loaded(msg)
        assert fetched is msg.message
        assert msg.message_text == "fetched"

    def test_ensure_message_loaded_fills_text_from_media_group_caption(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(MessageWorker, "_init_storage_manager", lambda self: None)
        acc = _DummyAcc(
            fetched=_DummyFetchedMessage(media_group_id="grp"),
            media_group_caption="from_group",
        )
        worker = MessageWorker(queue.Queue(), acc)

        msg = Message(
            user_id="1",
            watch_key="k",
            source_chat_id="-100",
            message_id=123,
            watch_data={},
            dest_chat_id=None,
            message_text="",
            message=None,
        )

        worker._ensure_message_loaded(msg)
        assert msg.message_text == "from_group"
        assert acc.media_group_calls == [(-100, 123)]

    def test_ensure_message_loaded_raises_without_user_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(MessageWorker, "_init_storage_manager", lambda self: None)
        worker = MessageWorker(queue.Queue(), None)

        msg = Message(
            user_id="1",
            watch_key="k",
            source_chat_id="-100",
            message_id=123,
            watch_data={},
            dest_chat_id=None,
            message_text="",
            message=None,
        )

        with pytest.raises(UnrecoverableError):
            worker._ensure_message_loaded(msg)

    def test_run_requeues_and_clears_message_on_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(MessageWorker, "_init_storage_manager", lambda self: None)
        monkeypatch.setattr("bot.workers.message_worker.get_backoff_time", lambda _: 0)
        monkeypatch.setattr("bot.workers.message_worker.time.sleep", lambda _: None)

        message_queue: queue.Queue = queue.Queue()
        worker = MessageWorker(message_queue, _DummyAcc(), max_retries=1)

        msg = Message(
            user_id="1",
            watch_key="k",
            source_chat_id="-100",
            message_id=123,
            watch_data={},
            dest_chat_id=None,
            message_text="hi",
            message=object(),
        )
        message_queue.put(msg)

        def _fake_process(self, msg_obj: Message) -> str:
            self.running = False
            return "retry"

        monkeypatch.setattr(MessageWorker, "process_message", _fake_process, raising=True)

        worker.run()

        assert message_queue.qsize() == 0
        assert len(worker._delayed) == 1
        _, _, requeued = worker._delayed[0]
        assert requeued.retry_count == 1
        assert requeued.message is None
