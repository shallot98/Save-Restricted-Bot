"""`web/routes/api.py` 的路由级测试（报告 §3 P1-6：该文件此前 158 语句 0%）。

重点之一是 `/api/calibrate/async` 的 info_hash 分支回归：该分支曾写成
``kwargs={'info_hash': ...}``，被 ``submit_task(**kwargs)`` 再包一层后，任务函数
收到的是 ``kwargs=<dict>``，必然 TypeError（前端只看到任务 FAILED，没有任何请求
层面的报错）。这里的替身管理器**同步执行**任务函数并把异常暴露出来，正是为了让
那种包装错误在单测里直接红。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from bot.services.async_calibration_manager import CalibrationTask, TaskStatus
from src.core.exceptions import NotFoundError
from unit.web_route_fakes import RouteTestBed, build_testbed, csrf_headers


class FakeAsyncManager:
    """同步执行版的 `AsyncCalibrationManager`，契约与真实实现一致。

    `submit_task(info_hash, func, *args, **kwargs)` → 立即 `func(*args, **kwargs)`，
    因此路由若把参数多包一层 dict，这里就会 TypeError 而不是悄悄变成 FAILED。
    """

    def __init__(self) -> None:
        self.submissions: list[tuple[str, tuple, dict]] = []
        self.tasks: dict[str, CalibrationTask] = {}
        self.next_task_id = "task-1"

    def submit_task(
        self,
        info_hash: str,
        calibration_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> str:
        self.submissions.append((info_hash, args, kwargs))
        result, error = calibration_func(*args, **kwargs)
        task = CalibrationTask(
            task_id=self.next_task_id,
            info_hash=info_hash,
            status=TaskStatus.COMPLETED if result is not None else TaskStatus.FAILED,
            result=result,
            error=error,
            created_at=1.0,
            completed_at=2.0,
        )
        self.tasks[task.task_id] = task
        return task.task_id

    def get_task_status(self, task_id: str) -> Optional[CalibrationTask]:
        return self.tasks.get(task_id)


@pytest.fixture
def bed(tmp_path: Path) -> RouteTestBed:
    return build_testbed(tmp_path)


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch) -> FakeAsyncManager:
    fake = FakeAsyncManager()
    monkeypatch.setattr(
        "web.routes.api.get_async_calibration_manager", lambda: fake, raising=True
    )
    return fake


class TestCalibrationTaskAdmin:
    def test_retry_success(self, bed: RouteTestBed) -> None:
        response = bed.client().post("/api/calibration/task/9/retry", headers=csrf_headers())

        assert response.status_code == 200
        assert response.get_json()["success"] is True
        assert bed.calibration_service.calls_named("schedule_retry") == [("schedule_retry", 9)]

    def test_retry_returns_500_when_service_reports_failure(self, bed: RouteTestBed) -> None:
        bed.calibration_service.retry_result = False

        response = bed.client().post("/api/calibration/task/9/retry", headers=csrf_headers())

        assert response.status_code == 500
        assert response.get_json() == {"success": False, "error": "重试失败"}

    def test_delete_task_missing_returns_404(self, bed: RouteTestBed) -> None:
        bed.calibration_service.delete_result = False

        response = bed.client().post("/api/calibration/task/9/delete", headers=csrf_headers())

        assert response.status_code == 404
        assert bed.calibration_service.calls_named("delete_task") == [("delete_task", 9)]

    def test_delete_task_success(self, bed: RouteTestBed) -> None:
        response = bed.client().post("/api/calibration/task/9/delete", headers=csrf_headers())

        assert response.status_code == 200
        assert response.get_json()["success"] is True

    def test_retry_missing_task_returns_404(self, bed: RouteTestBed) -> None:
        bed.calibration_service.raise_on = NotFoundError("任务不存在", resource_type="task")

        response = bed.client().post("/api/calibration/task/9/retry", headers=csrf_headers())

        assert response.status_code == 404
        assert response.get_json() == {"success": False, "error": "任务不存在"}

    def test_retry_internal_error_returns_generic_500(self, bed: RouteTestBed) -> None:
        """异常原文只进日志：此前该分支把 `str(e)` 原样回显（报告 P1-5 #6 同类）。"""
        bed.calibration_service.raise_on = RuntimeError("/app/data/notes.db is locked")

        response = bed.client().post("/api/calibration/task/9/retry", headers=csrf_headers())

        assert response.status_code == 500
        assert response.get_json() == {"success": False, "error": "重试失败"}
        assert b"notes.db" not in response.data

    def test_delete_internal_error_returns_generic_500(self, bed: RouteTestBed) -> None:
        bed.calibration_service.raise_on = RuntimeError("/app/data/notes.db is locked")

        response = bed.client().post("/api/calibration/task/9/delete", headers=csrf_headers())

        assert response.status_code == 500
        assert response.get_json() == {"success": False, "error": "删除失败"}
        assert b"notes.db" not in response.data


