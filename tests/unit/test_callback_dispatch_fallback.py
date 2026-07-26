"""回调分发兜底：未命中路由必须 answer + 告警，不能让按钮永久转圈。

背景：`can_handle` 的前缀判定比 `dispatch_context` 的 exact 表宽（例如 FilterCallbackHandler
用 `filter_` 前缀接单，但 exact 表里已删除死路由 `filter_none`）。缺口出现时旧实现静默
返回 False，callback_query.answer() 从未被调用 → Telegram 客户端按钮永久转圈且无日志。
"""

import pytest

from bot.handlers.callback_handlers.base import CallbackContext, CallbackHandler


class _Answerable:
    """记录 answer 调用的最小 CallbackQuery 替身。"""

    def __init__(self):
        self.answers = []

    def answer(self, text="", show_alert=False):
        self.answers.append((text, show_alert))


class _Handler(CallbackHandler):
    def can_handle(self, data: str) -> bool:
        return data.startswith("demo_")

    def handle(self, client, callback_query) -> None:  # pragma: no cover - 未在本测试使用
        raise NotImplementedError


def _context(data: str, callback_query) -> CallbackContext:
    return CallbackContext(
        client=None,
        callback_query=callback_query,
        data=data,
        chat_id=1,
        message_id=2,
        user_id="3",
    )


@pytest.fixture
def handler():
    return _Handler(bot=None, acc=None)


def test_unmatched_route_answers_and_warns(handler, caplog):
    """接单但无路由时：返回 False、回一句提示、并留下 warning 日志。"""
    query = _Answerable()

    with caplog.at_level("WARNING"):
        matched = handler.dispatch_context(_context("demo_removed", query), {"demo_alive": lambda ctx: None})

    assert matched is False
    assert query.answers == [("❌ 该操作已下线", True)]
    assert "demo_removed" in caplog.text


def test_exact_route_still_dispatches_without_fallback(handler):
    """命中 exact 路由时不得触发兜底回应。"""
    query = _Answerable()
    seen = []

    matched = handler.dispatch_context(_context("demo_alive", query), {"demo_alive": seen.append})

    assert matched is True
    assert len(seen) == 1
    assert query.answers == []


def test_prefix_route_still_dispatches_without_fallback(handler):
    """命中前缀路由时不得触发兜底回应。"""
    query = _Answerable()
    seen = []

    matched = handler.dispatch_context(
        _context("demo_pfx_42", query), None, (("demo_pfx_", seen.append),)
    )

    assert matched is True
    assert len(seen) == 1
    assert query.answers == []
