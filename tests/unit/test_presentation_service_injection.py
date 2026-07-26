"""表现层不得做服务定位（报告 §5.3 规则 3 / §5.2 目标层序）。

背景：`bot/` 曾在 11 处、`web/` 曾在 5 处写 `from composition.container import
get_xxx()` 就地取服务，而 `composition/` 自身又 import `bot.services` /
`bot.storage` —— composition ⇄ 交付层的双向环，`.importlinter` 的层序契约因此
长期无法把 `composition` 纳入。

本文件钉三件事：
1. **静态**：`bot/`、`web/` 源码里不再出现对 `composition` 的 import。
   `lint-imports` 在 CI 里覆盖同一约束，但它不在 pytest 里跑；这条断言让
   「顺手加一句 import composition」在本地单测阶段就红。
2. **动态**：注入缺失时各注入点**立刻抛错**，而不是静默回落到全局容器
   （§5.3 规则 5）——静默回落会让「装配漏了」在生产上完全不可见。
3. **动态**：注入到位时，服务确实沿装配路径传到了终点（注册表 → 处理器）。
"""

from __future__ import annotations

import ast
import queue
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from bot.handlers.callback_handlers.base import CallbackHandler
from bot.handlers.callback_registry import CallbackRegistry
from bot.handlers.instances import set_acc_instance, set_bot_instance
from bot.runtime_services import BotServices
from bot.workers.message_worker import MessageWorker
from web import create_app
from web.services import WebServices, bind_services, get_services

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _imported_top_level_modules(source: Path) -> set[str]:
    """收集一个文件里所有 import 的顶层模块名（含函数内延迟 import）。"""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


@pytest.mark.parametrize("package", ["bot", "web"])
def test_presentation_packages_do_not_import_composition(package: str) -> None:
    offenders = [
        str(path.relative_to(PROJECT_ROOT))
        for path in sorted((PROJECT_ROOT / package).rglob("*.py"))
        if "composition" in _imported_top_level_modules(path)
    ]
    assert offenders == [], (
        f"{package}/ 重新出现了对组合根的 import（服务定位回归）：{offenders}；"
        "服务应由 main.py / app.py 经 BotServices / WebServices 注入"
    )


# ---------------------------------------------------------------------------
# bot 侧：回调处理器
# ---------------------------------------------------------------------------


class _StubHandler(CallbackHandler):
    def can_handle(self, data: str) -> bool:  # pragma: no cover - 本文件不分发
        return True

    def handle(self, client, callback_query) -> None:  # pragma: no cover
        raise NotImplementedError


def _services() -> BotServices:
    return BotServices(
        watch_service=SimpleNamespace(name="watch"),
        watch_setup_service=SimpleNamespace(name="watch_setup"),
        message_worker_service=SimpleNamespace(name="worker"),
        calibration_manager=SimpleNamespace(name="calibration"),
    )


def test_callback_handler_without_injection_fails_loudly() -> None:
    handler = _StubHandler(bot=None, acc=None)

    with pytest.raises(RuntimeError, match="未注入 BotServices"):
        handler.watch_service


def test_callback_handler_uses_injected_services() -> None:
    services = _services()
    handler = _StubHandler(bot=None, acc=None, services=services)

    assert handler.watch_service is services.watch_service
    assert handler.watch_setup_service is services.watch_setup_service


def test_registry_propagates_services_to_handlers() -> None:
    registry = CallbackRegistry()
    services = _services()

    set_bot_instance("bot-x")
    set_acc_instance("acc-x")
    registry.bind_services(services)
    registry.initialize(force=True)

    assert registry.handlers, "注册表未构造任何处理器"
    for handler in registry.handlers:
        assert handler.watch_service is services.watch_service


def test_registry_rebuilds_handlers_when_services_change() -> None:
    registry = CallbackRegistry()
    set_bot_instance("bot-x")
    set_acc_instance("acc-x")

    first = _services()
    registry.bind_services(first)
    registry.initialize(force=True)

    second = _services()
    registry.bind_services(second)
    assert registry._should_reinitialize("bot-x", "acc-x") is True


# ---------------------------------------------------------------------------
# bot 侧：消息 worker
# ---------------------------------------------------------------------------


def test_message_worker_without_injection_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MessageWorker, "_init_storage_manager", lambda self: None)
    worker = MessageWorker(queue.Queue(), None)

    with pytest.raises(RuntimeError, match="MessageWorkerService"):
        worker._message_service
    with pytest.raises(RuntimeError, match="WatchService"):
        worker._watch_service


def test_message_worker_uses_injected_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MessageWorker, "_init_storage_manager", lambda self: None)
    message_service = SimpleNamespace(name="worker")
    watch_service = SimpleNamespace(name="watch")

    worker = MessageWorker(
        queue.Queue(),
        None,
        message_service=message_service,
        watch_service=watch_service,
    )

    assert worker._message_service is message_service
    assert worker._watch_service is watch_service


# ---------------------------------------------------------------------------
# web 侧：应用工厂
# ---------------------------------------------------------------------------


def _web_services() -> WebServices:
    return WebServices(
        note_service=SimpleNamespace(name="note"),
        calibration_service=SimpleNamespace(name="calibration"),
        calibration_workflow_service=SimpleNamespace(name="workflow"),
        qbittorrent_service=SimpleNamespace(name="qbt"),
        reload_calibration_config=lambda: None,
    )


def test_create_app_requires_services() -> None:
    """工厂没有「自己去容器里取」的默认值——否则服务定位只是被藏进了工厂。"""
    with pytest.raises(TypeError, match="services"):
        create_app()  # type: ignore[call-arg]


def test_get_services_without_binding_fails_loudly() -> None:
    app = Flask(__name__)

    with app.app_context():
        with pytest.raises(RuntimeError, match="未绑定 WebServices"):
            get_services()


def test_get_services_returns_bound_bundle() -> None:
    app = Flask(__name__)
    services = _web_services()
    bind_services(app, services)

    with app.app_context():
        assert get_services() is services
