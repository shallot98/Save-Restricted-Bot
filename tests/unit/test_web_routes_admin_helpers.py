"""`web/routes/admin_helpers.py` 的纯函数测试（此前 75 语句 0%）。

这些 helper 是后台写操作的**校验闸门**：密码强度、WebDAV 连通性、观看站点 URL
协议。路由层测试已经覆盖它们的主干，这里补的是不便经由 HTTP 制造的边角——
连通性探针抛异常、探针返回 False、以及「配置不完整时根本不该发起探测」。
"""

from __future__ import annotations

from typing import Any

import pytest

from web.routes.admin_helpers import (
    PasswordChangeDeps,
    PasswordChangeForm,
    WebDAVSaveDeps,
    build_admin_context,
    change_password,
    read_password_change_form,
    read_viewer_config,
    read_webdav_config,
    save_webdav_settings,
    validate_viewer_config,
    validate_webdav_config,
)


class _StubApp:
    def __init__(self) -> None:
        self.storage_manager: Any = None


def _form(**overrides: str) -> PasswordChangeForm:
    fields = {
        "username": "admin",
        "current_password": "old-pass",
        "new_password": "new-pass",
        "confirm_password": "new-pass",
    }
    fields.update(overrides)
    return PasswordChangeForm(**fields)


class TestChangePassword:
    def test_updates_when_all_checks_pass(self) -> None:
        updated: list[tuple[str, str]] = []
        deps = PasswordChangeDeps(
            verify_user=lambda u, p: True,
            update_password=lambda u, p: updated.append((u, p)),
        )

        assert change_password(_form(), deps) is None
        assert updated == [("admin", "new-pass")]

    def test_wrong_current_password_blocks_update(self) -> None:
        updated: list[tuple[str, str]] = []
        deps = PasswordChangeDeps(
            verify_user=lambda u, p: False,
            update_password=lambda u, p: updated.append((u, p)),
        )

        assert change_password(_form(), deps) == "当前密码不正确"
        assert updated == []

    @pytest.mark.parametrize(
        ("overrides", "expected"),
        [
            ({"new_password": "abc", "confirm_password": "abc"}, "新密码长度至少为 6 个字符"),
            ({"confirm_password": "other-pass"}, "两次输入的新密码不一致"),
        ],
    )
    def test_validation_failures_block_update(self, overrides: dict, expected: str) -> None:
        updated: list[tuple[str, str]] = []
        deps = PasswordChangeDeps(
            verify_user=lambda u, p: True,
            update_password=lambda u, p: updated.append((u, p)),
        )

        assert change_password(_form(**overrides), deps) == expected
        assert updated == []


def test_read_password_change_form_coerces_missing_fields() -> None:
    change = read_password_change_form({}, "admin")

    assert change == PasswordChangeForm("admin", "", "", "")


class TestWebDAVConfig:
    def test_read_webdav_config_trims_and_maps_checkboxes(self) -> None:
        config = read_webdav_config(
            {
                "enabled": "on",
                "url": "  https://dav.example  ",
                "webdav_username": " u ",
                "webdav_password": " p ",
                "base_path": " /x ",
            }
        )

        assert config == {
            "enabled": True,
            "url": "https://dav.example",
            "username": "u",
            "password": "p",
            "base_path": "/x",
            "keep_local_copy": False,
        }

    def test_incomplete_config_skips_probe(self) -> None:
        probes: list[tuple] = []

        def _factory(*args: Any) -> Any:
            probes.append(args)
            raise AssertionError("配置不完整时不应发起连通性探测")

        config = {"enabled": True, "url": "https://dav.example", "username": "", "password": ""}
        assert validate_webdav_config(config, _factory) is None
        assert probes == []

    def test_probe_failure_returns_message(self) -> None:
        class _Client:
            def __init__(self, *_: Any) -> None:
                pass

            def test_connection(self) -> bool:
                return False

        config = {"enabled": True, "url": "u", "username": "n", "password": "p", "base_path": "/"}
        assert validate_webdav_config(config, _Client) == "WebDAV 连接测试失败，请检查配置"

    def test_probe_exception_is_reported_not_raised(self) -> None:
        def _factory(*_: Any) -> Any:
            raise ConnectionError("name resolution failed")

        config = {"enabled": True, "url": "u", "username": "n", "password": "p", "base_path": "/"}
        error = validate_webdav_config(config, _factory)

        assert error is not None
        assert "WebDAV 连接失败" in error

    def test_save_rebinds_storage_manager(self) -> None:
        saved: list[dict] = []
        app = _StubApp()
        deps = WebDAVSaveDeps(
            save_config=saved.append,
            init_storage_manager=lambda: "new-manager",
            app=app,
        )

        save_webdav_settings({"enabled": True}, deps)

        assert saved == [{"enabled": True}]
        assert app.storage_manager == "new-manager"


class TestViewerConfig:
    def test_read_trims_url(self) -> None:
        assert read_viewer_config({"viewer_url": "  https://v/ "}) == {"viewer_url": "https://v/"}

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("", "观看网站URL不能为空"),
            ("v.example", "URL必须以 http:// 或 https:// 开头"),
            ("https://v.example/", None),
            ("http://v.example/", None),
        ],
    )
    def test_validation(self, url: str, expected: str | None) -> None:
        assert validate_viewer_config({"viewer_url": url}) == expected


class TestBuildAdminContext:
    def test_aggregates_service_data(self) -> None:
        class _Notes:
            def get_notes(self, **kwargs: Any) -> Any:
                assert kwargs == {"user_id": None, "page_size": 1}
                return type("R", (), {"total": 12})()

            def get_all_sources(self) -> list[dict]:
                return [{"source_chat_id": "-1", "source_name": "a", "count": 12}]

        class _Calib:
            def get_stats(self) -> dict:
                return {"total": 4, "by_status": {"pending": 4}}

        context = build_admin_context(_Notes(), _Calib(), must_change_password=True)

        assert context["total_count"] == 12
        assert context["total_sources"] == 1
        assert context["calib_stats"]["total"] == 4
        assert context["must_change_password"] is True

    def test_falls_back_to_zeroes_when_services_fail(self) -> None:
        class _Boom:
            def get_notes(self, **_: Any) -> Any:
                raise RuntimeError("db down")

            def get_all_sources(self) -> list:
                raise RuntimeError("db down")

            def get_stats(self) -> dict:
                raise RuntimeError("db down")

        context = build_admin_context(_Boom(), _Boom(), must_change_password=False)

        assert context["total_count"] == 0
        assert context["total_sources"] == 0
        assert context["sources"] == []
        assert context["calib_stats"] == {"total": 0, "by_status": {}}
