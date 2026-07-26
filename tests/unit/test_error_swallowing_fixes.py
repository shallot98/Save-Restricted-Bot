"""吞错点修复的回归测试（报告 §3 P1-5）。

每个用例锁定一条「失败方向」：损坏数据不得被静默放行/静默丢弃。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from flask import Flask

from bot.handlers.callback_registry import CallbackRegistry
from bot.handlers.instances import get_acc_instance, get_bot_instance
from bot.storage.webdav_client import StorageManager
from bot.utils.helpers import UNSUPPORTED_MESSAGE_TYPE, get_message_type
from src.domain.entities.watch import WatchTask
from src.domain.services.filter_service import FilterService
from src.infrastructure.persistence.repositories.sqlite_watch_repository_helpers import (
    _parse_dict_watch_task,
    parse_config_dict,
    row_to_task,
)
from web.routes.media import media_bp


def test_bad_task_does_not_drop_other_tasks_of_same_user(caplog) -> None:
    """P1-5 #1: 单条任务损坏只跳过该条，同用户其余任务保留且有 error 日志。

    原报告点名的是 ``json_watch_repository_helpers``，但那条链路随
    ``JSONWatchRepository`` 死实现一并删除；生产唯一在用的解析入口是
    ``SQLiteWatchRepository.save_config_dict`` → ``parse_config_dict``，
    本用例改钉这一条。
    """
    config_dict = {"42": {"good": {"source": "-100", "dest": "-200"}, "": {"source": ""}}}
    with caplog.at_level(logging.ERROR):
        parsed = parse_config_dict(config_dict)

    assert set(parsed) == {"42"}
    assert set(parsed["42"].tasks) == {"-100|-200"}
    assert any("跳过无法解析的监控任务" in record.message for record in caplog.records)


def test_corrupt_blacklist_blocks_forwarding(caplog) -> None:
    """P1-5 #2: 黑名单 JSON 损坏时任务被标记损坏，转发方向为「拒绝」。"""
    row = {"user_id": "42", "watch_key": "k", "source_id": "-100", "blacklist_json": "{not json"}
    with caplog.at_level(logging.ERROR):
        task = row_to_task(row)

    assert task.filters_corrupt is True
    assert FilterService.should_forward(task, "anything") is False
    assert any("过滤器数据损坏" in record.message for record in caplog.records)


def test_invalid_regex_is_logged_once(caplog) -> None:
    """P1-5 #3: 非法正则被跳过但必须留下含 pattern 原文的 error 日志。"""
    import src.domain.services.filter_service as filter_module

    filter_module._reported_invalid_patterns.clear()
    task = WatchTask(source="s", dest=None, blacklist_regex=["[unclosed"])
    with caplog.at_level(logging.ERROR):
        assert FilterService.should_forward(task, "text") is True
        FilterService.should_forward(task, "text again")

    invalid_logs = [r for r in caplog.records if "非法正则表达式" in r.message]
    assert len(invalid_logs) == 1
    assert "[unclosed" in invalid_logs[0].getMessage()


def test_callback_error_does_not_leak_exception_text() -> None:
    """P1-5 #4: 处理器异常原文不得回传到 Telegram 弹窗。"""
    answered: list[str] = []

    class _Handler:
        def can_handle(self, _data: str) -> bool:
            return True

        def handle(self, _client, _query) -> None:
            raise RuntimeError("/app/data/secret.db chat_id=12345")

    class _Query:
        data = "x"

        def answer(self, text: str, show_alert: bool = False) -> None:
            answered.append(text)

    registry = CallbackRegistry()
    registry.handlers = [_Handler()]
    registry._initialized = True
    registry._bound_bot = get_bot_instance()
    registry._bound_acc = get_acc_instance()

    assert registry.dispatch(None, _Query()) is False
    assert answered == ["❌ 操作失败，请稍后重试"]


def test_incompatible_task_skip_is_logged(caplog) -> None:
    """P1-5 #5: 字段不兼容的单条任务跳过时必须带任务标识记日志。"""
    with caplog.at_level(logging.ERROR):
        assert _parse_dict_watch_task("", {"source": "", "dest": "-200"}) is None

    assert any("跳过无法解析的监控任务" in r.message for r in caplog.records)


def test_media_error_response_hides_path(tmp_path: Path, caplog) -> None:
    """P1-5 #6: 媒体路由异常不得把绝对路径回给浏览器，服务端必须留日志。"""

    class _BoomStorage(StorageManager):
        def get_file_path(self, storage_location: str) -> str:
            raise OSError(f"[Errno 2] No such file: {tmp_path}/media/secret.mp4")

    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.storage_manager = _BoomStorage(str(tmp_path))
    app.register_blueprint(media_bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session["username"] = "test"

    with caplog.at_level(logging.ERROR):
        response = client.get("/media/local%3Aa.mp4")

    assert response.status_code == 500
    assert str(tmp_path).encode() not in response.data
    assert any("媒体请求处理失败" in r.message for r in caplog.records)


def test_unknown_message_type_is_explicit() -> None:
    """P1-5 #7: 投票之类的消息不再被伪装成 "Text"。"""

    class _Poll:
        id = 7
        text = None
        poll = object()

    assert get_message_type(_Poll()) == UNSUPPORTED_MESSAGE_TYPE


def test_get_message_type_keeps_known_types() -> None:
    """P1-5 #7 兼容性：已知类型的返回值保持不变。"""

    class _Photo:
        text = None

        class photo:
            file_id = "abc"

    class _Text:
        text = "hello"

    assert get_message_type(_Photo()) == "Photo"
    assert get_message_type(_Text()) == "Text"


@pytest.mark.parametrize("payload", [{}, {"source": "   "}])
def test_watch_task_requires_source(payload: dict) -> None:
    """source 缺失/空白必须显式报错，而不是构造出无来源的任务。"""
    with pytest.raises(ValueError):
        WatchTask.from_dict(payload)
