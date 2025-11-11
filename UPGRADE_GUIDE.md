# 升级指南 - 多图片支持与数据独立存储

## 版本信息
- 从版本: v2.0.x (单图片)
- 到版本: v2.1.0 (多图片 + 数据独立)
- 发布日期: 2024

## 升级前准备

### 1. 备份现有数据

**必须备份的文件：**
```bash
# 备份数据库
cp data/notes.db data/notes.db.backup

# 备份配置文件
cp config.json config.json.backup
cp watch_config.json watch_config.json.backup

# 备份媒体文件
tar -czf media-backup-$(date +%Y%m%d).tar.gz data/media/
```

### 2. 检查环境

```bash
# Python版本（需要3.7+）
python3 --version

# 检查磁盘空间
df -h

# 检查进程
ps aux | grep python
```

### 3. 停止现有服务

```bash
# 如果使用systemd
sudo systemctl stop telegram-bot

# 如果使用screen/tmux
# 进入会话并按 Ctrl+C

# 如果使用Docker
docker-compose down
```

## 升级步骤

### 方式一：本地部署（推荐）

#### 步骤1: 更新代码
```bash
cd /path/to/Save-Restricted-Bot
git fetch origin
git checkout feat/data-separation-multi-image-notes-docker-volumes
git pull
```

#### 步骤2: 运行迁移脚本
```bash
python3 migrate_to_multi_image.py
```

**预期输出：**
```
==============================================================
Save-Restricted-Bot 多图片支持迁移工具
==============================================================

此脚本将:
1. 升级数据库以支持多图片功能
2. 迁移现有单媒体数据到新表
3. 将配置文件组织到 data/config/ 目录

是否继续? (y/N): y

==============================================================
开始数据库迁移...
==============================================================
📝 创建 note_media 表...
✅ note_media 表创建成功

📦 迁移现有媒体数据...
✅ 成功迁移 15 条媒体记录到新表

==============================================================
迁移配置文件...
==============================================================
✅ 复制 config.json → data/config/config.json
✅ 复制 watch_config.json → data/config/watch_config.json

==============================================================
验证迁移结果...
==============================================================
✅ 表 notes 存在
✅ 表 note_media 存在
✅ 表 users 存在

📊 数据统计:
   笔记总数: 15
   媒体总数: 15

📁 目录结构:
   ✅ data
   ✅ data/media
   ✅ data/config

==============================================================
✅ 迁移完成!
==============================================================
```

#### 步骤3: 验证配置
```bash
# 检查配置文件是否存在
ls -la data/config/

# 应该看到：
# config.json
# watch_config.json
```

#### 步骤4: 重启服务
```bash
# 使用systemd
sudo systemctl start telegram-bot

# 或直接运行
python3 main.py &
python3 app.py &

# 查看启动日志
tail -f bot.log
```

### 方式二：Docker部署

#### 步骤1: 停止容器
```bash
cd /path/to/Save-Restricted-Bot
docker-compose down
```

#### 步骤2: 更新代码
```bash
git fetch origin
git checkout feat/data-separation-multi-image-notes-docker-volumes
git pull
```

#### 步骤3: 迁移配置文件
```bash
# 创建配置目录
mkdir -p data/config

# 移动配置文件（如果在根目录）
if [ -f config.json ]; then
    cp config.json data/config/
fi

if [ -f watch_config.json ]; then
    cp watch_config.json data/config/
fi
```

#### 步骤4: 更新Docker配置
```bash
# 检查 docker-compose.yml 是否包含新配置
cat docker-compose.yml | grep -A 5 volumes

# 应该包含：
# volumes:
#   - ./data:/app/data
#   - ./downloads:/app/downloads
```

#### 步骤5: 重建并启动
```bash
docker-compose build
docker-compose up -d
```

#### 步骤6: 运行迁移（在容器内）
```bash
docker-compose exec telegram-bot python3 migrate_to_multi_image.py
```

## 升级后验证

### 1. 检查数据库
```bash
sqlite3 data/notes.db
```

```sql
-- 检查表结构
.tables
-- 应该看到: notes  note_media  users

-- 检查 note_media 表
.schema note_media

-- 检查数据
SELECT COUNT(*) FROM notes;
SELECT COUNT(*) FROM note_media;
```

### 2. 测试多图片功能

1. **发送测试媒体组**
   - 在监控的频道/群组中
   - 选择3-5张图片
   - 添加文字说明
   - 一起发送

2. **查看Web界面**
   - 访问 http://localhost:5000/notes
   - 找到刚才的笔记
   - 确认所有图片都显示
   - 检查布局是否正确

3. **检查旧笔记**
   - 找一条旧的单图片笔记
   - 确认仍然可以正常显示
   - 尝试编辑和删除

