"""
Unit tests for CalibrationManager stats accessor.
"""

from __future__ import annotations


def test_calibration_manager_get_stats_uses_database_function(monkeypatch) -> None:
    import bot.services.calibration_manager as calibration_manager_module

    monkeypatch.setattr(
        calibration_manager_module.CalibrationManager,
        "reload_config",
        lambda self: setattr(self, "config", {}),
        raising=True,
    )
    monkeypatch.setattr(
        calibration_manager_module,
        "get_calibration_stats",
        lambda: {"pending": 3, "success": 10},
        raising=True,
    )

    manager = calibration_manager_module.CalibrationManager()
    assert manager.get_stats() == {"pending": 3, "success": 10}
