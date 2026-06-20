from __future__ import annotations

from types import SimpleNamespace

from bot.services.pt_pay_monitor import (
    extract_pt_codes,
    contains_success_keyword,
    wait_for_bot_reply,
)


class FakeClient:
    def __init__(self, history_batches):
        self._history_batches = list(history_batches)
        self._call_count = 0

    def get_chat_history(self, chat_id, limit=10):
        index = min(self._call_count, len(self._history_batches) - 1)
        self._call_count += 1
        for message in self._history_batches[index]:
            yield message


def make_message(message_id: int, text: str, outgoing: bool = False):
    return SimpleNamespace(id=message_id, text=text, caption=None, outgoing=outgoing)


def test_extract_pt_codes_preserves_order_and_deduplicates():
    text = """
    PT-100
    无关内容
    PT-200
    PT-100
    PT-300-extra
    """
    assert extract_pt_codes(text) == ["PT-100", "PT-200", "PT-300-extra"]


def test_contains_success_keyword_matches_substring():
    assert contains_success_keyword("支付成功，已处理", ["成功"])
    assert not contains_success_keyword("处理中", ["成功"])


def test_wait_for_bot_reply_detects_success_message():
    client = FakeClient(
        history_batches=[
            [
                make_message(8, "支付成功"),
                make_message(7, "/pay PT-100", outgoing=True),
                make_message(6, "旧消息"),
            ]
        ]
    )

    result = wait_for_bot_reply(
        client=client,
        target_chat_ref=12345,
        sent_message_id=7,
        success_keywords=["成功"],
        timeout_seconds=0.01,
        poll_interval_seconds=0.0,
        history_limit=10,
    )

    assert result.success is True
    assert result.matched_reply == "支付成功"


def test_wait_for_bot_reply_ignores_non_success_messages():
    client = FakeClient(
        history_batches=[
            [
                make_message(9, "处理中"),
                make_message(8, "队列中"),
                make_message(7, "/pay PT-100", outgoing=True),
            ]
        ]
    )

    result = wait_for_bot_reply(
        client=client,
        target_chat_ref=12345,
        sent_message_id=7,
        success_keywords=["成功"],
        timeout_seconds=0.01,
        poll_interval_seconds=0.0,
        history_limit=10,
    )

    assert result.success is False
    assert result.observed_replies == ("处理中", "队列中")


def test_wait_for_bot_reply_returns_early_on_failure_keywords():
    client = FakeClient(
        history_batches=[
            [
                make_message(9, "编号无效"),
                make_message(8, "/pay PT-100", outgoing=True),
            ]
        ]
    )

    result = wait_for_bot_reply(
        client=client,
        target_chat_ref=12345,
        sent_message_id=8,
        success_keywords=["成功"],
        timeout_seconds=5.0,
        poll_interval_seconds=0.0,
        history_limit=10,
    )

    assert result.success is False
    assert result.matched_reply == "编号无效"
    assert result.observed_replies == ("编号无效",)


def test_monitor_ignores_messages_with_only_one_pt_code():
    from bot.services.pt_pay_runtime import MonitorSettings, PtPayMonitor

    monitor = PtPayMonitor(
        client=SimpleNamespace(),
        settings=MonitorSettings(
            source_chat_ref='-1001',
            target_bot_ref='@target',
            source_chat_id='-1001',
            target_bot_id=12345,
        ),
    )

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-1001),
        id=10,
        text='PT-ONLYONE',
        caption=None,
    )

    monitor.handle_message(message)

    assert monitor._task_queue.empty()


def test_monitor_enqueues_messages_with_two_pt_codes():
    from bot.services.pt_pay_runtime import MonitorSettings, PtPayMonitor

    monitor = PtPayMonitor(
        client=SimpleNamespace(),
        settings=MonitorSettings(
            source_chat_ref='-1001',
            target_bot_ref='@target',
            source_chat_id='-1001',
            target_bot_id=12345,
        ),
    )

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-1001),
        id=11,
        text='PT-ONE\nPT-TWO',
        caption=None,
    )

    monitor.handle_message(message)

    queued = monitor._task_queue.get_nowait()
    assert queued.pt_codes == ('PT-ONE', 'PT-TWO')
