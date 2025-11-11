# 多图片支持与数据独立存储

## 概述

此版本为 Save-Restricted-Bot 添加了两个重要功能：

1. **多图片支持** - 网页笔记可以包含多张图片，保留 Telegram 媒体组的完整结构
2. **数据独立存储** - 所有用户数据和配置集中在 `data/` 目录，更新代码时不受影响

## 新功能详情

### 1. 多图片支持

#### 功能说明
- 当用户在 Telegram 中发送多张图片（媒体组）时，记录模式会自动识别并保存所有图片
- 所有图片和文字说明都保存在同一条笔记中
- 网页界面使用优雅的网格布局展示多张图片
- 完全兼容旧版单图片笔记

#### 技术实现
- 新增 `note_media` 数据库表存储多媒体关系
- 使用 `media_group_id` 识别 Telegram 媒体组
- 通过定时器（2秒）收集媒体组中的所有消息
- 保留媒体顺序（`media_order` 字段）

#### 展示效果
- **单张图片**: 全宽显示，最高200px
- **两张图片**: 并排两列，每张150px高
- **三张及以上**: 第一张占两列200px高，其余150px高两列排列

### 2. 数据独立存储

#### 目录结构
```
project/
├── main.py                    # 机器人代码
├── app.py                     # Web应用代码
├── database.py                # 数据库管理
├── data/                      # 📁 用户数据目录（Git忽略）
│   ├── config/               # 配置文件目录
│   │   ├── config.json       # Bot配置（不再在根目录）
│   │   └── watch_config.json # 监控配置
│   ├── notes.db              # SQLite数据库
│   └── media/                # 媒体文件目录
│       ├── xxx.jpg
│       └── yyy.jpg
├── *.session                  # Pyrogram会话文件
└── ...其他代码文件
```

#### 优势
1. **更新安全**: `git pull` 更新代码时，`data/` 目录不受影响
2. **备份简单**: 只需备份 `data/` 目录即可保存所有用户数据
3. **Docker友好**: 通过 volume 挂载 `./data:/app/data` 实现数据持久化
4. **环境变量支持**: 可通过 `DATA_DIR` 环境变量自定义数据目录路径

## 数据库变更

### 新表：note_media
```sql
CREATE TABLE note_media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,              -- 关联的笔记ID
    media_type TEXT NOT NULL,              -- 'photo' 或 'video'
    media_path TEXT NOT NULL,              -- 媒体文件路径
    media_order INTEGER DEFAULT 0,         -- 显示顺序
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
);
```

### 旧表：notes
保持不变，向后兼容：
- `media_type` 和 `media_path` 字段仍然存在
- 新笔记主要使用 `note_media` 表
- 旧笔记仍可正常访问

## 迁移指南

### 自动迁移（推荐）

运行迁移脚本：
```bash
python3 migrate_to_multi_image.py
```

脚本会自动：
1. 创建 `note_media` 表
2. 迁移现有单媒体数据到新表
3. 将配置文件复制到 `data/config/`
4. 验证迁移结果

### 手动迁移

如果需要手动操作：

1. **备份数据**
   ```bash
   cp data/notes.db data/notes.db.backup
   cp config.json config.json.backup
   cp watch_config.json watch_config.json.backup
   ```

2. **创建目录**
   ```bash
   mkdir -p data/config
   ```

3. **移动配置文件**
   ```bash
   cp config.json data/config/
   cp watch_config.json data/config/
   ```

4. **重启机器人**
   - 数据库表会自动创建
   - 配置文件会自动从新位置加载

## Docker 部署

### docker-compose.yml
```yaml
version: '3.8'

services:
  telegram-bot:
    build: .
    container_name: save-restricted-bot
    restart: unless-stopped
    ports:
      - "10000:10000"  # Bot端口
      - "5000:5000"    # Web界面端口
    environment:
      - TOKEN=${TOKEN}
      - ID=${ID}
      - HASH=${HASH}
      - STRING=${STRING}
      - DATA_DIR=/app/data  # 容器内数据目录
    volumes:
      - ./data:/app/data    # 数据持久化
      - ./downloads:/app/downloads
```

### 使用说明

1. **首次部署**
   ```bash
   # 创建配置文件
   mkdir -p data/config
   cp config.json.example data/config/config.json
   # 编辑配置...
   
   # 启动容器
   docker-compose up -d
   ```

2. **数据备份**
   ```bash
   tar -czf backup-$(date +%Y%m%d).tar.gz data/
   ```

3. **更新代码**
   ```bash
   git pull
   docker-compose build
   docker-compose up -d
   # 所有配置和数据自动保留！
   ```

## API 变更

### database.py

