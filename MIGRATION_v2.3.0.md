# 迁移到 v2.3.0 指南

本文档指导您如何从旧版本迁移到 v2.3.0。

## 🎯 迁移目标

将配置文件从旧位置迁移到新的 DATA_DIR 结构：

**旧结构**：
```
/app/                          # 或项目根目录
├── config.json               # ❌ 旧位置
├── watch_config.json         # ❌ 旧位置
└── data/                     # ❌ 相对路径
    ├── notes.db
    └── media/
```

**新结构**：
```
/data/save_restricted_bot/     # ✅ 绝对路径
├── config/                    # ✅ 新配置目录
│   ├── config.json
│   └── watch_config.json
├── media/
├── logs/
└── notes.db
```

## 🚀 自动迁移（推荐）

### Docker 用户

v2.3.0 会自动处理大部分迁移：

1. **更新代码**：
   ```bash
   cd /path/to/save-restricted-bot
   git pull
   ```

2. **备份旧配置**（可选但推荐）：
   ```bash
   cp config.json config.json.backup
   cp watch_config.json watch_config.json.backup
   ```

3. **设置环境变量**：
   编辑 `docker-compose.yml` 或 `.env` 文件，确保包含：
   ```yaml
   environment:
     - TOKEN=${TOKEN}
     - ID=${ID}
     - HASH=${HASH}
     - STRING=${STRING}
     - DATA_DIR=/data/save_restricted_bot
   ```

4. **重启容器**：
   ```bash
   docker-compose down
   docker-compose up -d
   ```

5. **验证**：
   ```bash
   # 检查新配置文件
   docker exec save-restricted-bot ls -la /data/save_restricted_bot/config/
   
   # 应该看到 config.json 和 watch_config.json
   ```

6. **清理旧文件**（验证成功后）：
   ```bash
   # 进入容器
   docker exec -it save-restricted-bot bash
   
   # 删除旧配置文件（如果还在项目根目录）
   rm -f config.json watch_config.json
   
   # 退出
   exit
   ```

### 本地部署用户

1. **更新代码**：
   ```bash
   cd /path/to/save-restricted-bot
   git pull
   ```

2. **备份旧配置**：
   ```bash
   cp config.json config.json.backup
   cp watch_config.json watch_config.json.backup
   ```

3. **设置环境变量**（可选）：
   ```bash
   export DATA_DIR=/data/save_restricted_bot
   export TOKEN=your_token
   export ID=your_id
   export HASH=your_hash
   export STRING=your_string
   ```

4. **创建数据目录**：
   ```bash
   sudo mkdir -p /data/save_restricted_bot/config
   sudo chown -R $USER:$USER /data/save_restricted_bot
   ```

5. **移动配置文件**：
   ```bash
   mv config.json /data/save_restricted_bot/config/
   mv watch_config.json /data/save_restricted_bot/config/
   ```

6. **移动数据库和媒体**（如果在旧位置）：
   ```bash
   # 如果数据在 ./data/ 目录
   mv data/notes.db /data/save_restricted_bot/
   mv data/media/* /data/save_restricted_bot/media/
   ```

7. **重启服务**：
   ```bash
   # 停止旧进程
   pkill -f "python.*main.py"
   pkill -f "python.*app.py"
   
   # 启动新进程
   python main.py &
   python app.py &
   ```

8. **验证**：
   ```bash
   ls -la /data/save_restricted_bot/config/
   ```

## 🔍 手动迁移步骤

如果自动迁移不工作，按以下步骤手动迁移：

### 步骤 1: 停止服务
```bash
# Docker
docker-compose down

# 本地
pkill -f "python.*main.py"
pkill -f "python.*app.py"
```

### 步骤 2: 创建新目录结构
```bash
sudo mkdir -p /data/save_restricted_bot/config
sudo mkdir -p /data/save_restricted_bot/media
sudo mkdir -p /data/save_restricted_bot/logs
```

### 步骤 3: 复制配置文件
```bash
# 找到旧配置文件
find . -name "config.json" -o -name "watch_config.json"

# 复制到新位置
cp config.json /data/save_restricted_bot/config/
cp watch_config.json /data/save_restricted_bot/config/
```

### 步骤 4: 复制数据文件
```bash
# 数据库
cp data/notes.db /data/save_restricted_bot/ 2>/dev/null || echo "数据库不存在，将自动创建"

# 媒体文件
cp -r data/media/* /data/save_restricted_bot/media/ 2>/dev/null || echo "媒体文件不存在"
```

### 步骤 5: 设置权限
```bash
# Docker 用户（使用容器内的 UID）
sudo chown -R 1000:1000 /data/save_restricted_bot

# 本地用户
sudo chown -R $USER:$USER /data/save_restricted_bot
```