class TestEditNoteApi:
    def test_updates_stripped_text(self, bed: RouteTestBed) -> None:
        response = bed.client().post(
            "/api/edit_note/1", json={"message_text": "  改过的正文 "}, headers=csrf_headers()
        )

        assert response.status_code == 200
        assert bed.note_service.calls_named("update_text") == [("update_text", 1, "改过的正文")]
        assert bed.note_service.notes[1].message_text == "改过的正文"

    def test_missing_body_clears_text(self, bed: RouteTestBed) -> None:
        response = bed.client().post("/api/edit_note/1", json={}, headers=csrf_headers())

        assert response.status_code == 200
        assert bed.note_service.calls_named("update_text") == [("update_text", 1, "")]

    def test_non_string_payload_returns_400(self, bed: RouteTestBed) -> None:
        response = bed.client().post(
            "/api/edit_note/1", json={"message_text": 123}, headers=csrf_headers()
        )

        assert response.status_code == 400
        assert bed.note_service.calls_named("update_text") == []

    def test_missing_note_returns_404(self, bed: RouteTestBed) -> None:
        response = bed.client().post(
            "/api/edit_note/404", json={"message_text": "x"}, headers=csrf_headers()
        )

        assert response.status_code == 404

    def test_internal_error_does_not_leak_details(self, bed: RouteTestBed) -> None:
        bed.note_service.raise_on_write = RuntimeError("/app/data/notes.db disk I/O error")

        response = bed.client().post(
            "/api/edit_note/1", json={"message_text": "x"}, headers=csrf_headers()
        )

        assert response.status_code == 500
        assert response.get_json() == {"success": False, "error": "服务器错误"}


class TestSyncCalibrate:
    def test_success_returns_workflow_payload(self, bed: RouteTestBed) -> None:
        response = bed.client().post("/api/calibrate/1", headers=csrf_headers())

        assert response.status_code == 200
        assert response.get_json() == {"success": True, "updated": 1}
        assert bed.workflow_service.calls_named("calibrate_note") == [("calibrate_note", 1)]

    def test_workflow_exception_returns_generic_500(self, bed: RouteTestBed) -> None:
        bed.workflow_service.raise_on = RuntimeError("qbt at http://10.0.0.5:8080 unreachable")

        response = bed.client().post("/api/calibrate/1", headers=csrf_headers())

        assert response.status_code == 500
        assert response.get_json() == {"success": False, "error": "服务器错误"}
        assert b"10.0.0.5" not in response.data

    def test_workflow_error_propagates_status_code(self, bed: RouteTestBed) -> None:
        bed.workflow_service.note_result = (None, "笔记不存在", 404)

        response = bed.client().post("/api/calibrate/404", headers=csrf_headers())

        assert response.status_code == 404
        assert response.get_json() == {"success": False, "error": "笔记不存在"}


