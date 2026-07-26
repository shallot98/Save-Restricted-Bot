"""
Composition Root - 组合根
=========================

**唯一认识所有具体实现的地方。**

这里是依赖注入的装配层：把 `src.infrastructure` 的具体仓储接到
`src.application` 的服务上，再由进程入口注入 `bot/` `web/` 两个表现层。

Phase 3 起，表现层**不再反向取用**本包：`main.py` 用
`composition.bot_runtime.build_bot_services()` 构造 `bot.runtime_services.BotServices`
后经 `register_all_handlers(..., services=...)` 注入；`app.py` 用
`composition.web_runtime.build_web_services()` 构造 `web.services.WebServices`
后经 `create_app(services=...)` 注入。`bot/` 与 `web/` 对 `composition` 的
import 数为 0，`composition` 因此得以进入 `.importlinter` 的层序契约（最顶层）。

为什么不放在 `src/core/`：
    组合根天然需要 import 每一个具体实现。放在最内层会把
    `src.application` / `src.infrastructure` 顶层倒灌进 `src.core`，
    形成 `src.core → src.application → ... → src.core` 的依赖环
    （见 docs/ARCHITECTURE_REFACTOR_REPORT_2026-07-26.md §3 P1-1）。
    组合根位于所有层之外，依赖方向因此单向收敛：

        main.py / app.py → composition/ → bot/ · web/ → src.application → src.domain
                                                              ↑
                                                      src.infrastructure

分层约束：
    - `composition` 可以 import 任何一层，反向为 0（层序契约守住）
    - `src/` 内不得 import `bot/` `web/`（窄端口在 `src.core.interfaces`，
      具体实现由 `composition/wiring.py` 在启动期注入）
    - `src/` 内不得 import `composition`（顶层与函数内延迟 import 一律不许）
      Phase 3 已无例外：`src/compat` 整包删除，原先那 5 处函数内延迟 import
      （旧版 watch config 外观）随函数一起搬回仓库根 `config.py`。根模块位于
      组合根之上、不入 import-linter 契约，是遗留外观的正确归属。四条契约
      现已零 `ignore_imports` 豁免。

注意：`composition.wiring` 不在本包 `__init__` 里再导出——它顶层 import bot，
提前拉起会把 bot 侧模块塞进任何只想拿容器的调用方（含根 `database.py`）。
入口按需 `from composition.wiring import configure_runtime_implementations`。
"""

from composition.container import (
    ServiceContainer,
    get_container,
    get_note_service,
    get_watch_service,
    get_calibration_service,
    get_watch_setup_service,
    get_qbittorrent_service,
    get_calibration_workflow_service,
    get_message_worker_service,
)

__all__ = [
    "ServiceContainer",
    "get_container",
    "get_note_service",
    "get_watch_service",
    "get_calibration_service",
    "get_watch_setup_service",
    "get_qbittorrent_service",
    "get_calibration_workflow_service",
    "get_message_worker_service",
]
