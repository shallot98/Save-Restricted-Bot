# 更新日志 v2.2.0

## 发布日期
2024

## 主要更新

### 🗂️ 1. 数据存储独立化

**改进说明**：
将数据目录从项目相对路径 `data/` 迁移到系统级绝对路径 `/data/save_restricted_bot/`

**优势**：
- ✅ 避免与其他程序数据冲突
- ✅ 系统级独立存储，更安全
- ✅ 便于集中管理和备份
- ✅ Docker 容器数据持久化更可靠

**影响文件**：
- `main.py` - 更新 DATA_DIR 默认值
- `database.py` - 更新 DATA_DIR 默认值
- `docker-compose.yml` - 更新 volume 挂载路径

**新增文件**：
- `migrate_to_system_data_dir.py` - 数据迁移脚本

---

### 🚀 2. 启动时配置自动初始化

**改进说明**：
程序启动时自动检查并创建配置文件，无需手动创建

**功能**：
- 自动检测 `config.json` 是否存在
- 不存在时自动创建包含默认字段的配置
- 自动创建 `watch_config.json` 为空监控列表 `{}`
- 已存在的配置不会被覆盖

**优势**：
- ✅ 首次部署更简单
- ✅ 减少配置错误
- ✅ 提升用户体验

**影响文件**：
- `main.py` - 添加配置初始化逻辑

---

### 📸 3. 网页笔记多媒体容量扩展（最多9张）

**改进说明**：
明确限制每条笔记最多支持 9 张媒体（图片/视频），类似 Telegram 标准

**验证机制**：
1. **数据库层面**：`add_note()` 函数验证 `len(media_list) <= 9`
2. **处理层面**：`process_media_group()` 函数限制处理前 9 张媒体

**超出处理**：
- 自动忽略超过 9 张的媒体
- 在日志中记录警告信息
- 不会导致程序崩溃

**影响文件**：
- `database.py` - `add_note()` 函数添加验证
- `main.py` - `process_media_group()` 函数添加限制

---

### 🔍 4. 网页搜索 UI 改进（可折叠设计）

**改进说明**：
搜索框默认收起为图标，点击展开，提升界面简洁度

**功能特性**：
- 🔍 默认只显示搜索图标（圆形按钮）
- 点击图标展开搜索输入框
- 展开后自动聚焦到输入框
- 点击外部且输入框为空时自动收起
- 如果有搜索词，保持展开状态
- 平滑的滑入动画（0.3秒）

**优势**：
- ✅ 界面更简洁
- ✅ 节省屏幕空间
- ✅ 交互更流畅
- ✅ 响应式设计友好

**影响文件**：
- `templates/notes.html` - 更新 CSS 和 HTML 结构，添加 JavaScript 控制

---

## 📂 新数据目录结构

```
/data/save_restricted_bot/
├── config/
│   ├── config.json              # Bot 配置（自动创建）
│   └── watch_config.json        # 监控配置（自动创建）
├── media/                       # 媒体文件
├── logs/                        # 日志文件（预留）
└── notes.db                     # 笔记数据库
```

---

## 🔄 升级指南

### 快速升级

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 运行数据迁移脚本（需要 sudo）
sudo python3 migrate_to_system_data_dir.py

# 3. 重启服务
systemctl restart your-bot-service
# 或
docker-compose down && docker-compose up -d --build
```

### Docker 用户

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 创建新数据目录
sudo mkdir -p /data/save_restricted_bot

# 3. 重新构建并启动容器
docker-compose down
docker-compose up -d --build
```

---

## ⚠️ 重要提醒

1. **升级前务必备份数据**：
   ```bash
   tar -czf data_backup_$(date +%Y%m%d).tar.gz data/
   ```

2. **确认权限**：
   ```bash
   sudo chown -R $(whoami):$(whoami) /data/save_restricted_bot/
   ```

3. **验证迁移**：
   - 检查配置文件是否正确加载
   - 测试监控任务是否正常
   - 验证网页笔记是否能访问
   - 测试新笔记是否能正常保存

4. **清理旧数据**：
   只有在确认新数据目录工作正常后，才删除旧的 `data/` 目录

---

## 🐛 Bug 修复

无重大 Bug 修复，本次为功能改进版本。

---

## 📝 配置变更

### Environment Variables

**旧配置**：
```bash
DATA_DIR=data
```

**新配置**：
```bash
DATA_DIR=/data/save_restricted_bot
# 或者不设置，使用默认值
```

### Docker Compose

**旧配置**：
```yaml
volumes:
  - ./data:/app/data
environment:
  - DATA_DIR=/app/data
```

**新配置**：
```yaml
volumes:
  - /data/save_restricted_bot:/data/save_restricted_bot
environment:
  - DATA_DIR=/data/save_restricted_bot
```

---

## 🔗 相关文档

- 📖 详细升级指南：[DATA_DIR_UPGRADE_GUIDE.md](DATA_DIR_UPGRADE_GUIDE.md)
- 📖 数据保护指南：[DATA_PROTECTION.md](DATA_PROTECTION.md)
- 📖 多图支持文档：[MULTI_IMAGE_SUPPORT.md](MULTI_IMAGE_SUPPORT.md)

---

## 📊 版本对比

| 功能 | v2.1.x | v2.2.0 |
|------|--------|--------|
| 数据目录 | `./data/` | `/data/save_restricted_bot/` |
| 配置初始化 | 手动创建 | 自动创建 |
| 媒体数量限制 | 无明确限制 | 最多 9 张 |
| 搜索框 | 始终展开 | 可折叠 |
| Docker Volume | `./data:/app/data` | `/data/save_restricted_bot:/data/save_restricted_bot` |

---

## 🤝 贡献者

感谢所有为这个版本贡献的开发者！

---

## 📞 获取帮助

如遇问题：
1. 查看 [DATA_DIR_UPGRADE_GUIDE.md](DATA_DIR_UPGRADE_GUIDE.md) 故障排查部分
2. 检查日志输出
3. 提交 Issue 到 GitHub 仓库

---

**版本**: v2.2.0  
**发布日期**: 2024  
**兼容性**: 向后兼容 v2.1.x