#### add_note() 函数新增参数
```python
def add_note(user_id, source_chat_id, source_name, message_text, 
             media_type=None, media_path=None, media_list=None):
    """
    Args:
        media_list: 多媒体列表 [{'type': 'photo', 'path': 'xxx.jpg'}, ...]
    """
```

#### get_notes() 返回值变更
```python
notes = get_notes()
# 每条笔记现在包含 'media_list' 字段
for note in notes:
    print(note['media_list'])  # [{'media_type': 'photo', 'media_path': 'xxx.jpg'}, ...]
```

#### 新增函数
```python
def get_note_media(note_id):
    """获取笔记的所有媒体文件"""
    return [{'id': 1, 'media_type': 'photo', 'media_path': 'xxx.jpg', ...}, ...]
```

### main.py

#### 配置文件路径
```python
# 旧版
with open('config.json', 'r') as f: DATA = json.load(f)

# 新版（自动兼容）
CONFIG_FILE = os.path.join(DATA_DIR, 'config', 'config.json') 
    if os.path.exists(os.path.join(DATA_DIR, 'config', 'config.json')) 
    else 'config.json'
```

#### 媒体组处理
```python
# 新增全局变量
media_groups = {}  # 跟踪正在接收的媒体组

# 在 auto_forward 函数中
if message.media_group_id:
    # 收集媒体组中的所有消息
    # 使用定时器延迟处理，确保收到所有图片
```

## 向后兼容

### 100% 兼容旧版数据
- 旧的单图片笔记正常显示
- 旧的配置文件位置仍可使用（根目录）
- 数据库 schema 保持兼容
- API 签名保持兼容（新增可选参数）

### 优雅降级
- 如果 `media_list` 为空，使用旧的 `media_path`
- Web界面自动检测并适配显示方式
- 迁移脚本可安全重复运行

## 测试方法

### 测试多图片功能

1. **创建记录模式监控任务**
   ```
   /watch -> 添加监控 -> 选择来源 -> 设置record_mode=true
   ```

2. **发送测试媒体组**
   - 在被监控的频道/群组中
   - 选择多张图片（2-10张）
   - 添加文字说明
   - 一起发送

3. **查看Web界面**
   - 访问 http://localhost:5000/notes
   - 查看新笔记是否包含所有图片
   - 检查图片排列是否正确

### 测试数据独立性

1. **修改配置文件**
   ```bash
   echo "test" >> data/config/config.json
   ```

2. **模拟代码更新**
   ```bash
   git stash
   git pull
   git stash pop
   ```

3. **验证数据完整**
   ```bash
   cat data/config/config.json  # 应该还包含 "test"
   ls data/media/               # 媒体文件仍在
   ```

## 常见问题

### Q: 旧笔记会自动转换为多图片格式吗？
A: 迁移脚本会将旧的单图片笔记复制到 `note_media` 表，但不会删除原始数据。两种格式并存，Web界面会优先显示 `media_list`。

### Q: 配置文件必须移动到 data/config/ 吗？
A: 不是必须的。代码会优先查找 `data/config/`，如果不存在则使用根目录的配置文件。但建议迁移以获得更好的数据管理。

### Q: 媒体组最多支持多少张图片？
A: 技术上没有限制，但 Telegram 本身限制媒体组最多10个项目。

### Q: Docker部署时如何处理？
A: 确保 `docker-compose.yml` 包含 `- ./data:/app/data` 卷挂载，然后配置文件放在主机的 `./data/config/` 目录。

### Q: 如何回滚到旧版？
A: 
1. 保留 `data/` 目录不动
2. 切换到旧版代码分支
3. 旧版会忽略 `note_media` 表，继续使用 `notes` 表的 `media_path` 字段

## 性能考虑

### 数据库查询优化
- `note_media` 表添加了 `note_id` 索引
- `get_notes()` 函数会批量加载媒体
- 分页仍然高效（只加载当前页的媒体）

### 媒体存储
- 图片以原始分辨率存储
- 视频只存储缩略图（节省空间）
- 文件名包含消息ID和时间戳，避免冲突

### 媒体组处理
- 使用2秒定时器等待所有消息
- 避免重复处理相同媒体组
- 处理完成后自动清理内存

## 更新日志

### v2.1.0 (2024)
- ✨ 新增多图片支持
- ✨ 数据独立存储到 `data/` 目录
- ✨ 配置文件集中管理
- ✨ Docker volume 支持
- ✨ 迁移脚本
- 🐛 修复媒体组处理bug
- 📝 更新文档

## 贡献

欢迎提交 Issue 和 Pull Request！

- 报告 Bug: [GitHub Issues]
- 功能建议: [GitHub Discussions]
- 代码贡献: Fork -> 修改 -> PR

## 许可证

与主项目相同