class TestAsyncCalibrate:
    def test_requires_note_id_or_info_hash(self, bed: RouteTestBed, manager: FakeAsyncManager) -> None:
        response = bed.client().post("/api/calibrate/async", json={}, headers=csrf_headers())

        assert response.status_code == 400
        assert manager.submissions == []

    def test_note_id_branch_submits_note_job(
        self, bed: RouteTestBed, manager: FakeAsyncManager
    ) -> None:
        response = bed.client().post(
            "/api/calibrate/async", json={"note_id": 5}, headers=csrf_headers()
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "success": True,
            "task_id": "task-1",
            "status": TaskStatus.PENDING.value,
        }
        (info_hash, args, kwargs), = manager.submissions
        assert info_hash == "note:5"
        assert args == ()
        assert kwargs["note_id"] == 5
        assert kwargs["workflow_service"] is bed.workflow_service
        # 任务函数确实跑到了 workflow 服务上（同步替身立即执行）
        assert bed.workflow_service.calls_named("calibrate_note") == [("calibrate_note", 5)]

    def test_non_integer_note_id_returns_400(
        self, bed: RouteTestBed, manager: FakeAsyncManager
    ) -> None:
        response = bed.client().post(
            "/api/calibrate/async", json={"note_id": "abc"}, headers=csrf_headers()
        )

        assert response.status_code == 400
        assert manager.submissions == []

    def test_info_hash_branch_passes_flat_kwargs(
        self, bed: RouteTestBed, manager: FakeAsyncManager
    ) -> None:
        """回归：参数必须平铺展开，不能再包一层 `kwargs={...}`。"""
        response = bed.client().post(
            "/api/calibrate/async", json={"info_hash": "  ABCDEF  "}, headers=csrf_headers()
        )

        assert response.status_code == 200
        (info_hash, args, kwargs), = manager.submissions
        assert info_hash == "ABCDEF"
        assert args == ()
        assert set(kwargs) == {"info_hash_value", "workflow_service"}
        assert kwargs["info_hash_value"] == "ABCDEF"
        assert bed.workflow_service.calls_named("calibrate_info_hash_filename") == [
            ("calibrate_info_hash_filename", "ABCDEF")
        ]
        assert manager.tasks["task-1"].status is TaskStatus.COMPLETED
        assert manager.tasks["task-1"].result == "calibrated.mkv"

    def test_blank_info_hash_returns_400(
        self, bed: RouteTestBed, manager: FakeAsyncManager
    ) -> None:
        response = bed.client().post(
            "/api/calibrate/async", json={"info_hash": "   "}, headers=csrf_headers()
        )

        assert response.status_code == 400
        assert manager.submissions == []

    def test_status_reports_completed_result(
        self, bed: RouteTestBed, manager: FakeAsyncManager
    ) -> None:
        client = bed.client()
        client.post("/api/calibrate/async", json={"info_hash": "ABCDEF"}, headers=csrf_headers())

        response = client.get("/api/calibrate/status/task-1")

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["status"] == TaskStatus.COMPLETED.value
        assert payload["result"] == "calibrated.mkv"

    def test_status_reports_failure_reason(
        self, bed: RouteTestBed, manager: FakeAsyncManager
    ) -> None:
        bed.workflow_service.info_hash_result = (None, "qBittorrent 无响应")
        client = bed.client()
        client.post("/api/calibrate/async", json={"info_hash": "ABCDEF"}, headers=csrf_headers())

        payload = client.get("/api/calibrate/status/task-1").get_json()

        assert payload["status"] == TaskStatus.FAILED.value
        assert payload["error"] == "qBittorrent 无响应"

    def test_note_job_failure_marks_task_failed(
        self, bed: RouteTestBed, manager: FakeAsyncManager
    ) -> None:
        """note_id 分支的任务函数把 (payload, error, status) 折成 (None, error)。"""
        bed.workflow_service.note_result = (None, "笔记没有磁力链接", 400)
        client = bed.client()

        client.post("/api/calibrate/async", json={"note_id": 5}, headers=csrf_headers())

        task = manager.tasks["task-1"]
        assert task.status is TaskStatus.FAILED
        assert task.error == "笔记没有磁力链接"

    def test_unknown_task_returns_404(self, bed: RouteTestBed, manager: FakeAsyncManager) -> None:
        response = bed.client().get("/api/calibrate/status/nope")

        assert response.status_code == 404


