"""组合根：装配 Bot 进程的表现层依赖。

这里是 Bot 侧「谁来构造服务」的唯一答案。`bot/` 自己只声明需要什么
（`bot.runtime_services.BotServices`），拿到实例的责任在组合根，注入的动作在
进程入口 `main.py`：

    main.py
      → composition.wiring.configure_runtime_implementations()   # 端口 ← 实现
      → composition.bot_runtime.build_bot_services()             # 服务实例
      → bot.handlers.register_all_handlers(..., services=...)    # 注入表现层

拆掉的是 `bot/` 里 11 处 `from composition.container import get_xxx()`
（报告 §5.3 规则 3）。依赖方向由此单向化为 composition → bot，
`.importlinter` 的层序契约才能把 composition 放到最顶层。
"""

from __future__ import annotations

from bot.runtime_services import BotServices
from composition.calibration import get_calibration_manager
from composition.container import (
    get_message_worker_service,
    get_watch_service,
    get_watch_setup_service,
)


def build_bot_services() -> BotServices:
    """Build the service bundle handed to the Telegram presentation layer.

    容器内部本就是惰性单例，这里取用即固化引用：整个 Bot 进程共享同一组实例，
    与改动前 `get_xxx()` 每次返回同一单例的行为等价，只是取用点从散落的业务代码
    收敛到了这一处。
    """
    return BotServices(
        watch_service=get_watch_service(),
        watch_setup_service=get_watch_setup_service(),
        message_worker_service=get_message_worker_service(),
        calibration_manager=get_calibration_manager(),
    )
