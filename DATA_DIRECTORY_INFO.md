# 数据目录说明

## 📂 数据目录位置

Save-Restricted-Bot 使用系统级独立数据目录存储所有用户数据：

```
/data/save_restricted_bot/
```

## 🎯 为什么使用绝对路径？

1. **避免冲突**：系统级路径避免与其他程序数据混合
2. **独立性强**：与项目代码完全分离
3. **便于备份**：一个目录包含所有数据
4. **Docker 友好**：容器重建不丢失数据
5. **权限清晰**：统一管理访问权限

## 📁 目录结构

```
/data/save_restricted_bot/
│
├── config/                          # 配置文件目录
│   ├── config.json                  # Bot 凭证配置
│   │   ├── TOKEN                    # Bot Token
│   │   ├── ID                       # API ID
│   │   ├── HASH                     # API Hash
│   │   └── STRING                   # Session String
│   │
│   └── watch_config.json            # 监控任务配置
│       └── {user_id: {tasks...}}    # 用户监控任务
│
├── media/                           # 媒体文件存储
│   ├── *.jpg                        # 图片文件
│   └── *_thumb.jpg                  # 视频缩略图
│
├── logs/                            # 日志文件（预留）
│   └── *.log                        # 应用日志
│
└── notes.db                         # SQLite 数据库
    ├── notes                        # 笔记主表
    ├── note_media                   # 笔记媒体表（多图支持）
    └── users                        # 用户认证表
```

## 🔑 文件权限

### 推荐权限设置

```bash
# 设置目录所有者（替换 your_user 为实际用户名）
sudo chown -R your_user:your_user /data/save_restricted_bot/

# 设置合理权限
chmod 700 /data/save_restricted_bot/
chmod 700 /data/save_restricted_bot/config/
chmod 600 /data/save_restricted_bot/config/*.json
chmod 755 /data/save_restricted_bot/media/
chmod 644 /data/save_restricted_bot/media/*
chmod 600 /data/save_restricted_bot/notes.db
```

### 权限说明

- **700**: 只有所有者可以读写执行（目录）
- **600**: 只有所有者可以读写（配置文件、数据库）
- **755**: 所有者可读写执行，其他人可读执行（媒体目录）
- **644**: 所有者可读写，其他人只读（媒体文件）

## 🌍 环境变量

### 自定义数据目录

如果需要使用其他位置，可以通过环境变量指定：

```bash
# 方式 1: 导出环境变量
export DATA_DIR=/your/custom/path

# 方式 2: 在 .env 文件中设置
echo "DATA_DIR=/your/custom/path" >> .env

# 方式 3: Docker Compose 中设置
# docker-compose.yml:
environment:
  - DATA_DIR=/your/custom/path
```

### 默认值

如果未设置 `DATA_DIR` 环境变量，默认使用：
```
/data/save_restricted_bot
```

## 🚀 首次启动

### 自动初始化

程序首次启动时会自动：

1. ✅ 创建数据目录结构
2. ✅ 创建默认配置文件
3. ✅ 初始化数据库
4. ✅ 创建默认管理员账户

**无需手动创建任何文件！**

### 启动流程

```bash
# 1. 克隆仓库
git clone https://github.com/your-repo/save-restricted-bot.git
cd save-restricted-bot

# 2. 安装依赖
pip install -r requirements.txt

# 3. 直接启动（会自动初始化）
python3 main.py

# 4. 首次启动后，编辑配置文件
sudo nano /data/save_restricted_bot/config/config.json
```

## 🐳 Docker 部署

### Docker Compose 配置

```yaml
version: '3.8'

services:
  telegram-bot:
    build: .
    container_name: save-restricted-bot
    restart: unless-stopped
    ports:
      - "10000:10000"
      - "5000:5000"
    environment:
      - DATA_DIR=/data/save_restricted_bot
    volumes:
      - /data/save_restricted_bot:/data/save_restricted_bot
      - ./downloads:/app/downloads
```

### Docker 启动步骤

```bash
# 1. 创建宿主机数据目录
sudo mkdir -p /data/save_restricted_bot

# 2. 设置权限
sudo chown -R $(whoami):$(whoami) /data/save_restricted_bot/

# 3. 启动容器
docker-compose up -d --build

# 4. 首次启动后，编辑配置
docker exec -it save-restricted-bot nano /data/save_restricted_bot/config/config.json

# 5. 重启容器使配置生效
docker-compose restart
```

