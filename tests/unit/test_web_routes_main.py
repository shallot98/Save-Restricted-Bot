"""`web/routes/main.py` 的路由级测试（此前 26 语句 0%）。

`/health` 是容器 healthcheck 的判据（`docker-compose.yml`），它此前没有任何测试
——一旦 200/503 的判定写反，编排层会把坏进程当成健康的。这里把三类降级各钉一条。
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from unit.web_route_fakes import RouteTestBed, build_testbed


@pytest.fixture
def bed(tmp_path: Path) -> RouteTestBed:
    return build_testbed(tmp_path)


@pytest.fixture(autouse=True)
def healthy_dependencies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """把 `/health` 的三个探针都指到测试可控的对象上。

    尤其是数据库连接：路由模块顶层持有 `get_db_connection`，不拦就会打开运维的
    真实 `data/notes.db`。
    """
    config_file = tmp_path / "config.json"
    watch_file = tmp_path / "watch_config.json"
    config_file.write_text("{}", encoding="utf-8")
    watch_file.write_text("{}", encoding="utf-8")

    _patch_settings_paths(monkeypatch, config_file, watch_file)
    monkeypatch.setattr(
        "web.routes.main.get_db_connection", _fake_connection_factory(ok=True), raising=True
    )


def _patch_settings_paths(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, watch_file: Path
) -> None:
    """替换路由模块持有的 settings。

    `PathConfig.config_file` 是只读 property（由 DATA_DIR 推导），改不了单个字段；
    换掉模块级 `settings` 引用是这里唯一不碰生产环境变量的做法。
    """
    stub = SimpleNamespace(paths=SimpleNamespace(config_file=config_file, watch_file=watch_file))
    monkeypatch.setattr("web.routes.main.settings", stub, raising=True)


def _fake_connection_factory(*, ok: bool):
    @contextlib.contextmanager
    def _connect():
        if not ok:
            raise RuntimeError("unable to open database file: /app/data/notes.db")
        yield _StubConnection()

    return _connect


class _StubConnection:
    def execute(self, _sql: str) -> "_StubConnection":
        return self

    def fetchone(self) -> tuple:
        return (1,)


class TestHome:
    def test_anonymous_goes_to_login(self, bed: RouteTestBed) -> None:
        response = bed.client(logged_in=False).get("/")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_logged_in_goes_to_notes(self, bed: RouteTestBed) -> None:
        response = bed.client().get("/")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/notes")


class TestHealth:
    def test_all_green_returns_200(self, bed: RouteTestBed) -> None:
        response = bed.client(logged_in=False).get("/health")

        assert response.status_code == 200
        assert response.get_json() == {
            "status": "healthy",
            "checks": {
                "database": "ok",
                "config": "ok",
                "watch_config": "ok",
                "storage": "ok",
            },
        }

    def test_database_failure_returns_503(
        self, bed: RouteTestBed, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "web.routes.main.get_db_connection", _fake_connection_factory(ok=False), raising=True
        )

        response = bed.client(logged_in=False).get("/health")
        payload = response.get_json()

        assert response.status_code == 503
        assert payload["status"] == "unhealthy"
        assert payload["checks"]["database"] == "error"

    def test_database_failure_does_not_leak_exception_text(
        self, bed: RouteTestBed, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`/health` 匿名可访问，异常原文（含 `/app/data/notes.db`）不得进响应体。"""
        monkeypatch.setattr(
            "web.routes.main.get_db_connection", _fake_connection_factory(ok=False), raising=True
        )

        response = bed.client(logged_in=False).get("/health")

        assert b"notes.db" not in response.data
        assert b"unable to open" not in response.data

    def test_missing_config_files_are_reported_without_failing_health(
        self, bed: RouteTestBed, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """配置文件缺失只标 missing，不改总状态——这是现有语义，钉住以防悄悄改。"""
        _patch_settings_paths(monkeypatch, tmp_path / "nope.json", tmp_path / "nope2.json")

        payload = bed.client(logged_in=False).get("/health").get_json()

        assert payload["status"] == "healthy"
        assert payload["checks"]["config"] == "missing"
        assert payload["checks"]["watch_config"] == "missing"

    def test_missing_storage_manager_degrades_without_failing_healthcheck(
        self, bed: RouteTestBed
    ) -> None:
        """存储不可用 → `degraded`，但 HTTP 仍 200。

        取舍见路由 docstring：编排层只看状态码，storage 抖动不应把一个仍能读写
        笔记的进程判成坏进程；降级信息通过响应体传达。
        """
        bed.app.storage_manager = None

        response = bed.client(logged_in=False).get("/health")
        payload = response.get_json()

        assert response.status_code == 200
        assert payload["checks"]["storage"] == "error"
        assert payload["status"] == "degraded"

    def test_database_failure_outranks_storage_degradation(
        self, bed: RouteTestBed, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """两个探针同时坏时，unhealthy 不能被 degraded 盖回去。"""
        bed.app.storage_manager = None
        monkeypatch.setattr(
            "web.routes.main.get_db_connection", _fake_connection_factory(ok=False), raising=True
        )

        response = bed.client(logged_in=False).get("/health")

        assert response.status_code == 503
        assert response.get_json()["status"] == "unhealthy"
