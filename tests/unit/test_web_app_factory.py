"""`web.create_app()` 的装配契约，含本轮新增的构造期副作用注入点。

`WebInfrastructure` 是为了让 `web/routes/*` 可测才开的缝（报告 §4 Phase 3 ①）。
缝本身也要有断言：默认必须仍是生产实现（否则 `app.py` 会静默地不建库），注入版
必须真的被调用且只调用一次。
"""

from __future__ import annotations

from pathlib import Path

from src.infrastructure.persistence import init_database as real_init_database
from unit.web_route_fakes import build_testbed
from web import WebInfrastructure, _default_infrastructure, create_app
from web.services import EXTENSION_KEY, WebServices


def test_default_infrastructure_is_production_implementation() -> None:
    """默认值必须仍指向真实建库/存储装配 —— 缝不能顺手改掉生产行为。"""
    from web.utils.storage import init_storage_manager

    infra = _default_infrastructure()

    assert infra.init_database is real_init_database
    assert infra.init_storage_manager is init_storage_manager


def test_injected_infrastructure_runs_once_and_binds_storage_manager() -> None:
    calls: list[str] = []
    services = WebServices(
        note_service=object(),  # type: ignore[arg-type]
        calibration_service=object(),  # type: ignore[arg-type]
        calibration_workflow_service=object(),  # type: ignore[arg-type]
        qbittorrent_service=object(),  # type: ignore[arg-type]
        reload_calibration_config=lambda: None,
    )
    infrastructure = WebInfrastructure(
        init_database=lambda: calls.append("db"),
        init_storage_manager=lambda: (calls.append("storage"), "manager-obj")[1],
    )

    app = create_app(services=services, infrastructure=infrastructure)

    assert calls == ["db", "storage"]
    assert app.storage_manager == "manager-obj"
    assert app.extensions[EXTENSION_KEY] is services


def test_factory_applies_custom_config_and_registers_blueprints(tmp_path: Path) -> None:
    bed = build_testbed(tmp_path)

    assert bed.app.config["TESTING"] is True
    assert {"main", "auth", "notes", "admin", "media", "api", "monitoring"} <= set(
        bed.app.blueprints
    )


def test_factory_output_carries_security_baseline(tmp_path: Path) -> None:
    """经工厂建出来的 app 一定带 CSRF 与安全响应头。

    `test_media_route_range.py` 那种绕开工厂自建 `Flask(__name__)` 的写法测不到这
    一层——这正是把路由测试搬回真实工厂的理由之一。
    """
    bed = build_testbed(tmp_path)
    client = bed.client(logged_in=False)

    # 取一个不碰数据库的端点：/health 会打开真实 notes.db
    response = client.get("/login")

    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Content-Security-Policy")
    assert client.post("/delete_note/1").status_code == 403