## 💾 数据备份

### 完整备份

```bash
# 备份整个数据目录
sudo tar -czf save_restricted_bot_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
     /data/save_restricted_bot/

# 验证备份
tar -tzf save_restricted_bot_backup_*.tar.gz
```

### 仅备份配置和数据库

```bash
# 备份配置和数据库（不包括媒体文件）
sudo tar -czf config_backup_$(date +%Y%m%d).tar.gz \
     /data/save_restricted_bot/config/ \
     /data/save_restricted_bot/notes.db
```

### 定期备份（Cron）

```bash
# 编辑 crontab
crontab -e

# 添加每日备份任务（每天凌晨 3 点）
0 3 * * * tar -czf /backup/save_restricted_bot_$(date +\%Y\%m\%d).tar.gz /data/save_restricted_bot/ && find /backup -name "save_restricted_bot_*.tar.gz" -mtime +7 -delete
```

## 🔄 数据恢复

### 从备份恢复

```bash
# 1. 停止服务
systemctl stop your-bot-service
# 或 Docker:
docker-compose down

# 2. 恢复数据
sudo tar -xzf save_restricted_bot_backup_YYYYMMDD_HHMMSS.tar.gz -C /

# 3. 检查权限
sudo chown -R your_user:your_user /data/save_restricted_bot/

# 4. 重启服务
systemctl start your-bot-service
# 或 Docker:
docker-compose up -d
```

## 🔍 故障排查

### 问题 1: 权限被拒绝

```bash
# 错误信息: PermissionError: [Errno 13] Permission denied
# 解决方案:
sudo chown -R $(whoami):$(whoami) /data/save_restricted_bot/
chmod -R u+rwX /data/save_restricted_bot/
```

### 问题 2: 目录不存在

```bash
# 错误信息: FileNotFoundError: No such file or directory
# 解决方案:
sudo mkdir -p /data/save_restricted_bot/{config,media,logs}
```

### 问题 3: 磁盘空间不足

```bash
# 检查磁盘使用情况
df -h /data

# 清理旧媒体文件（谨慎操作）
# 删除 30 天前的媒体文件
find /data/save_restricted_bot/media/ -type f -mtime +30 -delete
```

### 问题 4: Docker 容器访问被拒

```bash
# 确保容器内用户有权限访问挂载目录
# 方式 1: 修改目录权限
sudo chmod -R 777 /data/save_restricted_bot/

# 方式 2: 修改 Dockerfile 用户ID匹配
# 在 Dockerfile 中添加:
# USER 1000:1000
```

## 📊 磁盘使用监控

### 查看目录大小

```bash
# 查看总大小
du -sh /data/save_restricted_bot/

# 查看各子目录大小
du -sh /data/save_restricted_bot/*/

# 查看媒体文件数量
find /data/save_restricted_bot/media/ -type f | wc -l
```

### 监控脚本示例

```bash
#!/bin/bash
# disk_monitor.sh

DATA_DIR="/data/save_restricted_bot"
THRESHOLD=80  # 磁盘使用率阈值

usage=$(df -h "$DATA_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')

if [ "$usage" -gt "$THRESHOLD" ]; then
    echo "警告: 数据目录磁盘使用率 ${usage}%"
    # 发送通知或清理旧文件
fi
```

## 🔐 安全建议

1. **限制访问权限**：只有必要的用户可以访问数据目录
2. **定期备份**：至少每天备份一次配置和数据库
3. **加密敏感数据**：考虑对配置文件加密
4. **监控访问日志**：定期检查异常访问
5. **网络隔离**：生产环境限制网页端口访问

## 📚 相关文档

- [升级指南](DATA_DIR_UPGRADE_GUIDE.md) - 从旧版本迁移数据
- [数据保护指南](DATA_PROTECTION.md) - 数据安全最佳实践
- [Docker 部署指南](DOCKER_SETUP.md) - Docker 环境部署
- [更新日志 v2.2](CHANGELOG_v2.2.md) - 版本更新详情

---

**最后更新**: 2024  
**版本**: v2.2.0
