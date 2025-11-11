# Release Notes - v2.3.2

## 🚀 版本信息

- **版本号**: v2.3.2
- **发布日期**: 2024
- **类型**: Bug 修复版本
- **优先级**: 推荐升级

---

## 📝 概述

v2.3.2 是一个重要的 Bug 修复版本，解决了用户反馈的两个关键体验问题：
1. 网页搜索面板自动弹出影响用户体验
2. 机器人在群组/频道中无法使用

---

## 🐛 修复的问题

### 问题 1: 搜索面板自动弹出
**症状**: 
- 每次刷新网页，搜索/筛选框都会自动显示
- 影响用户浏览笔记的初始体验

**修复**:
- 在 CSS 中添加 `display: none;` 使搜索面板默认隐藏
- 只有点击搜索图标 (🔍) 时才会弹出

**受益用户**: 所有使用 Web 界面的用户

---

### 问题 2: 群组/频道中无法使用机器人
**症状**:
- 机器人添加到群组后，即使提及机器人也无法使用转发和批量下载功能
- 限制了机器人的使用场景

**修复**:
- 修改消息过滤器，支持 `filters.mentioned` 和 `filters.reply`
- 现在支持通过 `@bot_username` 提及机器人或回复机器人的消息来使用

**受益用户**: 需要在团队群组或讨论频道中使用机器人的用户

---

## ✨ 新增功能

虽然这是一个 Bug 修复版本，但群组支持的修复实际上扩展了机器人的使用场景：

### 群组使用场景
1. **团队协作**: 在团队群组中共享和转发受限内容
2. **讨论群**: 在讨论群中快速获取频道内容
3. **工作群**: 批量下载和处理消息

### 使用方法
```
在群组中:
@your_bot_name https://t.me/channel/123

或者回复机器人的消息:
https://t.me/channel/456
```

---

## 📊 技术变更

### 修改的文件
1. `templates/notes.html` (Line 212)
   - 添加 `display: none;` 到 `.search-panel` CSS 类

2. `main.py` (Line 1347)
   - 修改消息过滤器从 `filters.private` 到 `(filters.private | filters.mentioned | filters.reply)`

### 新增的文件
1. `test_fixes.py` - 自动化测试脚本
2. `BUG_FIXES.md` - 详细的 Bug 修复文档
3. `CHANGELOG_v2.3.2.md` - 完整变更日志
4. `RELEASE_NOTES_v2.3.2.md` - 本文件

---

## 🔄 升级指南

### 前置要求
- 现有版本: v2.3.1 或更早
- 无需数据迁移
- 无需修改配置

### 升级步骤

#### 使用 Docker Compose (推荐)
```bash
cd /path/to/save-restricted-bot
git pull origin main
docker-compose down
docker-compose up -d
```

#### 使用 Docker
```bash
cd /path/to/save-restricted-bot
git pull origin main
docker stop save-restricted-bot
docker rm save-restricted-bot
docker build -t save-restricted-bot .
docker run -d --name save-restricted-bot \
  -v /data/save_restricted_bot:/data/save_restricted_bot \
  -e DATA_DIR=/data/save_restricted_bot \
  --env-file .env \
  save-restricted-bot
```

#### 本地部署
```bash
cd /path/to/save-restricted-bot
git pull origin main
pkill -f "python.*main.py"
python3 main.py &
```

### 验证升级
```bash
python3 test_fixes.py
```

预期输出:
```
✅ 测试 1 (搜索面板默认隐藏): 通过
✅ 测试 2 (群组消息处理): 通过
```

---

## 📖 使用文档

### 搜索面板使用
1. 打开 Web 界面：http://your-server:5000
2. 点击顶部导航栏的搜索图标 (🔍)
3. 在弹出的搜索面板中输入筛选条件
4. 点击"搜索"按钮或"清除筛选"按钮

### 群组使用指南

