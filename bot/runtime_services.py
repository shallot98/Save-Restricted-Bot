"""Bot 表现层的运行时依赖契约（由组合根在进程启动时构造并注入）。

为什么需要这个 DTO
------------------
`bot/` 曾在 11 处写 `from composition.container import get_xxx()` 就地取服务
——报告 §5.3 规则 3 明令禁止的服务定位；而 `composition/` 自身又反向 import
`bot.services` / `bot.storage`，构成 **composition ⇄ bot 双向环**。这正是
`.importlinter` 的层序契约此前无法把 `composition` 纳入的原因（见该文件契约 4 注释）。

依赖方向收敛为单向后：

    main.py（进程入口，不属于任何被约束的包）
        → composition.bot_runtime.build_bot_services()
        → bot.handlers.register_all_handlers(bot, acc, queue, services=...)

`bot/` 只认识本模块里自己定义的 DTO，不再认识组合根。DTO 由 `bot/` 而非
`composition/` 拥有，是因为反过来会让 `bot/` 为了写类型标注重新 import 组合根，
把刚拆掉的那条边原样装回去。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 仅用于类型标注：避免启动期把整条 application 层拉进 bot 的导入图
    from bot.services.calibration_manager import CalibrationManager
    from src.application.services import (
        MessageWorkerService,
        WatchService,
        WatchSetupService,
    )


@dataclass(frozen=True)
class BotServices:
    """Bot 进程一次性装配、随后逐层显式传递的服务集合。

    字段刻意保持窄：只放**当前确实被表现层调用**的服务。新增字段前先确认调用方，
    否则就是把组合根的全部实现清单又搬回了表现层（§5.3 规则 10 的同类问题）。
    """

    watch_service: "WatchService"
    watch_setup_service: "WatchSetupService"
    message_worker_service: "MessageWorkerService"
    calibration_manager: "CalibrationManager"
