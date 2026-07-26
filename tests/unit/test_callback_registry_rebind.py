"""
Unit tests for callback registry rebind behavior.
"""

from __future__ import annotations

from bot.handlers.callback_registry import CallbackRegistry
from bot.handlers.instances import set_bot_instance, set_acc_instance


class _DummyHandler:
    def __init__(self, bot, acc, *, services=None):
        self.bot = bot
        self.acc = acc
        self.services = services

    def can_handle(self, _data: str) -> bool:
        return True

    def handle(self, _client, _callback_query) -> None:
        return None


class _DummyCallbackQuery:
    def __init__(self) -> None:
        self.data = "dummy"

    def answer(self, *_args, **_kwargs) -> None:
        return None


def test_callback_registry_rebinds_on_instance_change(monkeypatch) -> None:
    import bot.handlers.callback_registry as registry_module

    monkeypatch.setattr(registry_module, "MenuCallbackHandler", _DummyHandler)
    monkeypatch.setattr(registry_module, "WatchCallbackHandler", _DummyHandler)
    monkeypatch.setattr(registry_module, "FilterCallbackHandler", _DummyHandler)
    monkeypatch.setattr(registry_module, "EditCallbackHandler", _DummyHandler)
    monkeypatch.setattr(registry_module, "ModeCallbackHandler", _DummyHandler)
    monkeypatch.setattr(registry_module, "ScriptCallbackHandler", _DummyHandler)
    monkeypatch.setattr(registry_module, "SigninCallbackHandler", _DummyHandler)
    monkeypatch.setattr(registry_module, "HistoryCopyCallbackHandler", _DummyHandler)

    registry = CallbackRegistry()
    query = _DummyCallbackQuery()

    set_bot_instance("bot-1")
    set_acc_instance("acc-1")
    assert registry.dispatch(None, query) is True
    assert registry.handlers[0].bot == "bot-1"

    set_bot_instance("bot-2")
    set_acc_instance("acc-2")
    assert registry.dispatch(None, query) is True
    assert registry.handlers[0].bot == "bot-2"
