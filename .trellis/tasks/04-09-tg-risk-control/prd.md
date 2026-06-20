# brainstorm: telegram anti-risk control system

## Goal

为当前项目增加一个 Telegram 侧的“合规型风控系统”，目标不是绕过平台限制，而是通过节流、退避、熔断、告警和账号健康保护，降低因为发送过快、失败过多、并发过高或异常模式而触发 Telegram 限流/封禁风险的概率。

## What I already know

* 用户提出“做一个风控系统，防止被 tg 风控”。
* 仓库里已经存在多处 Telegram 侧速率控制与重试基础设施：
  * `bot/workers/message_worker.py` 中已有 `FloodWait` 处理、重试与 `RATE_LIMIT_DELAY`。
  * `bot/services/history_copy_runtime.py` 中已有 `FloodWait` 重试、逐条失败继续、致命错误退出。
  * `scripts/pt_pay_monitor.py` / `bot/services/pt_pay_runtime.py` 中已有 `poll_interval`、`send_interval`、队列和串行发送模式。
* 仓库里已有通用监控/告警配置样式：`config.example.py` 中定义了 performance / slow_query / error_tracking / alerting / storage。
* 当前代码中的 Telegram 风控相关逻辑是“分散式”的，尚未看到统一的风险预算、全局限流器、熔断器或 Telegram 账号健康状态机。

## Assumptions (temporary)

* 这个“风控系统”应当做成 **合规保护层**，而不是做账号轮换、伪装、指纹对抗之类规避机制。
* 已确认 MVP 覆盖范围：仅新做的历史复制脚本。
* 已确认能力范围为增强版：全局发送节流、`FloodWait` 统一退避、连续失败熔断、冷却恢复、每小时发送预算。

## Open Questions

* 无阻塞性需求问题，已具备进入实现阶段的条件。


## Requirements (evolving)

* 需要一个统一、可复用的 Telegram 风险控制层，但 MVP 先接入历史复制脚本。
* 需要至少包含：全局发送间隔、`FloodWait` 统一退避、连续失败熔断、冷却恢复、每小时发送预算。
* 当触发熔断或预算耗尽时，脚本应自动进入冷却期，并在冷却结束后自动恢复运行。
* 应优先复用现有的 `FloodWait` / 重试 / 发送间隔模式，而不是到处复制逻辑。
* 应支持观测：至少能看到触发了什么保护动作，以及为什么暂停/限速。
* 设计上要保留未来扩展到其他 Telegram 出站路径的可能。

## Acceptance Criteria (evolving)

* [ ] 对历史复制脚本的 Telegram 出站动作，能统一应用节流/退避/暂停策略
* [ ] 能记录风控事件（如 `FloodWait`、连续失败、熔断开启、恢复、预算耗尽）
* [ ] 每小时发送预算达到阈值时会执行预定义保护动作
* [ ] 不需要通过静默 fallback 掩盖错误，保护动作与失败原因应可见

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Technical Approach

* 为 `scripts/tg_history_copy.py` 抽取一个独立的 Telegram 风控层，而不是把风控逻辑散落在复制循环里。
* 风控层至少维护：发送时间窗计数、连续失败计数、当前冷却状态、最近风控事件。
* 出站复制前统一经过风控决策：允许发送 / 延迟发送 / 进入冷却。
* `FloodWait` 不再只做局部 sleep，而要反馈给风控层，更新冷却状态与事件日志。
* 先只接入历史复制脚本，但接口设计允许后续复用到自动转发等其他出站路径。

## Decision (ADR-lite)

**Context**: 用户要降低 Telegram 对历史复制脚本的限流/封禁风险，但不希望做绕过式方案。
**Decision**: 先做历史复制脚本专用的增强版合规风控层，包含全局发送间隔、`FloodWait` 统一退避、连续失败熔断、冷却恢复、每小时发送预算。
**Consequences**: 能显著降低暴力发送风险，但会降低复制吞吐；MVP 只保护历史复制脚本，不立即覆盖其他 Telegram 出站流程。

## Implementation Plan (small PRs)

* PR1: 提取独立风控配置与状态模型，并把 `tg_history_copy` 接入统一发送前检查
* PR2: 实现预算、连续失败熔断、冷却恢复、`FloodWait` 事件上报
* PR3: 增加日志/统计输出、文档与单元测试

## Out of Scope (explicit)

* 绕过 Telegram 权限模型
* 账号农场、批量号轮换、设备/指纹对抗
* 在需求未锁定前直接改所有 Telegram 路径
* 当前 MVP 不直接接入自动转发、PT pay、签到等其他出站路径

## Technical Notes

* Existing patterns to reuse:
  * `bot/workers/message_worker.py`：FloodWait 重试、速率延迟、错误分类
  * `bot/services/history_copy_runtime.py`：best-effort 单条失败继续、致命错误退出
  * `bot/services/pt_pay_runtime.py`：串行化调用、轮询间隔、发送间隔
  * `config.example.py`：监控/告警配置结构
* Constraint:
  * 当前仓库工作树本来就有大量未提交变更，因此新改动应尽量模块化、可渐进接入
