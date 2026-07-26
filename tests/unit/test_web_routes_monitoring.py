"""`web/routes/monitoring.py` 的鉴权与开关测试（此前 85 语句 0%）。

为什么只测这两件事：报告 §6.2 把「monitoring 子系统是否保留」列为待业务确认项
（UI 无入口，但路由仍注册在 `/monitoring`）。在去留定下来之前，值得钉住的不是它
的指标语义，而是——**它没有把一个未鉴权的观测面挂在公网上**，以及
`MONITORING_DASHBOARD_ENABLED=0` 这个开关真的关得掉。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from unit.web_route_fakes import RouteTestBed, build_testbed
from web.routes.monitoring import _extract_slow_queries

PAGE_ENDPOINTS = ["/monitoring/", "/monitoring/dashboard"]
API_ENDPOINTS = ["/monitoring/api/summary", "/monitoring/api/db/recent"]


@pytest.fixture
def bed(tmp_path: Path) -> RouteTestBed:
    return build_testbed(tmp_path)


@pytest.mark.parametrize("path", PAGE_ENDPOINTS)
def test_pages_require_login(bed: RouteTestBed, path: str) -> None:
    response = bed.client(logged_in=False).get(path)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("path", API_ENDPOINTS)
def test_apis_require_login(bed: RouteTestBed, path: str) -> None:
    response = bed.client(logged_in=False).get(path)

    assert response.status_code == 401
    assert response.get_json() == {"success": False, "error": "未登录"}


@pytest.mark.parametrize("path", PAGE_ENDPOINTS + API_ENDPOINTS)
def test_kill_switch_hides_every_endpoint(
    bed: RouteTestBed, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setenv("MONITORING_DASHBOARD_ENABLED", "0")

    response = bed.client().get(path)

    assert response.status_code == 404


class TestExtractSlowQueries:
    def test_keeps_only_slow_db_metrics(self) -> None:
        metrics = [
            {"name": "http.request", "value": 1, "metadata": {"is_slow": True}},
            {"name": "db.query.duration_ms", "value": 2, "metadata": {"is_slow": False}},
            {
                "name": "db.query.duration_ms",
                "value": 120,
                "timestamp": 7,
                "metadata": {"is_slow": True, "query": "SELECT 1", "rows_affected": 3},
                "tags": {"query_type": "select"},
            },
        ]

        assert _extract_slow_queries(metrics) == [
            {
                "timestamp": 7,
                "duration_ms": 120,
                "query": "SELECT 1",
                "rows_affected": 3,
                "query_type": "select",
            }
        ]

    def test_respects_limit(self) -> None:
        metrics = [
            {"name": "db.query.duration_ms", "value": i, "metadata": {"is_slow": True}}
            for i in range(5)
        ]

        assert len(_extract_slow_queries(metrics, limit=2)) == 2
