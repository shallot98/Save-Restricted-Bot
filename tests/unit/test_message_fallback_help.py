from __future__ import annotations

from types import SimpleNamespace

import bot.handlers.messages as messages_module
from bot.runtime_services import BotServices


class _DummyBot:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_message(self, chat_id, text, reply_markup=None, reply_to_message_id=None) -> None:
        self.sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
                "reply_to_message_id": reply_to_message_id,
            }
        )


def _callback_data(markup) -> list[str]:
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if getattr(button, "callback_data", None)
    ]


def test_save_replies_with_help_for_unknown_private_text(monkeypatch) -> None:
    bot = _DummyBot()
    monkeypatch.setattr(messages_module, "get_bot_instance", lambda: bot)
    monkeypatch.setattr(messages_module, "get_acc_instance", lambda: None)
    monkeypatch.setattr(messages_module, "get_business_metrics", lambda: None)

    message = SimpleNamespace(
        text="你好",
        chat=SimpleNamespace(id=1001),
        from_user=SimpleNamespace(id=2002),
        id=3003,
    )

    # save() 现在要求显式注入服务；本用例走的是「未识别文本」分支，不触达服务。
    services = BotServices(
        watch_service=object(),
        watch_setup_service=object(),
        message_worker_service=object(),
        calibration_manager=object(),
    )
    messages_module.save(None, message, services=services)

    assert len(bot.sent) == 1
    payload = bot.sent[0]
    assert "未识别的消息内容" in payload["text"]
    assert payload["reply_to_message_id"] == 3003
    callbacks = _callback_data(payload["reply_markup"])
    assert "menu_script" in callbacks
    assert "menu_help" in callbacks
