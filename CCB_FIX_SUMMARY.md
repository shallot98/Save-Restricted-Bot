# CCB Up Codex 启动失败修复总结

## 问题描述

`ccb up codex` 命令在 tmux 环境中启动失败，错误信息显示尝试使用 wezterm 而不是 tmux。

## 根本原因

1. **环境变量污染**: `WEZTERM_PANE=0` 和 `CCB_TERMINAL=wezterm` 被错误地设置在环境中
2. **.bashrc 自动检测逻辑缺陷**: 原始的 WEZTERM_PANE 自动检测代码在 tmux 环境中也会运行，因为它只检查 `TERM_PROGRAM` 而没有检查 `TMUX` 环境变量
3. **ccb 检测优先级**: ccb 脚本优先检查 `WEZTERM_PANE` 环境变量，导致即使在 tmux 中也会被误判为 wezterm 环境

## 修复方案

### 1. 修改 .bashrc 自动检测逻辑

**修改前:**
```bash
if [ -z "$WEZTERM_PANE" ] && [ "$TERM_PROGRAM" = "WezTerm" ] && command -v wezterm &>/dev/null; then
```

**修改后:**
```bash
if [ -z "$WEZTERM_PANE" ] && [ -z "$TMUX" ] && [ "$TERM_PROGRAM" = "WezTerm" ] && command -v wezterm &>/dev/null; then
```

**关键改进**: 添加了 `[ -z "$TMUX" ]` 检查，确保只在非 tmux 环境中设置 WEZTERM_PANE

### 2. 禁用强制 CCB_TERMINAL 设置

**修改前:**
```bash
export CCB_TERMINAL=wezterm
```

**修改后:**
```bash
# 强制 ccb 使用 WezTerm (已禁用,让 ccb 自动检测)
# export CCB_TERMINAL=wezterm
```

### 3. 清理环境变量

创建了修复脚本 `/tmp/fix_ccb_env.sh`:
```bash
#!/bin/bash
# 从 tmux 全局环境中删除
tmux set-environment -gu CCB_TERMINAL 2>/dev/null
tmux set-environment -gu WEZTERM_PANE 2>/dev/null

# 从当前 shell 中删除
unset CCB_TERMINAL
unset WEZTERM_PANE
```

## 使用方法

### 临时解决方案（立即生效）

在子 shell 中运行 ccb:
```bash
(export CCB_TERMINAL=tmux; unset WEZTERM_PANE; ccb up codex)
```

### 永久解决方案

1. 运行修复脚本:
```bash
source /tmp/fix_ccb_env.sh
```

2. 重新加载 .bashrc:
```bash
source ~/.bashrc
```

3. 或者重新连接 tmux 会话:
```bash
# 退出当前会话
exit
# 重新连接
tmux attach
```

## 验证

修复后，ccb 应该能够正确检测 tmux 环境并使用 tmux 后端:
```bash
ccb up codex --no-claude
```

预期输出:
```
🚀 Claude AI 启动器
📅 2025-12-21 19:25:37
🔌 后端: codex
==================================================
🚀 启动 Codex 后端 (tmux)...
✅ Codex 已启动 (tmux: codex-16337-4094275)
```

## 技术细节

### ccb 终端检测优先级

1. 检查 `CCB_TERMINAL` 或 `CODEX_TERMINAL` 环境变量
2. 检查 `WEZTERM_PANE` 环境变量
3. 调用 `detect_terminal()` 函数自动检测
4. 兜底返回 None

### detect_terminal() 函数逻辑

1. 如果 `WEZTERM_PANE` 存在，返回 "wezterm"
2. 如果 `TMUX` 存在，返回 "tmux"
3. 如果 wezterm 可执行文件存在，返回 "wezterm"
4. 如果 tmux 可执行文件存在，返回 "tmux"
5. 返回 None

## 相关文件

- `/root/.bashrc` - Shell 配置文件
- `/root/.local/bin/ccb` - ccb 主脚本
- `/root/.local/share/codex-dual/lib/terminal.py` - 终端检测模块
- `/tmp/fix_ccb_env.sh` - 环境变量修复脚本

## 日期

2025-12-21
