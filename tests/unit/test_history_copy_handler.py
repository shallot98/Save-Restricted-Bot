from __future__ import annotations

from types import SimpleNamespace

import bot.handlers.callback_handlers.history_copy_handler as history_module
from bot.handlers.callback_handlers.history_copy_handler import HistoryCopyCallbackHandler


class _DummyBot:
    def __init__(self, raise_not_modified: bool = False) -> None:
        self.raise_not_modified = raise_not_modified
        self.edits: list[dict] = []

    def edit_message_text(self, chat_id, message_id, text, reply_markup=None) -> None:
        self.edits.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )
        if self.raise_not_modified:
            raise RuntimeError(
                'Telegram says: [400 MESSAGE_NOT_MODIFIED] - The message was not modified'
            )


class _DummyCallbackQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = SimpleNamespace(chat=SimpleNamespace(id=1001), id=2002)
        self.from_user = SimpleNamespace(id=3003)
        self.answers: list[dict] = []

    def answer(self, text: str = "", show_alert: bool = False) -> None:
        self.answers.append({"text": text, "show_alert": show_alert})


class _DummyManager:
    def __init__(self, task) -> None:
        self.task = task
        self.restarted: list[tuple[str, str]] = []

    def get_user_task(self, _user_id: str, _task_id: str):
        return self.task

    def restart_task(self, user_id: str, task_id: str):
        self.restarted.append((user_id, task_id))
        self.task = _task("running")
        return self.task


def _task(status: str = "running"):
    return SimpleNamespace(
        task_id="task-1",
        source_name="源群",
        source_chat_ref="@src",
        source_chat_id="-100111",
        dest_name="目标群",
        dest_chat_ref="@dst",
        dest_chat_id="-100222",
        history_limit=100,
        status=status,
        state_db_path="data/history_copy_state/test.db",
        started_at=1.0,
        finished_at=2.0 if status != "running" else 0.0,
        status_message="scanned=10 copied=8 skipped=1 failed=1",
        scanned_count=10,
        copied_count=8,
        skipped_count=1,
        failed_count=1,
        error_message="RuntimeError: boom" if status == "failed" else "",
    )


def test_refresh_ignores_message_not_modified(monkeypatch) -> None:
    bot = _DummyBot(raise_not_modified=True)
    callback = _DummyCallbackQuery("history_copy_view_task-1")
    monkeypatch.setattr(history_module, "get_history_copy_task_manager", lambda: _DummyManager(_task()))

    handler = HistoryCopyCallbackHandler(bot, acc=object())
    handler.handle(None, callback)

    assert callback.answers[-1]["text"] == "状态未变化"
    assert callback.answers[-1]["show_alert"] is False


def test_render_detail_returns_true_when_message_changes(monkeypatch) -> None:
    bot = _DummyBot()
    callback = _DummyCallbackQuery("history_copy_view_task-1")
    monkeypatch.setattr(history_module, "get_history_copy_task_manager", lambda: _DummyManager(_task("completed")))

    handler = HistoryCopyCallbackHandler(bot, acc=object())
    handler.handle(None, callback)

    assert bot.edits
    assert callback.answers[-1]["text"] == ""


def test_failed_task_detail_shows_restart_button(monkeypatch) -> None:
    bot = _DummyBot()
    callback = _DummyCallbackQuery("history_copy_view_task-1")
    monkeypatch.setattr(history_module, "get_history_copy_task_manager", lambda: _DummyManager(_task("failed")))

    handler = HistoryCopyCallbackHandler(bot, acc=object())
    handler.handle(None, callback)

    keyboard = bot.edits[-1]["reply_markup"]
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "▶️ 重启任务" in button_texts


def test_restart_callback_restarts_stopped_task(monkeypatch) -> None:
    bot = _DummyBot()
    callback = _DummyCallbackQuery("history_copy_restart_task-1")
    manager = _DummyManager(_task("interrupted"))
    monkeypatch.setattr(history_module, "get_history_copy_task_manager", lambda: manager)

    handler = HistoryCopyCallbackHandler(bot, acc=object())
    handler.handle(None, callback)

    assert manager.restarted == [("3003", "task-1")]
    assert "状态：🟡 运行中" in bot.edits[-1]["text"]
    assert callback.answers[-1]["text"] == "✅ 已重启"
