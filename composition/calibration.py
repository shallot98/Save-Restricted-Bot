"""``CalibrationManager`` 的装配与进程内单例。

原本这个单例住在 ``bot/services/calibration_manager.py``，并在 ``__init__``
里通过 ``from composition.container import get_calibration_service`` 自行取服务
——那是业务代码里的服务定位（报告 §5.3 rule 3），同时给
``composition → bot.services.calibration_manager → composition`` 埋了导入环。
依赖改为构造函数注入后，「谁来构造」这件事上移到组合根，也就是本模块。
"""

from __future__ import annotations

from typing import Optional

from bot.services.calibration_manager import CalibrationManager
from composition.container import get_calibration_service

_calibration_manager: Optional[CalibrationManager] = None


def build_calibration_manager() -> CalibrationManager:
    """构造一个全新的 ``CalibrationManager``（不走单例，供测试与显式装配使用）。"""
    return CalibrationManager(get_calibration_service())


def get_calibration_manager() -> CalibrationManager:
    """进程内单例。``CalibrationManager`` 持有校准配置缓存与队列状态，需共享。"""
    global _calibration_manager
    if _calibration_manager is None:
        _calibration_manager = build_calibration_manager()
    return _calibration_manager