class TestDownload:
    def test_adds_note_download_with_selected_index(self, bed: RouteTestBed) -> None:
        response = bed.client().post(
            "/api/download/1", json={"magnet_index": 2}, headers=csrf_headers()
        )

        assert response.status_code == 200
        assert response.get_json() == {"success": True, "info_hash": "AAAA"}
        assert bed.qbittorrent_service.calls_named("add_note_download") == [
            ("add_note_download", 1, 2)
        ]

    def test_missing_note_returns_404_without_touching_qbittorrent(
        self, bed: RouteTestBed
    ) -> None:
        response = bed.client().post("/api/download/404", json={}, headers=csrf_headers())

        assert response.status_code == 404
        assert bed.qbittorrent_service.calls == []

    def test_qbittorrent_failure_returns_generic_500(self, bed: RouteTestBed) -> None:
        bed.qbittorrent_service.raise_on = RuntimeError("http://10.0.0.5:8080 refused")

        response = bed.client().post("/api/download/1", json={}, headers=csrf_headers())

        assert response.status_code == 500
        assert response.get_json() == {"success": False, "error": "服务器错误"}

    def test_download_status_passthrough(self, bed: RouteTestBed) -> None:
        bed.qbittorrent_service.status_result = ({"success": True, "progress": 0.25}, 200)

        response = bed.client().get("/api/download/status/AAAA")

        assert response.status_code == 200
        assert response.get_json()["progress"] == 0.25
        assert bed.qbittorrent_service.calls_named("get_download_status") == [
            ("get_download_status", "AAAA")
        ]

    def test_download_status_failure_returns_generic_500(self, bed: RouteTestBed) -> None:
        bed.qbittorrent_service.raise_on = RuntimeError("connection to 10.0.0.5 failed")

        response = bed.client().get("/api/download/status/AAAA")

        assert response.status_code == 500
        assert response.get_json() == {"success": False, "error": "服务器错误"}


class TestBatchCalibrate:
    def test_defaults_count_and_force(self, bed: RouteTestBed) -> None:
        response = bed.client().post("/api/calibrate/batch", json={}, headers=csrf_headers())

        assert response.status_code == 200
        assert bed.workflow_service.calls_named("batch_schedule_recent_notes") == [
            ("batch_schedule_recent_notes", 100, False)
        ]

    @pytest.mark.parametrize("count", [0, -1, 1001, "many"])
    def test_rejects_out_of_range_count(self, bed: RouteTestBed, count: object) -> None:
        response = bed.client().post(
            "/api/calibrate/batch", json={"count": count}, headers=csrf_headers()
        )

        assert response.status_code == 400
        assert bed.workflow_service.calls == []

    @pytest.mark.parametrize("count", [True, False])
    def test_rejects_bool_count(self, bed: RouteTestBed, count: bool) -> None:
        """`bool` 是 `int` 的子类，`isinstance(count, int)` 会把 `true` 放行成 count=1。"""
        response = bed.client().post(
            "/api/calibrate/batch", json={"count": count}, headers=csrf_headers()
        )

        assert response.status_code == 400
        assert response.get_json() == {"success": False, "error": "数量必须在1-1000之间"}
        assert bed.workflow_service.calls == []

    def test_service_exception_returns_generic_500(self, bed: RouteTestBed) -> None:
        bed.workflow_service.raise_on = RuntimeError("scheduler at /app/data/notes.db down")

        response = bed.client().post(
            "/api/calibrate/batch", json={"count": 10}, headers=csrf_headers()
        )

        assert response.status_code == 500
        assert response.get_json() == {"success": False, "error": "服务器错误"}
        assert b"notes.db" not in response.data

    def test_empty_result_returns_404(self, bed: RouteTestBed) -> None:
        bed.workflow_service.batch_result = {"success": True, "total": 0}

        response = bed.client().post(
            "/api/calibrate/batch", json={"count": 10, "force": True}, headers=csrf_headers()
        )

        assert response.status_code == 404
        assert bed.workflow_service.calls_named("batch_schedule_recent_notes") == [
            ("batch_schedule_recent_notes", 10, True)
        ]