### 3. 测试数据独立性

```bash
# 修改配置
echo "# test" >> data/config/config.json

# 模拟代码更新
git stash
git pull origin main
git stash pop

# 检查配置
cat data/config/config.json | grep "# test"
# 应该还能看到刚才添加的注释

# 恢复
git checkout data/config/config.json
```

## 回滚方案

如果升级后出现问题，可以回滚到旧版本：

### 方式一：使用备份
```bash
# 1. 停止服务
sudo systemctl stop telegram-bot
# 或 docker-compose down

# 2. 切换到旧版本代码
git checkout main  # 或之前的分支

# 3. 恢复备份
cp config.json.backup config.json
cp watch_config.json.backup watch_config.json
cp data/notes.db.backup data/notes.db

# 4. 重启服务
sudo systemctl start telegram-bot
```

### 方式二：保留新功能，只回滚配置
```bash
# 新版代码会自动兼容旧数据
# 只需确保配置文件在正确位置

# 如果配置文件丢失
cp data/config/config.json ./
cp data/config/watch_config.json ./
```

## 常见问题

### Q1: 迁移脚本报错 "数据库文件不存在"
**A:** 这是正常的，如果是新安装可以忽略。如果是升级，检查 `data/notes.db` 路径是否正确。

### Q2: 配置文件在根目录还是 data/config/?
**A:** 两个位置都可以工作。代码会优先使用 `data/config/`，如果不存在则使用根目录。建议迁移到 `data/config/` 以便统一管理。

### Q3: 旧笔记的图片不显示了
**A:** 检查：
1. `data/media/` 目录是否存在
2. 媒体文件是否还在
3. 数据库中的 `media_path` 字段是否正确
4. 迁移脚本是否成功运行

### Q4: 新笔记只显示一张图片
**A:** 检查：
1. 是否是真的媒体组（多张一起发送）
2. 数据库中是否有 `note_media` 记录
3. Web界面的 JavaScript 是否正常加载

### Q5: Docker容器启动失败
**A:** 检查：
1. `docker-compose.yml` 是否更新
2. `data/` 目录权限是否正确
3. 环境变量是否完整
4. 使用 `docker-compose logs` 查看详细错误

### Q6: 迁移后Web界面报500错误
**A:** 检查：
1. 数据库是否迁移成功
2. `database.py` 是否为最新版本
3. Python依赖是否安装完整
4. 查看 Flask 日志获取详细错误

## 性能优化建议

### 1. 数据库优化
```sql
-- 在 SQLite 中执行
VACUUM;
ANALYZE;
```

### 2. 媒体文件清理
```bash
# 找出没有被引用的媒体文件
python3 << 'EOF'
import sqlite3
import os

conn = sqlite3.connect('data/notes.db')
cursor = conn.cursor()

# 获取所有引用的媒体文件
cursor.execute('SELECT media_path FROM notes WHERE media_path IS NOT NULL')
old_media = {row[0] for row in cursor.fetchall()}

cursor.execute('SELECT media_path FROM note_media')
new_media = {row[0] for row in cursor.fetchall()}

all_referenced = old_media | new_media

# 获取实际存在的文件
media_dir = 'data/media'
actual_files = set(os.listdir(media_dir))

# 找出孤立文件
orphaned = actual_files - all_referenced
print(f"孤立文件数量: {len(orphaned)}")
for f in orphaned:
    print(f"  {f}")

conn.close()
EOF
```

### 3. 监控性能
```bash
# 数据库大小
du -h data/notes.db

# 媒体文件大小
du -sh data/media/

# 笔记统计
sqlite3 data/notes.db "SELECT COUNT(*) FROM notes;"
sqlite3 data/notes.db "SELECT COUNT(*) FROM note_media;"
```

## 技术支持

如果遇到问题：

1. **查看文档**
   - README.md
   - MULTI_IMAGE_SUPPORT.md
   - 本升级指南

2. **检查日志**
   ```bash
   # Bot日志
   tail -f bot.log
   
   # Web日志
   tail -f web.log
   
   # Docker日志
   docker-compose logs -f
   ```

3. **获取帮助**
   - GitHub Issues
   - GitHub Discussions
   - 社区论坛

## 下一步

升级完成后，您可以：

1. **配置新监控任务**
   - 测试多图片转发
   - 测试记录模式

2. **优化现有配置**
   - 整理 `data/config/` 目录
   - 清理不需要的旧文件

3. **设置定期备份**
   ```bash
   # 添加到 crontab
   0 2 * * * tar -czf ~/backups/bot-data-$(date +\%Y\%m\%d).tar.gz /path/to/data/
   ```

4. **探索新功能**
   - 多图片展示
   - 数据独立管理
   - Docker部署便利性

---

**祝升级顺利！** 🎉