#### 设置机器人（可选但推荐）
1. 找到 @BotFather
2. 发送 `/setprivacy`
3. 选择您的机器人
4. 选择 `Disable` (关闭隐私模式)

#### 在群组中使用
方式 1 - 提及机器人:
```
@your_bot_name https://t.me/channel/123
```

方式 2 - 回复机器人:
1. 回复机器人发送的任何消息
2. 在回复中发送链接

#### 支持的功能
- ✅ 单条消息转发
- ✅ 批量消息下载 (范围)
- ✅ 加入频道/群组
- ✅ 私有频道消息获取
- ✅ 公开频道消息获取

---

## ⚠️ 注意事项

### 隐私模式
如果保持隐私模式开启，机器人在群组中只能：
- 看到提及自己的消息 (`@bot_username`)
- 看到回复自己消息的消息
- 看到命令消息 (`/start`, `/help`, `/watch`)

**建议**: 关闭隐私模式以获得最佳体验

### 群组权限
确保机器人在群组中具有以下权限：
- ✅ 发送消息
- ✅ 发送媒体文件 (如果需要转发图片/视频)
- ✅ 回复消息

---

## 🧪 测试覆盖

### 自动化测试
- ✅ 搜索面板默认隐藏测试
- ✅ 消息过滤器配置测试
- ✅ CSS 语法验证
- ✅ Python 语法验证

### 手动测试建议
1. **Web 界面测试**:
   - 打开浏览器，访问 Web 界面
   - 确认搜索面板不会自动显示
   - 点击搜索图标，确认面板正常弹出

2. **群组功能测试**:
   - 将机器人添加到测试群组
   - 发送 `@bot_username https://t.me/test/123`
   - 确认机器人正常响应并转发消息

3. **私聊功能测试**:
   - 私聊机器人
   - 发送消息链接
   - 确认原有功能正常工作

---

## 📈 性能影响

### 性能变化
- 无性能影响
- 消息处理逻辑略微扩展，但影响可忽略不计
- Web 界面加载速度无变化

### 资源使用
- CPU: 无明显变化
- 内存: 无明显变化
- 磁盘: 无变化
- 网络: 无变化

---

## 🔒 安全性

### 安全影响
- ✅ 无新增安全风险
- ✅ 群组消息处理仍然需要明确提及或回复
- ✅ 配置文件和数据仍然安全存储在 DATA_DIR

### 隐私保护
- ✅ 群组中的消息不会被自动处理
- ✅ 只有提及或回复机器人的消息才会被处理
- ✅ 符合 Telegram Bot API 的隐私要求

---

## 🔮 未来计划

v2.3.2 后的发展方向：
1. 更多的群组管理功能
2. 增强的搜索过滤选项
3. 更好的移动端体验
4. 性能优化和缓存改进

---

## 📞 支持与反馈

### 问题报告
- GitHub Issues: https://github.com/your-repo/issues
- 提交 Bug 报告时请包含:
  - 版本号 (v2.3.2)
  - 操作系统和部署方式
  - 详细的错误信息和日志
  - 复现步骤

### 功能建议
- GitHub Discussions: https://github.com/your-repo/discussions
- 欢迎提出改进建议

### 文档
- 英文文档: [README.md](README.md)
- 中文文档: [README.zh-CN.md](README.zh-CN.md)
- Bug 修复详情: [BUG_FIXES.md](BUG_FIXES.md)
- 完整变更日志: [CHANGELOG_v2.3.2.md](CHANGELOG_v2.3.2.md)

---

## 🙏 致谢

感谢所有用户的反馈和支持！

特别感谢报告这些问题的用户：
- 搜索面板自动弹出问题的报告者
- 群组使用需求的提出者

你们的反馈帮助我们不断改进产品！

---

## 📜 许可证

本项目保持原有许可证不变。

---

**版本**: v2.3.2  
**发布日期**: 2024  
**状态**: ✅ 生产就绪  
**测试**: ✅ 已通过所有测试  
**推荐**: ✅ 推荐所有用户升级
