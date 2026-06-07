# Telegram 历史复制脚本

脚本路径：`scripts/tg_history_copy.py`

## 作用

使用 **Telegram 用户账号 session** 读取某个源群/频道的历史消息，并把消息复制到另一个目标群/频道。

特性：

- 支持公开 / 私有 chat（前提是该账号本身有访问权限）
- 公开源默认优先使用 Bot API 服务端直拷；失败后再用用户 session 直拷；仅在源消息禁止转发时回退到 **下载后重发**
- 支持断点续传；重复运行时跳过已成功复制的源消息
- 遇到单条失败会继续，结束时输出失败统计
- 内置合规风控层：最小发送间隔、`FloodWait` 统一退避、连续失败熔断、每小时发送预算

## 用法

```bash
python3 scripts/tg_history_copy.py \
  --source-chat -1001234567890 \
  --dest-chat -1009876543210
```

常用参数：

- `--session-name`：独立 user session 名称，默认 `history_copy`
- `--state-db`：断点续传状态库，默认 `data/history_copy_state.db`
- `--batch-size`：每批历史读取条数
- `--history-limit`：只复制最近 N 条历史消息
- `--flood-retries`：`FloodWait` 最大重试次数
- `--rate-limit-delay`：最小发送间隔秒数
- `--hourly-send-budget`：滑动一小时窗口内允许复制的最大消息数，`0` 表示关闭预算
- `--failure-threshold`：连续失败达到阈值后触发自动冷却，`0` 表示关闭熔断
- `--failure-cooldown-seconds`：连续失败熔断后的自动冷却秒数
- `--floodwait-buffer-seconds`：在 Telegram 返回 `FloodWait` 基础上追加的缓冲秒数

默认值：

- `--rate-limit-delay 1.0`
- `--hourly-send-budget 1800`
- `--failure-threshold 3`
- `--failure-cooldown-seconds 300`
- `--floodwait-buffer-seconds 1.0`

## 行为说明

- 当前实现按 Telegram 历史接口返回顺序读取消息，再按 oldest-first 顺序处理
- 公开源单条消息优先使用 Bot Client 的 `copy_message`
- 公开源完整媒体组优先使用 Bot Client 的 `copy_media_group`
- 私有源或 Bot Client 直拷失败时，继续使用用户 session 的 `copy_message` / `copy_media_group`
- 若命中 `CHAT_FORWARDS_RESTRICTED` / `ChatForwardsRestricted`，则自动回退到下载后重发
- 媒体组在部分已完成断点恢复场景下，会按逐条方式补齐剩余消息
- 断点状态按 `(source_chat_id, dest_chat_id, message_id)` 记录
- 复制动作会统一先经过风控层；若达到预算、命中冷却或最小发送间隔，会自动暂停并在冷却结束后继续
- 遇到 `FloodWait` 时，不再只做局部 sleep，而是写入统一冷却状态并由后续复制自动恢复
- 连续失败达到阈值时会触发自动熔断冷却；冷却结束后脚本继续运行，不需要人工确认

## 前提条件

- 已配置可用的 Telegram 用户 session
- 该账号对源 chat 有读取权限
- 该账号对目标 chat 有发言 / 发帖权限

## 风控日志示例

```text
🛡️ 风控暂停发送: operation=复制消息 reason=min_interval wait=1.0s
🛡️ 捕获 FloodWait，交由风控层统一退避: operation=复制媒体组 cooldown=17.0s
🛡️ 连续失败达到阈值，进入冷却: operation=复制消息 cooldown=300.0s
🛡️ 风控冷却结束，恢复发送: operation=复制消息
```
