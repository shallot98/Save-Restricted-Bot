# 部署验证指南 v2.3.0

本文档帮助您验证 Save-Restricted-Bot v2.3.0 的部署是否正确。

## 验证清单

### 1. 数据目录结构验证

运行以下命令检查数据目录结构：

```bash
# 方法 1: 使用测试脚本
python3 test_data_dir.py

# 方法 2: 手动检查
ls -la /data/save_restricted_bot/
ls -la /data/save_restricted_bot/config/
```

**预期输出**：
```
/data/save_restricted_bot/
├── config/
│   ├── config.json
│   └── watch_config.json
├── media/
├── logs/
└── notes.db
```

### 2. 配置文件验证

#### Docker 部署
```bash
# 检查配置文件是否在挂载的卷中
docker exec save-restricted-bot ls -la /data/save_restricted_bot/config/

# 检查环境变量
docker exec save-restricted-bot env | grep -E "TOKEN|ID|HASH|STRING|DATA_DIR"
```

#### 本地部署
```bash
# 检查配置文件
cat /data/save_restricted_bot/config/config.json

# 应该包含 TOKEN, ID, HASH, STRING
```

### 3. 监控配置持久化验证

#### 测试步骤
1. 启动 Bot
2. 使用 `/watch` 命令创建一个监控任务
3. 检查配置文件：
   ```bash
   # Docker
   docker exec save-restricted-bot cat /data/save_restricted_bot/config/watch_config.json
   
   # 本地
   cat /data/save_restricted_bot/config/watch_config.json
   ```
4. 重启 Bot
5. 再次检查配置文件（应该保持不变）

**预期结果**：
- 创建监控后，`watch_config.json` 立即包含任务配置
- 重启后，配置完整保留
- 在宿主机也能看到配置文件（Docker 部署）

### 4. 搜索 UI 功能验证

#### 测试步骤
1. 访问 Web 界面：http://localhost:5000
2. 登录（默认：admin/admin）
3. 点击顶部右侧的搜索图标（🔍）
4. 验证以下功能：
   - ✅ 搜索面板正确弹出
   - ✅ 面板包含：搜索框、来源选择、日期范围
   - ✅ 点击遮罩层可关闭面板
   - ✅ 点击关闭按钮（×）可关闭面板
   - ✅ 搜索功能正常工作
   - ✅ 筛选结果正确显示

#### 移动端验证
1. 使用手机浏览器访问
2. 点击搜索图标
3. 验证：
   - ✅ 搜索面板全屏显示
   - ✅ 按钮大小适合触摸
   - ✅ 日期选择器单列显示
   - ✅ 输入框大小合适

### 5. 媒体文件访问验证

#### 测试步骤
1. 创建一个带图片的监控任务（记录模式）
2. 等待消息被记录
3. 访问 Web 界面查看笔记
4. 验证图片能正常显示

**预期结果**：
- 图片正确显示
- 图片 URL 格式：`/media/<filename>`
- 图片文件存储在 `/data/save_restricted_bot/media/`

### 6. 日志和错误检查

#### Docker 部署
```bash
# 查看 Bot 日志
docker logs save-restricted-bot

# 应该看到以下消息：
# ✅ 已创建默认配置文件 /data/save_restricted_bot/config/config.json
# ✅ 已从环境变量初始化配置
# ✅ 已创建空监控配置文件 /data/save_restricted_bot/config/watch_config.json
```

#### 本地部署
```bash
# 启动时观察控制台输出
python main.py

# 应该看到初始化消息
```

### 7. 数据持久化验证（Docker）

#### 测试步骤
1. 创建监控任务
2. 记录一些笔记
3. 停止容器：
   ```bash
   docker-compose down
   ```
4. 检查宿主机数据：
   ```bash
   ls -la /data/save_restricted_bot/config/
   ls -la /data/save_restricted_bot/media/
   cat /data/save_restricted_bot/config/watch_config.json
   ```
5. 重启容器：
   ```bash
   docker-compose up -d
   ```
6. 验证数据完整性：
   - 监控任务依然存在
   - 笔记依然可见
   - 图片依然显示

**预期结果**：
- 所有数据完整保留
- 配置文件在宿主机可见且可编辑
- 容器重建不影响数据

## 常见问题排查

### 问题 1: 配置文件不在 DATA_DIR 中

**症状**：
- `watch_config.json` 在项目根目录
- 容器重启后配置丢失

**解决方案**：
```bash
# 检查代码是否使用正确的路径
grep "CONFIG_FILE\|WATCH_FILE" main.py

# 应该看到：
# CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
# WATCH_FILE = os.path.join(CONFIG_DIR, 'watch_config.json')
```

### 问题 2: 搜索面板不显示

**症状**：
- 点击搜索图标无反应
- 控制台有 JavaScript 错误

**解决方案**：
1. 检查浏览器控制台（F12）
2. 清除浏览器缓存
3. 验证 notes.html 包含新的搜索面板代码

### 问题 3: 媒体文件无法访问

**症状**：
- 图片不显示
- 404 错误

**解决方案**：
```bash
# 检查媒体目录权限
ls -la /data/save_restricted_bot/media/

# 检查 app.py 媒体路径
grep "media_dir" app.py

# 应该看到：
# media_dir = os.path.join(DATA_DIR, 'media')
```

### 问题 4: Docker 权限问题

**症状**：
- Permission denied 错误
- 无法创建文件

**解决方案**：
```bash
# 设置正确的权限
sudo chown -R 1000:1000 /data/save_restricted_bot
sudo chmod -R 755 /data/save_restricted_bot
```

## 成功标志

当您看到以下所有标志时，说明部署成功：

- ✅ 数据目录结构完整
- ✅ 配置文件在正确位置
- ✅ 监控配置持久化工作正常
- ✅ 搜索 UI 功能正常
- ✅ 媒体文件正常显示
- ✅ 日志无错误
- ✅ Docker 数据持久化正常

## 性能基准

正常情况下，应该观察到：

- Bot 启动时间：< 5 秒
- Web 界面加载时间：< 2 秒
- 搜索响应时间：< 1 秒
- 图片加载时间：< 1 秒

如果性能明显低于这些基准，请检查：
- 磁盘 I/O 性能
- 数据库文件大小
- 网络连接

## 支持

如果验证过程中遇到问题：

1. 查看 [CHANGELOG_v2.3.0.md](CHANGELOG_v2.3.0.md)
2. 查看 [README.md](README.md)
3. 提交 Issue 并附上：
   - 错误日志
   - 验证步骤输出
   - 环境信息（Docker 版本、Python 版本等）

---

**版本**: v2.3.0
**更新日期**: 2024
