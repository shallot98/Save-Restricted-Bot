from __future__ import annotations

from types import SimpleNamespace

from bot.handlers import script_setup
from bot.utils.status import user_states


class FakeBot:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent_messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        return SimpleNamespace(id=999)


class FakeManager:
    def __init__(self):
        self.calls = []

    def add_task(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            task_id="task-1",
            source_name=kwargs["source_name"],
            target_bot_name=kwargs["target_bot_name"],
            target_bot_ref=kwargs["target_bot_ref"],
        )


def test_handle_script_add_target_allows_non_bot_targets(monkeypatch):
    fake_bot = FakeBot()
    fake_manager = FakeManager()
    captured = {}

    def fake_resolve(message, allow_saved_messages, require_bot):
        captured["allow_saved_messages"] = allow_saved_messages
        captured["require_bot"] = require_bot
        return ("123456", "好友A", "@friend_a")

    monkeypatch.setattr(script_setup, "get_bot_instance", lambda: fake_bot)
    monkeypatch.setattr(script_setup, "get_pt_pay_monitor_manager", lambda: fake_manager)
    monkeypatch.setattr(script_setup, "_resolve_chat_input", fake_resolve)

    user_id = "42"
    user_states[user_id] = {
        "script_source_chat_id": "-1001",
        "script_source_name": "测试群",
    }

    message = SimpleNamespace(chat=SimpleNamespace(id=42), text="@friend_a")
    try:
        script_setup.handle_script_add_target_bot(message, user_id)
    finally:
        if user_id in user_states:
            del user_states[user_id]

    assert captured == {"allow_saved_messages": False, "require_bot": False}
    assert fake_manager.calls[0]["target_bot_name"] == "好友A"
    assert fake_manager.calls[0]["target_bot_ref"] == "@friend_a"
    assert "目标对象" in fake_bot.sent_messages[-1]["text"]