### 步骤 6: 更新配置
```bash
# Docker: 编辑 docker-compose.yml
nano docker-compose.yml

# 确保包含 DATA_DIR 环境变量：
# environment:
#   - DATA_DIR=/data/save_restricted_bot
```

### 步骤 7: 重启服务
```bash
# Docker
docker-compose up -d

# 本地
export DATA_DIR=/data/save_restricted_bot
python main.py &
python app.py &
```

## ✅ 验证迁移成功

运行以下检查：

### 1. 检查文件结构
```bash
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

### 2. 检查配置内容
```bash
cat /data/save_restricted_bot/config/config.json
cat /data/save_restricted_bot/config/watch_config.json
```

应该看到您的 TOKEN、ID、HASH、STRING 和监控配置。

### 3. 测试监控功能
1. 启动 Bot
2. 发送 `/watch` 命令
3. 创建一个测试监控
4. 检查配置文件是否更新：
   ```bash
   cat /data/save_restricted_bot/config/watch_config.json
   ```

### 4. 测试 Web 界面
1. 访问 http://localhost:5000
2. 登录
3. 点击搜索图标（🔍）
4. 验证搜索面板正常弹出

### 5. 测试数据持久化（Docker）
```bash
# 重启容器
docker-compose restart

# 检查数据是否保留
docker exec save-restricted-bot cat /data/save_restricted_bot/config/watch_config.json
```

## 🐛 常见问题

### 问题 1: 配置文件找不到

**错误**：`FileNotFoundError: [Errno 2] No such file or directory: '/data/save_restricted_bot/config/config.json'`

**解决**：
```bash
# 确保目录存在
sudo mkdir -p /data/save_restricted_bot/config

# 从环境变量初始化（Docker）
docker-compose down
docker-compose up -d

# 或手动创建（本地）
cat > /data/save_restricted_bot/config/config.json << EOF
{
    "TOKEN": "your_token",
    "ID": "your_id",
    "HASH": "your_hash",
    "STRING": "your_string"
}
EOF
```

### 问题 2: 权限被拒绝

**错误**：`PermissionError: [Errno 13] Permission denied: '/data/save_restricted_bot/config'`

**解决**：
```bash
# Docker
sudo chown -R 1000:1000 /data/save_restricted_bot
sudo chmod -R 755 /data/save_restricted_bot

# 本地
sudo chown -R $USER:$USER /data/save_restricted_bot
sudo chmod -R 755 /data/save_restricted_bot
```

### 问题 3: 旧数据丢失

**解决**：
```bash
# 检查旧数据位置
find . -name "notes.db"
find . -name "watch_config.json"

# 复制到新位置
cp <old_path>/notes.db /data/save_restricted_bot/
cp <old_path>/watch_config.json /data/save_restricted_bot/config/
```

### 问题 4: Docker 卷挂载问题

**错误**：容器内看不到文件

**解决**：
```bash
# 检查 docker-compose.yml 的 volumes 配置
cat docker-compose.yml | grep volumes -A 5

# 应该包含：
# volumes:
#   - /data/save_restricted_bot:/data/save_restricted_bot

# 重新创建容器
docker-compose down
docker-compose up -d
```

## 📊 迁移检查清单

完成以下检查项后，迁移即为成功：

- [ ] 配置文件在 `/data/save_restricted_bot/config/`
- [ ] 数据库文件在 `/data/save_restricted_bot/notes.db`
- [ ] 媒体文件在 `/data/save_restricted_bot/media/`
- [ ] Bot 正常启动，无错误
- [ ] Web 界面可以访问
- [ ] 搜索功能正常
- [ ] 监控任务保留
- [ ] 笔记数据保留
- [ ] 创建新监控时配置立即保存
- [ ] 容器重启后数据不丢失（Docker）

## 🔄 回滚到旧版本

如果迁移出现问题，可以回滚：

```bash
# 1. 停止新版本
docker-compose down  # 或 pkill -f python

# 2. 恢复旧配置
cp config.json.backup config.json
cp watch_config.json.backup watch_config.json

# 3. 切换到旧版本
git checkout <old_version_tag>

# 4. 重启服务
docker-compose up -d  # 或 python main.py & python app.py &
```

## 📞 获取帮助

如果遇到问题：

1. 查看日志：
   ```bash
   # Docker
   docker logs save-restricted-bot
   
   # 本地
   tail -f /data/save_restricted_bot/logs/*.log
   ```

2. 运行验证脚本：
   ```bash
   python3 test_data_dir.py
   ```

3. 查看详细文档：
   - [CHANGELOG_v2.3.0.md](CHANGELOG_v2.3.0.md)
   - [DEPLOYMENT_VERIFICATION.md](DEPLOYMENT_VERIFICATION.md)
   - [README.md](README.md)

4. 提交 Issue，包含：
   - 错误日志
   - 环境信息
   - 迁移步骤

---

**版本**: v2.3.0
**更新日期**: 2024
