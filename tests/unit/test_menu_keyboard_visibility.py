from __future__ import annotations

from types import SimpleNamespace

import bot.handlers.callback_handlers.menu_handler as menu_module
from bot.handlers.callback_handlers.menu_handler import MenuCallbackHandler
from bot.handlers.commands import register_command_handlers


class _DummyBot:
    def __init__(self) -> None:
        self.edits: list[dict] = []
        self.sent: list[dict] = []
        self.handlers: list = []

    def edit_message_text(self, chat_id, message_id, text, reply_markup=None) -> None:
        self.edits.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )

    def send_message(self, chat_id, text, reply_markup=None, reply_to_message_id=None) -> None:
        self.sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
                "reply_to_message_id": reply_to_message_id,
            }
        )

    def on_message(self, _filters):
        def decorator(func):
            self.handlers.append(func)
            return func

        return decorator


class _DummyCallbackQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = SimpleNamespace(chat=SimpleNamespace(id=1001), id=2002)
        self.from_user = SimpleNamespace(id=3003, mention="tester")

    def answer(self, *_args, **_kwargs) -> None:
        return None


def _callback_data(markup) -> list[str]:
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if getattr(button, "callback_data", None)
    ]


class _DummyManager:
    def count_user_tasks(self, _user_id: str) -> int:
        return 2

    def count_enabled_user_tasks(self, _user_id: str) -> int:
        return 1

    def list_user_tasks(self, _user_id: str):
        return [
            SimpleNamespace(
                enabled=True,
                source_name="源群A",
                target_bot_name="目标BotA",
                task_id="task-1",
                chat_name="签到群A",
                message_text="司机人签到",
            )
        ]


class _DummyHistoryCopyManager:
    def count_user_tasks(self, _user_id: str) -> int:
        return 3

    def count_running_user_tasks(self, _user_id: str) -> int:
        return 1


def test_menu_handler_hides_watch_entries(monkeypatch) -> None:
    monkeypatch.setattr(menu_module, "get_pt_pay_monitor_manager", lambda: _DummyManager())
    monkeypatch.setattr(menu_module, "get_scheduled_signin_manager", lambda: _DummyManager())
    monkeypatch.setattr(menu_module, "get_history_copy_task_manager", lambda: _DummyHistoryCopyManager())

    bot = _DummyBot()
    handler = MenuCallbackHandler(bot, acc=object())

    handler.handle(None, _DummyCallbackQuery("menu_main"))
    main_edit = bot.edits[-1]
    assert "menu_watch" not in _callback_data(main_edit["reply_markup"])
    assert "脚本模式" in main_edit["text"]

    handler.handle(None, _DummyCallbackQuery("menu_help"))
    help_edit = bot.edits[-1]
    assert "menu_watch" not in _callback_data(help_edit["reply_markup"])
    assert "监控功能" not in help_edit["text"]

    handler.handle(None, _DummyCallbackQuery("menu_script"))
    script_edit = bot.edits[-1]
    script_callbacks = _callback_data(script_edit["reply_markup"])
    assert "menu_watch" not in script_callbacks
    assert "menu_script_pt" in script_callbacks
    assert "menu_script_signin" in script_callbacks
    assert "menu_script_history_copy" in script_callbacks
    assert "script_view_task-1" not in script_callbacks
    assert "signin_view_task-1" not in script_callbacks
    assert "先选择脚本类型" in script_edit["text"]

    handler.handle(None, _DummyCallbackQuery("menu_script_pt"))
    pt_edit = bot.edits[-1]
    pt_callbacks = _callback_data(pt_edit["reply_markup"])
    assert "script_add_start" in pt_callbacks
    assert "script_list" in pt_callbacks
    assert "menu_script" in pt_callbacks
    assert "PT 联动脚本" in pt_edit["text"]

    handler.handle(None, _DummyCallbackQuery("menu_script_signin"))
    signin_edit = bot.edits[-1]
    signin_callbacks = _callback_data(signin_edit["reply_markup"])
    assert "signin_add_start" in signin_callbacks
    assert "signin_list" in signin_callbacks
    assert "menu_script" in signin_callbacks
    assert "定时签到脚本" in signin_edit["text"]

    handler.handle(None, _DummyCallbackQuery("menu_script_history_copy"))
    history_edit = bot.edits[-1]
    history_callbacks = _callback_data(history_edit["reply_markup"])
    assert "history_copy_add_start" in history_callbacks
    assert "history_copy_list" in history_callbacks
    assert "menu_script" in history_callbacks
    assert "历史复制" in history_edit["text"]


def test_start_and_help_commands_hide_watch_entries(monkeypatch) -> None:
    bot = _DummyBot()
    import bot.handlers.commands as commands_module

    monkeypatch.setattr(
        commands_module,
        "get_history_copy_task_manager",
        lambda: _DummyHistoryCopyManager(),
    )
    register_command_handlers(bot, acc=object())

    message = SimpleNamespace(
        chat=SimpleNamespace(id=1001),
        from_user=SimpleNamespace(mention="tester"),
        id=2002,
    )

    start_handler = bot.handlers[0]
    help_handler = bot.handlers[1]

    start_handler(None, message)
    start_message = bot.sent[-1]
    assert "menu_watch" not in _callback_data(start_message["reply_markup"])
    assert "脚本模式" in start_message["text"]

    help_handler(None, message)
    help_message = bot.sent[-1]
    assert "menu_watch" not in _callback_data(help_message["reply_markup"])
    assert "监控功能" not in help_message["text"]
    assert "历史复制" in help_message["text"]
