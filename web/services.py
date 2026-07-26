"""Flask 表现层的运行时依赖契约与访问入口。

为什么需要它
------------
`web/routes/` 曾在 5 处写 `from composition.container import get_xxx()` 就地取
服务（报告 §5.3 规则 3），而 `composition/` 又反向 import `bot.services` /
`bot.storage`，构成 composition ⇄ 交付层的双向环——`.importlinter` 的层序契约
因此一直无法把 `composition` 纳入。

改造后依赖单向：

    app.py（进程入口，不属于任何被约束的包）
      → composition.web_runtime.build_web_services()
      → web.create_app(services=...)   → bind_services(app, ...)
      → 路由函数 get_services()        → current_app.extensions

`WebServices` 由 `web/` 而非 `composition/` 拥有：反过来会让 `web/` 为了写类型
标注重新 import 组合根，把刚拆掉的边原样装回去。

线程注意事项
------------
`get_services()` 依赖 Flask 应用上下文。异步校准任务跑在
`AsyncCalibrationManager` 的线程池里，**没有**应用上下文，因此提交任务的路由必须
在请求内先取出需要的服务再放进闭包/参数——见 `web/routes/api.py::calibrate_async`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from flask import Flask, current_app

if TYPE_CHECKING:
    from src.application.services import (
        CalibrationService,
        CalibrationWorkflowService,
        NoteService,
        QBittorrentService,
    )

#: `app.extensions` 中的键名。用 extensions 而不是 app.config，是因为这里放的是
#: 活对象而非配置值，且 `app.config` 会被 `create_app(config=...)` 的调用方整体
#: update，容易被误覆盖。
EXTENSION_KEY = "srb_services"


@dataclass(frozen=True)
class WebServices:
    """Flask 进程一次性装配的服务集合。

    字段刻意保持窄：只放当前确实被路由调用的服务。`reload_calibration_config`
    是可调用端口而不是 `CalibrationManager` 实例——Web 侧只需要「重载配置」这
    一个动作，暴露整个管理器等于把 bot 的实现细节漏进路由。
    """

    note_service: "NoteService"
    calibration_service: "CalibrationService"
    calibration_workflow_service: "CalibrationWorkflowService"
    qbittorrent_service: "QBittorrentService"
    reload_calibration_config: Callable[[], None]


def bind_services(app: Flask, services: WebServices) -> None:
    """把服务集合绑定到应用实例（应用工厂调用）。"""
    app.extensions[EXTENSION_KEY] = services


def get_services() -> WebServices:
    """取当前应用绑定的服务集合。

    未绑定时直接抛错而不是回落到全局容器：静默回落会让「装配漏了」这件事在生产
    上完全不可见（§5.3 规则 5）。
    """
    services = current_app.extensions.get(EXTENSION_KEY)
    if not isinstance(services, WebServices):
        raise RuntimeError(
            "当前 Flask 应用未绑定 WebServices；"
            "请检查 app.py → create_app(services=...) 的装配路径"
        )
    return services
