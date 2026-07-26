"""
Unit tests for CalibrationManager stats accessor + 构造函数注入。
"""

from __future__ import annotations

import pytest


class _FakeCalibrationService:
    """只实现 CalibrationManager 真正调用到的两个方法。"""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self.get_config_calls = 0

    def get_config(self):
        self.get_config_calls += 1
        return type("Cfg", (), {"to_dict": lambda _self: {"enabled": True, "filter_mode": "empty_only"}})()

    def is_enabled(self) -> bool:
        return self._enabled


def test_calibration_manager_get_stats_uses_database_function(monkeypatch) -> None:
    import bot.services.calibration_manager as calibration_manager_module

    monkeypatch.setattr(
        calibration_manager_module,
        "get_calibration_stats",
        lambda: {"pending": 3, "success": 10},
        raising=True,
    )

    manager = calibration_manager_module.CalibrationManager(_FakeCalibrationService())
    assert manager.get_stats() == {"pending": 3, "success": 10}


def test_calibration_manager_requires_injected_service() -> None:
    """构造函数注入是强制的：不再有内部服务定位可兜底（§5.3 rule 3）。"""
    from bot.services.calibration_manager import CalibrationManager

    with pytest.raises(TypeError):
        CalibrationManager()  # type: ignore[call-arg]


def test_calibration_manager_uses_injected_service_not_container() -> None:
    """reload_config / is_enabled 全部落到注入的实例上，不触碰全局容器。"""
    from bot.services.calibration_manager import CalibrationManager

    service = _FakeCalibrationService(enabled=False)
    manager = CalibrationManager(service)

    assert manager.calibration_service is service
    assert service.get_config_calls == 1
    assert manager.config == {"enabled": True, "filter_mode": "empty_only"}
    assert manager.is_enabled() is False
