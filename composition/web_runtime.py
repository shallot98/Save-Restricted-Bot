"""组合根：装配 Flask 进程的表现层依赖。

与 `composition/bot_runtime.py` 同构——`web/` 只声明需要什么
（`web.services.WebServices`），构造在这里，注入在进程入口 `app.py`：

    app.py
      → composition.wiring.configure_runtime_implementations()   # 端口 ← 实现
      → composition.web_runtime.build_web_services()             # 服务实例
      → web.create_app(services=...)                             # 注入 Flask

拆掉的是 `web/routes/` 里 5 处 `from composition.container import get_xxx()`
以及 `web/__init__.py` 对 `composition.wiring` 的调用（报告 §5.3 规则 3）。
"""

from __future__ import annotations

from composition.calibration import get_calibration_manager
from composition.container import (
    get_calibration_service,
    get_calibration_workflow_service,
    get_note_service,
    get_qbittorrent_service,
)
from web.services import WebServices


def _reload_calibration_config() -> None:
    """让 Bot 侧校准管理器重读配置。

    Web 侧只需要这一个动作，所以注入的是可调用端口而不是 `CalibrationManager`
    实例——把整个管理器递给路由等于让表现层重新认识 bot 的实现细节。
    """
    get_calibration_manager().reload_config()


def build_web_services() -> WebServices:
    """Build the service bundle bound to the Flask application."""
    return WebServices(
        note_service=get_note_service(),
        calibration_service=get_calibration_service(),
        calibration_workflow_service=get_calibration_workflow_service(),
        qbittorrent_service=get_qbittorrent_service(),
        reload_calibration_config=_reload_calibration_config,
    )
