"""
监控仪表盘路由

提供：
- /monitoring/dashboard: 监控仪表盘页面（自动刷新）
- /monitoring/api/summary: 近实时指标汇总（内存）
- /monitoring/api/db/recent: 最近持久化指标（SQLite）
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

from flask import Blueprint, jsonify, render_template, request

from web.auth import api_login_required, login_required

from src.infrastructure.monitoring import get_metric_collector, is_monitoring_enabled
from src.infrastructure.monitoring.storage import get_memory_store, get_sqlite_store2

monitoring_bp = Blueprint("monitoring", __name__)


def _env_bool(key: str, default: bool) -> bool:
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


@monitoring_bp.route("/")
@login_required
def monitoring_root():
    if not _env_bool("MONITORING_DASHBOARD_ENABLED", True):
        return ("Not Found", 404)
    refresh_seconds = _env_int("MONITORING_DASHBOARD_REFRESH_SECONDS", 3)
    return render_template("dashboard.html", refresh_seconds=max(refresh_seconds, 1))


@monitoring_bp.route("/dashboard")
@login_required
def dashboard():
    if not _env_bool("MONITORING_DASHBOARD_ENABLED", True):
        return ("Not Found", 404)
    refresh_seconds = _env_int("MONITORING_DASHBOARD_REFRESH_SECONDS", 3)
    return render_template("dashboard.html", refresh_seconds=max(refresh_seconds, 1))


def _extract_slow_queries(metrics_recent: List[Dict[str, Any]], *, limit: int = 20) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for m in metrics_recent:
        if m.get("name") != "db.query.duration_ms":
            continue
        metadata = m.get("metadata") or {}
        if not metadata.get("is_slow"):
            continue
        items.append(
            {
                "timestamp": m.get("timestamp"),
                "duration_ms": m.get("value"),
                "query": metadata.get("query"),
                "rows_affected": metadata.get("rows_affected"),
                "query_type": (m.get("tags") or {}).get("query_type"),
            }
        )
        if len(items) >= limit:
            break
    return items


@monitoring_bp.route("/api/summary")
@api_login_required
def api_summary():
    if not _env_bool("MONITORING_DASHBOARD_ENABLED", True):
        return jsonify({"success": False, "error": "not_found"}), 404

    window_seconds = _env_int("MONITORING_DASHBOARD_WINDOW_SECONDS", 60)
    window_seconds = max(int(request.args.get("window", window_seconds)), 1)
    recent_limit = max(int(request.args.get("recent", 200)), 1)

    store = get_memory_store()
    metrics_recent = store.metrics_recent(limit=recent_limit)
    snapshot = store.metrics_snapshot(window_seconds=window_seconds)
    slow_queries = _extract_slow_queries(metrics_recent)

    errors_top: List[Dict[str, Any]] = []
    try:
        errors_top = store.errors_top(limit=10)
    except Exception:
        errors_top = []

    collector = get_metric_collector()

    return jsonify(
        {
            "success": True,
            "server_time_epoch": time.time(),
            "monitoring_enabled": bool(is_monitoring_enabled()),
            "collector_enabled": bool(getattr(collector, "enabled", False)),
            "persistence_enabled": bool(getattr(collector, "persistence_enabled", False)),
            "snapshot": snapshot,
            "metrics_recent": metrics_recent,
            "slow_queries": slow_queries,
            "errors_top": errors_top,
        }
    )


@monitoring_bp.route("/api/db/recent")
@api_login_required
def api_db_recent():
    if not _env_bool("MONITORING_DASHBOARD_ENABLED", True):
        return jsonify({"success": False, "error": "not_found"}), 404

    limit = max(int(request.args.get("limit", 200)), 1)
    since_seconds = request.args.get("since_seconds")
    since_epoch = None
    if since_seconds is not None:
        try:
            since_epoch = time.time() - max(float(since_seconds), 0.0)
        except ValueError:
            since_epoch = None

    try:
        items = get_sqlite_store2().metrics_recent(limit=limit, since_epoch=since_epoch)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "items": items})

