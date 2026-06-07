"""Helper functions for admin routes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PasswordChangeDeps:
    verify_user: Callable[[str, str], bool]
    update_password: Callable[[str, str], None]


@dataclass(frozen=True)
class PasswordChangeForm:
    username: str
    current_password: str
    new_password: str
    confirm_password: str


@dataclass(frozen=True)
class WebDAVSaveDeps:
    save_config: Callable[[Dict[str, Any]], None]
    init_storage_manager: Callable[[], Any]
    app: Any


def build_admin_context(
    note_service: Any,
    calibration_service: Any,
    must_change_password: bool,
) -> Dict[str, Any]:
    total_notes, total_sources, sources = _load_note_stats(note_service)
    calib_stats = _load_calibration_stats(calibration_service)
    return {
        "total_count": total_notes,
        "total_sources": total_sources,
        "calib_stats": calib_stats,
        "sources": sources,
        "must_change_password": must_change_password,
    }


def _load_note_stats(note_service: Any) -> tuple[int, int, list]:
    try:
        notes_result = note_service.get_notes(user_id=None, page_size=1)
        sources = note_service.get_all_sources()
        return notes_result.total, len(sources), sources
    except Exception as e:
        logger.error(f"获取笔记统计失败: {e}")
        return 0, 0, []


def _load_calibration_stats(calibration_service: Any) -> Dict[str, Any]:
    try:
        return calibration_service.get_stats()
    except Exception as e:
        logger.error(f"获取校准统计失败: {e}")
        return {"total": 0, "by_status": {}}


def read_password_change_form(form: Mapping[str, Any], username: str) -> PasswordChangeForm:
    return PasswordChangeForm(
        username=username,
        current_password=str(form.get("current_password") or ""),
        new_password=str(form.get("new_password") or ""),
        confirm_password=str(form.get("confirm_password") or ""),
    )


def change_password(change: PasswordChangeForm, deps: PasswordChangeDeps) -> Optional[str]:
    if not deps.verify_user(change.username, change.current_password):
        return "当前密码不正确"
    if len(change.new_password) < 6:
        return "新密码长度至少为 6 个字符"
    if change.new_password != change.confirm_password:
        return "两次输入的新密码不一致"
    deps.update_password(change.username, change.new_password)
    return None


def read_webdav_config(form: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "enabled": form.get("enabled") == "on",
        "url": str(form.get("url", "")).strip(),
        "username": str(form.get("webdav_username", "")).strip(),
        "password": str(form.get("webdav_password", "")).strip(),
        "base_path": str(form.get("base_path", "/telegram_media")).strip(),
        "keep_local_copy": form.get("keep_local_copy") == "on",
    }


def validate_webdav_config(config: Dict[str, Any], client_factory: Callable[..., Any]) -> Optional[str]:
    if not _should_test_webdav(config):
        return None
    try:
        client = client_factory(
            config["url"],
            config["username"],
            config["password"],
            config["base_path"],
        )
        if client.test_connection():
            return None
        return "WebDAV 连接测试失败，请检查配置"
    except Exception as e:
        return f"WebDAV 连接失败: {str(e)}"


def save_webdav_settings(config: Dict[str, Any], deps: WebDAVSaveDeps) -> None:
    deps.save_config(config)
    deps.app.storage_manager = deps.init_storage_manager()


def _should_test_webdav(config: Dict[str, Any]) -> bool:
    return bool(
        config.get("enabled")
        and config.get("url")
        and config.get("username")
        and config.get("password")
    )


def read_viewer_config(form: Mapping[str, Any]) -> Dict[str, str]:
    return {"viewer_url": str(form.get("viewer_url", "")).strip()}


def validate_viewer_config(config: Dict[str, str]) -> Optional[str]:
    viewer_url = config["viewer_url"]
    if not viewer_url:
        return "观看网站URL不能为空"
    if not (viewer_url.startswith("http://") or viewer_url.startswith("https://")):
        return "URL必须以 http:// 或 https:// 开头"
    return None
