"""
Composition Root - 具体实现装配
================================

把 `bot/` 侧的具体实现注册到 `ServiceContainer`，使 `src.application`
只依赖 `src.core.interfaces` 的窄端口（报告 §3 P1-1 / §5.2）。

为什么是「入口显式调用」而不是在 `container.py` 顶层 import bot：
    根 `database.py` 顶层 import `composition.container`，而 bot 侧实现
    （`calibration_manager` → `database`）会传递依赖到它。若 `container.py`
    顶层 import bot，就会形成
        composition.container → bot.services.calibration_manager
            → database → composition.container
    的导入环，回读时 `get_container` 尚未定义直接 ImportError。
    根 `database.py` 仍是 Phase 3 的删除目标，因此把装配从 **import 期**
    移到 **启动期**——这本就是组合根的标准做法：装配是运行时行为。

调用点：`main.py`（Bot 进程）与 `app.py`（Flask 进程）——都在**构造任何服务之前**。
注意不是 `web.create_app()`：Phase 3 起 `web/` 不再 import `composition`。
"""

from __future__ import annotations

import logging
from typing import Optional

from bot.storage.media_storage_provider import build_media_storage
from composition.calibration import get_calibration_manager
from composition.container import ServiceContainer, get_container
from src.core.interfaces import CalibrationScheduler

logger = logging.getLogger(__name__)


def build_calibration_scheduler() -> CalibrationScheduler:
    """Bot 侧 `CalibrationManager` 直接满足 `CalibrationScheduler` 端口。"""
    return get_calibration_manager()


def configure_runtime_implementations(
    container: Optional[ServiceContainer] = None,
) -> ServiceContainer:
    """Wire concrete bot-side implementations into the container (idempotent)."""
    target = container if container is not None else get_container()
    target.set_calibration_scheduler_provider(build_calibration_scheduler)
    target.set_media_storage_provider(build_media_storage)
    logger.debug("Composition root wired: calibration scheduler + media storage")
    return target
