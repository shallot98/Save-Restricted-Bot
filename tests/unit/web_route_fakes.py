"""`web/routes/*` 单测的手写替身与应用装配helper。

为什么是手写替身而不是 `unittest.mock`
--------------------------------------
沿用仓内既有的高质量样本（`test_history_copy_runtime.py`）：`Mock` 对任何属性都
返回一个新 Mock，路由把 DTO 字段拼进模板/JSON 时不会失败，于是「路由传错了参数」
这类回归照样绿灯。手写替身把每次调用**记录成可断言的元组**，并对未预期的调用直接
抛错，断言才落在参数与状态上，而不是「返回了 200」。

为什么能建整个 app
------------------
`create_app(..., infrastructure=...)` 是本轮开的缝（`web/__init__.py`）。在此之前
工厂构造期无条件 `init_database()`（真写 `data/notes.db`）+ `init_storage_manager()`
（真连 WebDAV），所以 `web/routes` 的写路径一直只能 0% 覆盖（报告 §3 P1-6）。
现在测试注入一对 no-op / 临时目录实现，就能走完包含 CSRF、安全头、服务绑定、
Jinja 过滤器在内的**真实**工厂路径。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from flask import Flask

from bot.storage.webdav_client import StorageManager
from src.application.dto import NoteDTO, PaginatedResult
from src.core.exceptions import NotFoundError
from web import WebInfrastructure, create_app
from web.services import WebServices

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def make_note(note_id: int = 1, **overrides: Any) -> NoteDTO:
    """构造一条形状与生产一致的 NoteDTO。"""
    fields: dict[str, Any] = {
        "id": note_id,
        "user_id": 42,
        "source_chat_id": "-100123",
        "source_name": "测试频道",
        "message_text": "hello magnet:?xt=urn:btih:AAAA&dn=demo.mp4",
        "timestamp": "2026-07-26 10:00:00",
        "media_type": None,
        "media_path": None,
        "media_paths": [],
        "magnet_link": "magnet:?xt=urn:btih:AAAA&dn=demo.mp4",
        "filename": "demo.mp4",
        "is_favorite": False,
    }
    fields.update(overrides)
    return NoteDTO(**fields)


class _Recorder:
    """记录调用序列；子类用 `self._record("name", ...)` 登记。"""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, *args))

    def call_names(self) -> list[str]:
        return [call[0] for call in self.calls]

    def calls_named(self, name: str) -> list[tuple]:
        return [call for call in self.calls if call[0] == name]


class FakeNoteService(_Recorder):
    """`NoteService` 中被 `web/routes` 实际调用的那 6 个方法。"""

    def __init__(
        self,
        notes: Optional[dict[int, NoteDTO]] = None,
        sources: Optional[list[dict]] = None,
        total: Optional[int] = None,
    ) -> None:
        super().__init__()
        self.notes: dict[int, NoteDTO] = dict(notes or {})
        self.sources = sources if sources is not None else [
            {"source_chat_id": "-100123", "source_name": "测试频道", "count": 1}
        ]
        self._total = total
        #: 置为异常实例时，写方法抛出它（用于覆盖 500 分支）
        self.raise_on_write: Optional[BaseException] = None
        #: 置为异常实例时，列表/来源查询抛出它（用于覆盖统计兜底分支）
        self.raise_on_read: Optional[BaseException] = None

    def get_notes(self, **kwargs: Any) -> PaginatedResult:
        self._record("get_notes", kwargs)
        if self.raise_on_read is not None:
            raise self.raise_on_read
        items = list(self.notes.values())
        return PaginatedResult(
            items=items,
            total=self._total if self._total is not None else len(items),
            page=kwargs.get("page") or 1,
            page_size=kwargs.get("page_size") or 20,
        )

    def get_all_sources(self) -> list[dict]:
        self._record("get_all_sources")
        if self.raise_on_read is not None:
            raise self.raise_on_read
        return self.sources

    def get_note(self, note_id: int) -> NoteDTO:
        self._record("get_note", note_id)
        return self._require(note_id)

    def update_text(self, note_id: int, text: str) -> None:
        self._record("update_text", note_id, text)
        self._raise_if_configured()
        note = self._require(note_id)
        note.message_text = text

    def delete_note(self, note_id: int) -> None:
        self._record("delete_note", note_id)
        self._raise_if_configured()
        self._require(note_id)
        del self.notes[note_id]

    def toggle_favorite(self, note_id: int) -> bool:
        self._record("toggle_favorite", note_id)
        self._raise_if_configured()
        note = self._require(note_id)
        note.is_favorite = not note.is_favorite
        return note.is_favorite

    def _require(self, note_id: int) -> NoteDTO:
        note = self.notes.get(note_id)
        if note is None:
            raise NotFoundError("笔记不存在", resource_type="note", resource_id=note_id)
        return note

    def _raise_if_configured(self) -> None:
        if self.raise_on_write is not None:
            raise self.raise_on_write


@dataclass
class FakeCalibrationConfig:
    data: dict

    def to_dict(self) -> dict:
        return dict(self.data)


@dataclass
class FakeCalibrationTask:
    data: dict

    def to_dict(self) -> dict:
        return dict(self.data)


class FakeCalibrationService(_Recorder):
    """`CalibrationService` 中被 admin / api 路由调用的方法。"""

    def __init__(self) -> None:
        super().__init__()
        self.config = FakeCalibrationConfig({"enabled": 1, "filter_mode": "empty_only"})
        self.stats: dict[str, Any] = {"total": 3, "by_status": {"pending": 1, "completed": 2}}
        self.tasks: list[FakeCalibrationTask] = []
        self.retry_result = True
        self.delete_result = True
        self.raise_on: Optional[BaseException] = None

    def schedule_retry(self, task_id: int) -> bool:
        self._record("schedule_retry", task_id)
        self._maybe_raise()
        return self.retry_result

    def delete_task(self, task_id: int) -> bool:
        self._record("delete_task", task_id)
        self._maybe_raise()
        return self.delete_result

    def get_stats(self) -> dict:
        self._record("get_stats")
        return self.stats

    def get_config(self) -> FakeCalibrationConfig:
        self._record("get_config")
        return self.config

    def update_config(self, data: dict) -> None:
        self._record("update_config", data)
        self._maybe_raise()
        self.config = FakeCalibrationConfig(dict(data))

    def list_all(self, status: Optional[str] = None, limit: int = 50, offset: int = 0):
        self._record("list_all", status, limit, offset)
        return self.tasks

    def _maybe_raise(self) -> None:
        if self.raise_on is not None:
            raise self.raise_on


class FakeCalibrationWorkflowService(_Recorder):
    """返回值形状与真实服务一致：三元组 / 二元组 / dict。"""

    def __init__(self) -> None:
        super().__init__()
        self.note_result: tuple[Optional[dict], Optional[str], int] = (
            {"success": True, "updated": 1},
            None,
            200,
        )
        self.info_hash_result: tuple[Optional[str], Optional[str]] = ("calibrated.mkv", None)
        self.batch_result: dict[str, Any] = {"success": True, "total": 5}
        self.raise_on: Optional[BaseException] = None

    def calibrate_note(self, note_id: int):
        self._record("calibrate_note", note_id)
        if self.raise_on is not None:
            raise self.raise_on
        return self.note_result

    def calibrate_info_hash_filename(self, info_hash: str):
        self._record("calibrate_info_hash_filename", info_hash)
        return self.info_hash_result

    def batch_schedule_recent_notes(self, count: int, force: bool) -> dict:
        self._record("batch_schedule_recent_notes", count, force)
        if self.raise_on is not None:
            raise self.raise_on
        return self.batch_result


class FakeQBittorrentService(_Recorder):
    def __init__(self) -> None:
        super().__init__()
        self.add_result: tuple[dict, int] = ({"success": True, "info_hash": "AAAA"}, 200)
        self.status_result: tuple[dict, int] = ({"success": True, "progress": 0.5}, 200)
        self.raise_on: Optional[BaseException] = None

    def add_note_download(self, note_dto: NoteDTO, magnet_index: Any):
        self._record("add_note_download", note_dto.id, magnet_index)
        if self.raise_on is not None:
            raise self.raise_on
        return self.add_result

    def get_download_status(self, info_hash: str):
        self._record("get_download_status", info_hash)
        if self.raise_on is not None:
            raise self.raise_on
        return self.status_result


@dataclass
class RouteTestBed:
    """一次装配产出的全部句柄，测试用它断言状态变化。"""

    app: Flask
    note_service: FakeNoteService
    calibration_service: FakeCalibrationService
    workflow_service: FakeCalibrationWorkflowService
    qbittorrent_service: FakeQBittorrentService
    reload_calls: list[str] = field(default_factory=list)

    def client(self, *, logged_in: bool = True, must_change_password: bool = False):
        client = self.app.test_client()
        if logged_in:
            login(client, must_change_password=must_change_password)
        return client


CSRF_TOKEN = "test-csrf-token"


def login(client, *, username: str = "admin", must_change_password: bool = False) -> None:
    """写入登录态与 CSRF token。

    直接写 session 而不是走 `/login`：登录流程本身已有
    `test_web_security_baseline.py` 覆盖，这里要测的是登录后的路由。
    """
    with client.session_transaction() as session:
        session["username"] = username
        session["_csrf_token"] = CSRF_TOKEN
        if must_change_password:
            session["must_change_password"] = True


def csrf_headers() -> dict[str, str]:
    return {"X-CSRFToken": CSRF_TOKEN}


def build_testbed(tmp_path: Path, note_service: Optional[FakeNoteService] = None) -> RouteTestBed:
    """用真实 `create_app()` 建 app，只把两处构造期副作用换成测试实现。"""
    calibration_service = FakeCalibrationService()
    workflow_service = FakeCalibrationWorkflowService()
    qbittorrent_service = FakeQBittorrentService()
    notes = note_service if note_service is not None else FakeNoteService({1: make_note(1)})
    reload_calls: list[str] = []

    services = WebServices(
        note_service=notes,  # type: ignore[arg-type]
        calibration_service=calibration_service,  # type: ignore[arg-type]
        calibration_workflow_service=workflow_service,  # type: ignore[arg-type]
        qbittorrent_service=qbittorrent_service,  # type: ignore[arg-type]
        reload_calibration_config=lambda: reload_calls.append("reload"),
    )

    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    infrastructure = WebInfrastructure(
        # 单测绝不能触碰运维的真实 data/notes.db —— 建库在这里被显式钉成 no-op
        init_database=_noop_init_database,
        init_storage_manager=lambda: StorageManager(str(media_dir)),
    )

    app = create_app({"TESTING": True}, services=services, infrastructure=infrastructure)
    return RouteTestBed(
        app=app,
        note_service=notes,
        calibration_service=calibration_service,
        workflow_service=workflow_service,
        qbittorrent_service=qbittorrent_service,
        reload_calls=reload_calls,
    )


def make_calibration_task(**overrides: Any) -> FakeCalibrationTask:
    """键集与 `src.domain.entities.calibration.CalibrationTask.to_dict()` 保持一致。

    模板直接对这些键做切片（`task.magnet_hash[:12]`），键名对不上会在渲染期炸，
    所以这里刻意不做「随便给几个字段」的省事写法。
    """
    data: dict[str, Any] = {
        "id": 1,
        "note_id": 1,
        "magnet_hash": "AAAABBBBCCCCDDDD",
        "status": "pending",
        "retry_count": 0,
        "last_attempt": None,
        "next_attempt": "2026-07-26 10:10:00",
        "error_message": None,
        "created_at": "2026-07-26 10:00:00",
    }
    data.update(overrides)
    return FakeCalibrationTask(data)


def _noop_init_database() -> None:
    return None
