"""`web/routes/notes.py` 的路由级测试（报告 §3 P1-6：该文件此前 102 语句 0%）。

覆盖列表 / 编辑 / 删除 / 收藏切换的成功路径与 404、失败路径。断言落在
**替身收到的参数**与**状态变化**上，而不是「返回了 200」——后者在服务被传错参数
时同样会绿。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.config.constants import AppConstants
from unit.web_route_fakes import (
    FakeNoteService,
    RouteTestBed,
    build_testbed,
    csrf_headers,
    make_note,
)


@pytest.fixture(autouse=True)
def stub_viewer_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """观看站点配置读的是运维真实配置文件，路由测试不该依赖（也不该读）它。"""
    monkeypatch.setattr(
        "web.routes.notes.load_viewer_config",
        lambda: {"viewer_url": "https://viewer.example/"},
        raising=True,
    )


@pytest.fixture
def bed(tmp_path: Path) -> RouteTestBed:
    return build_testbed(tmp_path)


class TestNotesList:
    def test_passes_query_filters_through_to_service(self, bed: RouteTestBed) -> None:
        response = bed.client().get(
            "/notes?page=2&source=-100123&search=abc&date_from=2026-07-01"
            "&date_to=2026-07-26&favorite=1"
        )

        assert response.status_code == 200
        (_, kwargs), = bed.note_service.calls_named("get_notes")
        assert kwargs == {
            "user_id": None,
            "source_chat_id": "-100123",
            "search_query": "abc",
            "date_from": "2026-07-01",
            "date_to": "2026-07-26",
            "favorite_only": True,
            "page": 2,
            "page_size": AppConstants.NOTES_PER_PAGE,
        }

    def test_defaults_to_first_page_without_filters(self, bed: RouteTestBed) -> None:
        response = bed.client().get("/notes")

        assert response.status_code == 200
        (_, kwargs), = bed.note_service.calls_named("get_notes")
        assert kwargs["page"] == 1
        assert kwargs["favorite_only"] is False
        assert kwargs["source_chat_id"] is None

    def test_renders_note_with_parsed_magnet_payload(self, bed: RouteTestBed) -> None:
        html = bed.client().get("/notes").data.decode("utf-8")

        assert "测试频道" in html
        # note_card.html 消费的是 _process_note_magnets 产出的 all_dns + viewer_url
        assert "https://viewer.example/" in html
        assert "demo.mp4" in html

    def test_note_without_magnet_renders_without_watch_link(self, tmp_path: Path) -> None:
        service = FakeNoteService(
            {3: make_note(3, message_text="纯文本笔记", magnet_link=None, filename=None)}
        )
        bed = build_testbed(tmp_path, note_service=service)

        html = bed.client().get("/notes").data.decode("utf-8")

        assert "纯文本笔记" in html
        assert "dnCount: 0" in html

    def test_requires_login(self, bed: RouteTestBed) -> None:
        response = bed.client(logged_in=False).get("/notes")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        assert bed.note_service.calls == []

    def test_forced_password_change_blocks_notes_page(self, bed: RouteTestBed) -> None:
        client = bed.client(must_change_password=True)

        response = client.get("/notes")

        assert response.status_code == 302
        assert "/admin" in response.headers["Location"]
        assert bed.note_service.calls == []


class TestEditNote:
    def test_get_renders_existing_note(self, bed: RouteTestBed) -> None:
        response = bed.client().get("/edit_note/1")

        assert response.status_code == 200
        assert bed.note_service.calls_named("get_note") == [("get_note", 1)]

    def test_get_missing_note_redirects_to_list(self, bed: RouteTestBed) -> None:
        response = bed.client().get("/edit_note/404")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/notes")

    def test_post_updates_text_and_redirects_to_return_url(self, bed: RouteTestBed) -> None:
        response = bed.client().post(
            "/edit_note/1",
            data={"message_text": "  新内容  ", "return_url": "/notes?page=3"},
            headers=csrf_headers(),
        )

        assert response.status_code == 302
        assert response.headers["Location"] == "/notes?page=3"
        # 前后空白被 strip 后才落到服务层
        assert bed.note_service.calls_named("update_text") == [("update_text", 1, "新内容")]
        assert bed.note_service.notes[1].message_text == "新内容"

    def test_post_without_csrf_token_is_rejected(self, bed: RouteTestBed) -> None:
        response = bed.client().post("/edit_note/1", data={"message_text": "x"})

        assert response.status_code == 403
        assert bed.note_service.calls_named("update_text") == []

    def test_post_failure_rerenders_form_without_leaking_internals(
        self, bed: RouteTestBed
    ) -> None:
        bed.note_service.raise_on_write = RuntimeError("sqlite3: no such table notes")

        response = bed.client().post(
            "/edit_note/1", data={"message_text": "x"}, headers=csrf_headers()
        )
        html = response.data.decode("utf-8")

        assert response.status_code == 200
        assert "更新失败" in html
        assert "sqlite3" not in html


class TestDeleteNote:
    def test_deletes_and_reports_success(self, bed: RouteTestBed) -> None:
        response = bed.client().post("/delete_note/1", headers=csrf_headers())

        assert response.status_code == 200
        assert response.get_json() == {"success": True, "reload": False}
        assert bed.note_service.calls_named("delete_note") == [("delete_note", 1)]
        assert 1 not in bed.note_service.notes

    def test_missing_note_returns_404(self, bed: RouteTestBed) -> None:
        response = bed.client().post("/delete_note/404", headers=csrf_headers())

        assert response.status_code == 404
        assert response.get_json() == {"success": False, "error": "笔记不存在"}

    def test_internal_error_returns_generic_500(self, bed: RouteTestBed) -> None:
        bed.note_service.raise_on_write = RuntimeError("/app/data/notes.db is locked")

        response = bed.client().post("/delete_note/1", headers=csrf_headers())

        assert response.status_code == 500
        # 延续 P1-5 #6 的修复语义：错误响应不得回显内部路径
        assert response.get_json() == {"success": False, "error": "删除失败"}

    def test_anonymous_gets_json_401_not_redirect(self, bed: RouteTestBed) -> None:
        """API 端点对未登录返回 JSON 401，而不是重定向到登录页。

        注意取 token 的方式：CSRF 的 `before_request` 排在鉴权装饰器之前，直接裸
        POST 会先撞 403，根本走不到 401 分支。这里先建立一个「有 CSRF token 但没
        登录」的会话，才能真正验到 `api_login_required`。
        """
        client = bed.client(logged_in=False)
        with client.session_transaction() as session:
            session["_csrf_token"] = csrf_headers()["X-CSRFToken"]

        response = client.post("/delete_note/1", headers=csrf_headers())

        assert response.status_code == 401
        assert response.get_json() == {"success": False, "error": "未登录"}
        assert bed.note_service.calls == []

    def test_anonymous_without_csrf_token_is_blocked_earlier(self, bed: RouteTestBed) -> None:
        response = bed.client(logged_in=False).post("/delete_note/1")

        assert response.status_code == 403
        assert bed.note_service.calls == []


class TestToggleFavorite:
    def test_toggles_state_and_returns_new_value(self, tmp_path: Path) -> None:
        service = FakeNoteService({7: make_note(7, is_favorite=False)})
        bed = build_testbed(tmp_path, note_service=service)
        client = bed.client()

        first = client.post("/toggle_favorite/7", headers=csrf_headers())
        second = client.post("/toggle_favorite/7", headers=csrf_headers())

        assert first.get_json() == {"success": True, "is_favorite": True}
        assert second.get_json() == {"success": True, "is_favorite": False}
        assert service.calls_named("toggle_favorite") == [
            ("toggle_favorite", 7),
            ("toggle_favorite", 7),
        ]

    def test_missing_note_returns_404(self, bed: RouteTestBed) -> None:
        response = bed.client().post("/toggle_favorite/404", headers=csrf_headers())

        assert response.status_code == 404
        assert response.get_json() == {"success": False, "error": "笔记不存在"}

    def test_internal_error_returns_generic_500(self, bed: RouteTestBed) -> None:
        bed.note_service.raise_on_write = RuntimeError("disk I/O error at /app/data")

        response = bed.client().post("/toggle_favorite/1", headers=csrf_headers())

        assert response.status_code == 500
        assert response.get_json() == {"success": False, "error": "操作失败"}
