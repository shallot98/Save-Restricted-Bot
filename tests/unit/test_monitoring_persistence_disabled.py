"""
Unit tests for the disabled monitoring persistence path.

monitoring 子系统已停用：指标默认只进内存聚合器，不再写 monitoring.db。
"""

from __future__ import annotations

import pytest

from src.infrastructure.monitoring import is_metric_persistence_enabled
from src.infrastructure.monitoring import storage


class TestMetricPersistenceDisabled:
    def test_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MONITORING_PERSIST_ENABLED", raising=False)
        monkeypatch.delenv("MONITORING_ENABLED", raising=False)

        assert is_metric_persistence_enabled() is False

    def test_requires_explicit_opt_in(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MONITORING_PERSIST_ENABLED", "1")
        monkeypatch.setenv("MONITORING_ENABLED", "1")

        assert is_metric_persistence_enabled() is True

    def test_stays_off_when_monitoring_globally_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MONITORING_PERSIST_ENABLED", "1")
        monkeypatch.setenv("MONITORING_ENABLED", "0")

        assert is_metric_persistence_enabled() is False


class TestDeadStoreRemoved:
    def test_legacy_sqlite_store_is_gone(self) -> None:
        assert not hasattr(storage, "get_sqlite_store")
        assert "get_sqlite_store" not in storage.__all__
