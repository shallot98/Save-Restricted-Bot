"""`web/routes/admin.py` 的路由级测试（报告 §3 P1-6：该文件此前 105 语句 0%）。

后台是全站唯一的写配置入口，也是「改密码 / 改 WebDAV / 改校准参数」的所在，此前
一条测试都没有。所有会落盘的依赖（`save_webdav_config` / `save_viewer_config` /
`update_password`）都换成记录型替身——既是为了断言参数，也是为了保证单测不写运维
的真实配置文件。
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from unit.web_route_fakes import (
    RouteTestBed,
    build_testbed,
    csrf_headers,
    make_calibration_task,
)
from web.services import EXTENSION_KEY, bind_services


class FakeWebDAVClient:
    """`bot.storage.webdav_client.WebDAVClient` 的连通性探针替身。"""

    connect_ok = True
    constructed: list[tuple] = []

    def __init__(self, url: str, username: str, password: str, base_path: str) -> None:
        type(self).constructed.append((url, username, password, base_path))

    def test_connection(self) -> bool:
        return type(self).connect_ok


@pytest.fixture
def bed(tmp_path: Path) -> RouteTestBed:
    return build_testbed(tmp_path)


@pytest.fixture
def saved_configs(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    """拦下 admin 路由的全部落盘/改库依赖，返回捕获到的调用。"""
    captured: dict[str, list] = {
        "webdav": [],
        "viewer": [],
        "password": [],
        "storage_init": [],
    }
    FakeWebDAVClient.constructed = []
    FakeWebDAVClient.connect_ok = True

    monkeypatch.setattr(
        "web.routes.admin.save_webdav_config",
        lambda config: captured["webdav"].append(config),
        raising=True,
    )
    monkeypatch.setattr(
        "web.routes.admin.load_webdav_config",
        lambda: {"enabled": False, "url": "", "username": "", "base_path": "/telegram_media"},
        raising=True,
    )
    monkeypatch.setattr(
        "web.routes.admin.save_viewer_config",
        lambda config: captured["viewer"].append(config),
        raising=True,
    )
    monkeypatch.setattr(
        "web.routes.admin.load_viewer_config",
        lambda: {"viewer_url": "https://viewer.example/"},
        raising=True,
    )
    monkeypatch.setattr(
        "web.routes.admin.update_password",
        lambda username, password: captured["password"].append((username, password)),
        raising=True,
    )
    monkeypatch.setattr("web.routes.admin.verify_user", lambda u, p: p == "correct", raising=True)
    monkeypatch.setattr("web.routes.admin.WebDAVClient", FakeWebDAVClient, raising=True)
    monkeypatch.setattr(
        "web.routes.admin.init_storage_manager",
        lambda: captured["storage_init"].append("init") or "storage",
        raising=True,
    )
    return captured


class TestAdminDashboard:
    def test_renders_stats_from_services(self, bed: RouteTestBed, saved_configs: dict) -> None:
        bed.note_service._total = 128
        bed.calibration_service.stats = {"total": 7, "by_status": {"pending": 7}}

        html = bed.client().get("/admin").data.decode("utf-8")

        assert "128" in html
        (_, kwargs), = bed.note_service.calls_named("get_notes")
        assert kwargs == {"user_id": None, "page_size": 1}
        assert "get_stats" in bed.calibration_service.call_names()

    def test_service_failure_degrades_to_zero_stats(
        self, bed: RouteTestBed, saved_configs: dict
    ) -> None:
        """`_load_note_stats` / `_load_calibration_stats` 的兜底分支。

        这是全仓少数「吞异常」被判定为可接受的地方（仪表盘取不到统计仍应可用），
        所以钉住它：页面 200，且渲染的是 0 而不是把内部异常抛给用户。
        """
        bed.note_service.raise_on_read = RuntimeError("/app/data/notes.db is locked")
        bed.calibration_service.raise_on = RuntimeError("calibration table missing")

        response = bed.client().get("/admin")
        html = response.data.decode("utf-8")

        assert response.status_code == 200
        assert "notes.db" not in html
        assert "calibration table missing" not in html

    def test_password_change_success_clears_forced_flag(
        self, bed: RouteTestBed, saved_configs: dict
    ) -> None:
        client = bed.client(must_change_password=True)

        response = client.post(
            "/admin",
            data={
                "current_password": "correct",
                "new_password": "new-strong-pass",
                "confirm_password": "new-strong-pass",
            },
            headers=csrf_headers(),
        )

        assert response.status_code == 200
        assert "密码更新成功" in response.data.decode("utf-8")
        assert saved_configs["password"] == [("admin", "new-strong-pass")]
        with client.session_transaction() as session:
            assert "must_change_password" not in session

    @pytest.mark.parametrize(
        ("form", "expected_error"),
        [
            (
                {"current_password": "wrong", "new_password": "abcdef", "confirm_password": "abcdef"},
                "当前密码不正确",
            ),
            (
                {"current_password": "correct", "new_password": "abc", "confirm_password": "abc"},
                "新密码长度至少为 6 个字符",
            ),
            (
                {"current_password": "correct", "new_password": "abcdef", "confirm_password": "abcdeg"},
                "两次输入的新密码不一致",
            ),
        ],
    )
    def test_password_change_rejections_do_not_write(
        self, bed: RouteTestBed, saved_configs: dict, form: dict, expected_error: str
    ) -> None:
        response = bed.client().post("/admin", data=form, headers=csrf_headers())

        assert response.status_code == 200
        assert expected_error in response.data.decode("utf-8")
        assert saved_configs["password"] == []

    def test_requires_login(self, bed: RouteTestBed, saved_configs: dict) -> None:
        response = bed.client(logged_in=False).get("/admin")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


class TestAdminWebDAV:
    def test_get_shows_current_config(self, bed: RouteTestBed, saved_configs: dict) -> None:
        response = bed.client().get("/admin/webdav")

        assert response.status_code == 200
        assert saved_configs["webdav"] == []

    def test_post_saves_normalized_config_and_reinits_storage(
        self, bed: RouteTestBed, saved_configs: dict
    ) -> None:
        response = bed.client().post(
            "/admin/webdav",
            data={
                "enabled": "on",
                "url": "  https://dav.example/  ",
                "webdav_username": " dav-user ",
                "webdav_password": " secret ",
                "base_path": " /media ",
                "keep_local_copy": "on",
            },
            headers=csrf_headers(),
        )

        assert response.status_code == 200
        assert saved_configs["webdav"] == [
            {
                "enabled": True,
                "url": "https://dav.example/",
                "username": "dav-user",
                "password": "secret",
                "base_path": "/media",
                "keep_local_copy": True,
            }
        ]
        assert saved_configs["storage_init"] == ["init"]
        assert FakeWebDAVClient.constructed == [
            ("https://dav.example/", "dav-user", "secret", "/media")
        ]

    def test_post_with_failing_connection_is_not_saved(
        self, bed: RouteTestBed, saved_configs: dict
    ) -> None:
        FakeWebDAVClient.connect_ok = False

        response = bed.client().post(
            "/admin/webdav",
            data={
                "enabled": "on",
                "url": "https://dav.example/",
                "webdav_username": "u",
                "webdav_password": "p",
            },
            headers=csrf_headers(),
        )

        assert "WebDAV 连接测试失败" in response.data.decode("utf-8")
        assert saved_configs["webdav"] == []
        assert saved_configs["storage_init"] == []

    def test_save_failure_rerenders_with_previous_config(
        self, bed: RouteTestBed, saved_configs: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(_config: dict) -> None:
            raise OSError("read-only file system")

        monkeypatch.setattr("web.routes.admin.save_webdav_config", _boom, raising=True)

        response = bed.client().post(
            "/admin/webdav", data={"url": "https://dav.example/"}, headers=csrf_headers()
        )

        assert response.status_code == 200
        assert "保存配置失败" in response.data.decode("utf-8")
        assert saved_configs["storage_init"] == []

    def test_disabled_config_skips_connection_probe(
        self, bed: RouteTestBed, saved_configs: dict
    ) -> None:
        response = bed.client().post(
            "/admin/webdav", data={"url": "https://dav.example/"}, headers=csrf_headers()
        )

        assert response.status_code == 200
        assert FakeWebDAVClient.constructed == []
        assert saved_configs["webdav"][0]["enabled"] is False


class TestAdminViewer:
    def test_get_shows_current_config(self, bed: RouteTestBed, saved_configs: dict) -> None:
        response = bed.client().get("/admin/viewer")

        assert response.status_code == 200
        assert "https://viewer.example/" in response.data.decode("utf-8")
        assert saved_configs["viewer"] == []

    def test_post_saves_trimmed_url(self, bed: RouteTestBed, saved_configs: dict) -> None:
        response = bed.client().post(
            "/admin/viewer", data={"viewer_url": "  https://v.example/w/ "}, headers=csrf_headers()
        )

        assert response.status_code == 200
        assert saved_configs["viewer"] == [{"viewer_url": "https://v.example/w/"}]

    @pytest.mark.parametrize("value", ["", "ftp://v.example"])
    def test_invalid_url_is_rejected(
        self, bed: RouteTestBed, saved_configs: dict, value: str
    ) -> None:
        response = bed.client().post(
            "/admin/viewer", data={"viewer_url": value}, headers=csrf_headers()
        )

        assert response.status_code == 200
        assert saved_configs["viewer"] == []

    def test_save_failure_rerenders_with_error(
        self, bed: RouteTestBed, saved_configs: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(_config: dict) -> None:
            raise OSError("read-only file system")

        monkeypatch.setattr("web.routes.admin.save_viewer_config", _boom, raising=True)

        response = bed.client().post(
            "/admin/viewer", data={"viewer_url": "https://v.example/"}, headers=csrf_headers()
        )

        assert response.status_code == 200
        assert "保存配置失败" in response.data.decode("utf-8")


class TestAdminCalibration:
    def test_get_renders_config_and_stats(self, bed: RouteTestBed) -> None:
        response = bed.client().get("/admin/calibration")

        assert response.status_code == 200
        assert bed.calibration_service.call_names().count("get_config") == 1

    def test_post_persists_typed_config_and_reloads_manager(self, bed: RouteTestBed) -> None:
        response = bed.client().post(
            "/admin/calibration",
            data={
                "enabled": "on",
                "filter_mode": "all",
                "first_delay": "60",
                "retry_delay_1": "120",
                "retry_delay_2": "240",
                "retry_delay_3": "480",
                "max_retries": "2",
                "concurrent_limit": "3",
                "timeout_per_magnet": "15",
                "batch_timeout": "150",
            },
            headers=csrf_headers(),
        )

        assert response.status_code == 200
        (_, config), = bed.calibration_service.calls_named("update_config")
        assert config == {
            "enabled": 1,
            "filter_mode": "all",
            "first_delay": 60,
            "retry_delay_1": 120,
            "retry_delay_2": 240,
            "retry_delay_3": 480,
            "max_retries": 2,
            "concurrent_limit": 3,
            "timeout_per_magnet": 15,
            "batch_timeout": 150,
        }
        # 保存后必须让 Bot 侧校准管理器重读配置
        assert bed.reload_calls == ["reload"]

    def test_reload_failure_does_not_fail_the_save(self, bed: RouteTestBed) -> None:
        """重载在后台线程里跑，失败只记日志——配置本身已经存下，页面不该 500。"""

        def _boom() -> None:
            raise RuntimeError("bot 进程不可达")

        services = replace(bed.app.extensions[EXTENSION_KEY], reload_calibration_config=_boom)
        bind_services(bed.app, services)

        response = bed.client().post(
            "/admin/calibration", data={"enabled": "on"}, headers=csrf_headers()
        )

        assert response.status_code == 200
        assert len(bed.calibration_service.calls_named("update_config")) == 1

    def test_invalid_numeric_input_reports_error_without_updating(
        self, bed: RouteTestBed
    ) -> None:
        response = bed.client().post(
            "/admin/calibration", data={"first_delay": "abc"}, headers=csrf_headers()
        )

        assert response.status_code == 200
        assert "保存配置失败" in response.data.decode("utf-8")
        assert bed.calibration_service.calls_named("update_config") == []
        assert bed.reload_calls == []


class TestCalibrationQueue:
    def test_lists_tasks_with_pagination_offset(self, bed: RouteTestBed) -> None:
        bed.calibration_service.tasks = [make_calibration_task(id=11, note_id=7)]

        response = bed.client().get("/admin/calibration/queue?status=pending&page=3")

        assert response.status_code == 200
        assert bed.calibration_service.calls_named("list_all") == [
            ("list_all", "pending", 50, 100)
        ]

    def test_blank_status_filter_becomes_none(self, bed: RouteTestBed) -> None:
        response = bed.client().get("/admin/calibration/queue")

        assert response.status_code == 200
        assert bed.calibration_service.calls_named("list_all") == [("list_all", None, 50, 0)]


def test_admin_routes_use_injected_services(bed: RouteTestBed, saved_configs: dict) -> None:
    """所有 admin 读路径都必须走注入的服务，不得就地做服务定位。"""
    client = bed.client()
    for path in ("/admin", "/admin/calibration", "/admin/calibration/queue"):
        assert client.get(path).status_code == 200

    called: set[str] = set(bed.calibration_service.call_names())
    assert {"get_stats", "get_config", "list_all"} <= called
