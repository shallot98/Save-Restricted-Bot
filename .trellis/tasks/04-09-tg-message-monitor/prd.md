# brainstorm: telegram group/channel message monitor

## Goal

实现一个脚本，用于检测指定 Telegram 群组或频道中的消息。目标对象可以是公开或私有聊天，但前提是运行脚本的 Telegram 账号本身已经具备访问权限。当前目标尚未锁定为“仅实时监听”“仅历史回溯”还是“两者都要”。

## What I already know

* 用户希望“检测某个 tg 群或者频道，不管是否公开还是私有，检测全部的消息”。
* 仓库当前已经是一个 Telegram 自动化项目，运行时依赖包含 `pyrogram` 与 `tgcrypto`。
* 项目已存在 user session 模式：`bot/core/client.py` 会初始化 User Client，并支持从 `STRING` 或现有 `.session` 文件启动。
* 项目 README 已声明支持 public/private/bot chats，并且已有监控类脚本 `scripts/pt_pay_monitor.py` 用于监听指定 source chat 的消息。
* `bot/services/pt_pay_runtime.py` 已有独立 user session、source chat 解析、消息监听的现成模式，可复用为新脚本的实现参考。

## Assumptions (temporary)

* 已确认采用 Telegram 用户账号（MTProto / user client）方案。
* “私有群/私有频道”只指脚本登录账号已加入或已获得邀请访问权限的对象，不包含绕过权限读取。
* 已确认 MVP 为：仅拉取目标 chat 的现有历史消息，不做实时监听。

## Open Questions


## Requirements (evolving)

* 提供一个可指定源 chat 与目标 chat 的脚本入口。
* 使用 Telegram 用户账号（Pyrogram user session）进行历史消息拉取。
* 能处理公开与私有群/频道，前提是账号有访问权限。
* MVP 只处理历史消息，不处理实时新消息。
* 拉取到的历史消息应复制到用户指定的目标频道或群聊，并隐藏原来源。
* 脚本应支持断点续传：重复运行时跳过已复制过的源消息。
* 尽量复用当前仓库已有 Pyrogram / user session 方案。

## Technical Approach

* 采用用户账号（MTProto / Pyrogram user client）而非仅 Bot API。
* 初始实现优先做成 `scripts/` 下的独立脚本，避免侵入主 Bot 流程。
* 继续复用现有 session / chat resolve 模式，但主流程改为历史遍历而非 idle 监听。
* 历史消息写入目标 chat 时，默认使用 copy 语义而非 forward 语义，以隐藏原来源。
* 通过本地状态文件或轻量数据库记录已处理的 `source_chat_id + message_id`，实现断点续传。
* 失败处理采用 best-effort：自动处理 `FloodWait`/重试；单条失败记录后继续；权限/登录等全局致命错误直接退出。

## Decision (ADR-lite)

**Context**: 用户希望覆盖公开与私有群/频道的“全部消息”，而 Bot-only 模式受 Telegram 群组 privacy mode 与权限限制。
**Decision**: 选择用户账号监听方案。
**Consequences**: 需要可用的用户 session；仅能读取该账号本身有权限访问的聊天；相较 Bot-only 方案，覆盖更接近“全部消息”。目标 chat 也要求该账号具备发言/发帖权限。

## Acceptance Criteria (evolving)

* [ ] 脚本可接受源 chat 与目标 chat 标识（chat_id / username / 其他可解析引用）
* [ ] 脚本能够连接 Telegram 并成功读取源 chat 的历史消息
* [ ] 对私有源 chat，在账号已具备访问权限时可正常工作
* [ ] 脚本仅拉取历史消息，不启动实时监听
* [ ] 拉取到的历史消息可以成功复制到目标频道或群聊
* [ ] 重复运行时，已复制过的源消息不会被重复复制
* [ ] 单条消息复制失败不会中断整次历史回放，最终会输出失败统计

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Implementation Plan (small PRs)

* PR1: 新增独立历史复制脚本与参数解析，复用现有 user session/chat resolve 模式
* PR2: 实现历史遍历 + copy_message/copy_media_group + FloodWait/重试
* PR3: 实现断点续传状态存储、失败统计与基础测试/文档

## Out of Scope (explicit)

* 绕过 Telegram 权限模型读取未授权私有聊天
* 在需求未确认前直接改动主 Bot 流程
* 将消息持久化到数据库或 Web 界面（当前 MVP 不需要）
* 多源 chat 批量同步（当前 MVP 先做单源到单目标）

## Technical Notes

* Existing patterns:
  * `scripts/pt_pay_monitor.py`：独立脚本 + `pyrogram.idle()` 持续监听
  * `bot/services/pt_pay_runtime.py`：独立 user client、source chat 解析、消息处理运行时
  * `bot/core/client.py`：主项目 user client 初始化、session 复用模式
  * `bot/workers/message_worker.py`：已有 `copy_message` / `copy_media_group`，可用于隐藏原来源地复制消息
* Constraints:
  * 当前仓库存在大量未提交改动，实施时需尽量局部修改，避免误碰现有工作树
  * 当前规范索引文档存在，但具体指南仍较空，需要更多依赖仓库现有代码模式


## Research Notes

### What similar tools / official docs indicate

* Telegram Bot FAQ states that bots in channels where they are members can receive channel messages, and in groups they only receive all messages when they are admin or privacy mode is disabled; privacy-enabled bots only receive limited message classes [Telegram Bot FAQ, https://core.telegram.org/bots/faq].
* Telegram bot introduction docs state that bots added to groups only see relevant messages by default because of privacy mode [Telegram Bots Intro, https://core.telegram.org/bots].
* Pyrogram provides `get_chat_history()` for both users and bots, and its examples include retrieving full chat history [Pyrogram docs, https://docs.pyrogram.org/api/methods/get_chat_history].

### Constraints from our repo/project

* The repo already standardizes on Pyrogram + session files.
* The repo already has a dedicated monitor script pattern using user sessions.
* We should prefer a standalone script under `scripts/` before touching the main bot flow.

### Feasible approaches here

**Approach A: User session monitor (Recommended)**

* How it works: use a logged-in Telegram user account via existing `STRING` / `.session`, resolve target chat, optionally backfill history, then subscribe to new messages.
* Pros: works for public and private chats as long as the account has access; best fit for “all messages”.
* Cons: requires user session, not just bot token.

**Approach B: Bot-only monitor**

* How it works: use the bot account only and listen to updates in chats/channels where the bot is present.
* Pros: simpler deployment if the user insists on bot-only.
* Cons: cannot reliably satisfy “all messages in any group/channel”; group visibility depends on privacy/admin settings.

**Approach C: Hybrid**

* How it works: prefer user session when available, otherwise degrade to bot mode.
* Pros: flexible deployment.
* Cons: semantics become inconsistent; “全部消息” becomes conditional and harder to explain/test.
