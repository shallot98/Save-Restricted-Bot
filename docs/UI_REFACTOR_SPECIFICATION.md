# Save-Restricted-Bot 网页UI完整重构方案

> **版本**: 1.0.0  
> **创建日期**: 2024-12-06  
> **适用范围**: Save-Restricted-Bot Web UI 完整现代化重构

---

## 📋 目录

- [第一部分：现状分析](#第一部分现状分析)
- [第二部分：超详细重构方案](#第二部分超详细重构方案)
- [第三部分：技术实施方案](#第三部分技术实施方案)
- [第四部分：CSS设计系统](#第四部分css设计系统)
- [第五部分：功能优先级和实施路线](#第五部分功能优先级和实施路线)
- [第六部分：性能优化方案](#第六部分性能优化方案)
- [第七部分：安全考虑](#第七部分安全考虑)
- [第八部分：部署和测试](#第八部分部署和测试)
- [第九部分：迁移计划](#第九部分迁移计划)

---

## 第一部分：现状分析

### 1.1 项目结构分析

#### 当前代码架构评估

```
Save-Restricted-Bot/
├── app.py                 # Flask 应用主文件 (717行)
├── database.py           # SQLite 数据库操作 (971行)
├── config.py             # 配置管理
├── main.py               # Telegram Bot 主入口
├── constants.py          # 常量定义
├── templates/            # Jinja2 模板
│   ├── notes.html       # 笔记列表页面 (1497行 - 内嵌CSS/JS)
│   ├── login.html       # 登录页面
│   ├── admin.html       # 管理页面
│   └── edit_note.html   # 编辑页面
└── bot/                 # Telegram Bot 逻辑
    ├── handlers/        # 消息处理器
    ├── filters/         # 过滤器
    ├── workers/         # 后台任务
    └── utils/          # 工具函数
```

**架构问题：**
- ❌ 前后端未分离，耦合度高
- ❌ 所有CSS/JS内嵌在HTML中（notes.html 1497行）
- ❌ 无模块化前端架构
- ❌ 服务器端渲染导致交互受限
- ❌ 无构建工具，无代码优化
- ❌ 无前端路由系统

### 1.2 数据库表结构分析

#### 当前Schema

```sql
-- notes 表（核心笔记数据）
CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    source_chat_id TEXT NOT NULL,
    source_name TEXT,
    message_text TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    media_type TEXT,                    -- 媒体类型
    media_path TEXT,                    -- 主媒体路径
    media_paths TEXT,                   -- JSON数组：多媒体路径
    media_group_id TEXT,                -- 媒体组ID
    magnet_link TEXT,                   -- 磁力链接
    filename TEXT,                      -- 校准后文件名
    is_favorite INTEGER DEFAULT 0       -- 收藏标记
);

-- users 表（用户认证）
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

-- calibration_tasks 表（校准任务）
CREATE TABLE calibration_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    magnet_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    last_attempt DATETIME,
    next_attempt DATETIME NOT NULL,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
);

-- auto_calibration_config 表（校准配置）
CREATE TABLE auto_calibration_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    enabled BOOLEAN DEFAULT 0,
    filter_mode TEXT DEFAULT 'empty_only',
    -- ... 其他配置字段
);
```

**存在问题：**
- ❌ 缺少标签系统（tags表）
- ❌ 缺少笔记-标签关联表
- ❌ 缺少分类/文件夹系统
- ❌ 无用户偏好设置表
- ❌ 无搜索历史表
- ❌ 无笔记版本控制
- ❌ media_paths 使用JSON存储，查询效率低
- ❌ 缺少全文索引

### 1.3 Flask应用层分析

#### 当前路由

```python
# 认证相关
GET  /login          # 登录页面
POST /login          # 登录提交
GET  /logout         # 登出

# 笔记管理
GET  /               # 重定向到 /notes
GET  /notes          # 笔记列表（带分页/搜索）
GET  /edit_note/<id> # 编辑笔记
POST /edit_note/<id> # 更新笔记
POST /delete_note/<id>      # 删除笔记（AJAX）
POST /toggle_favorite/<id>  # 收藏切换（AJAX）

# 管理页面
GET  /admin          # 密码修改
POST /admin          # 密码提交
GET  /admin/webdav   # WebDAV配置
POST /admin/webdav   # WebDAV保存
GET  /admin/viewer   # 观看网站配置
POST /admin/viewer   # 观看网站保存
GET  /admin/calibration     # 校准配置
POST /admin/calibration     # 校准保存

# 媒体文件
GET /media/<path>    # 媒体文件访问
```

**问题：**
- ❌ 无RESTful API设计
- ❌ 混合HTML渲染和JSON响应
- ❌ 无统一的API版本控制
- ❌ 无数据分页策略（仅简单LIMIT/OFFSET）
- ❌ 无错误处理中间件
- ❌ 无请求验证
- ❌ 缺少批量操作接口

### 1.4 前端架构分析

#### 当前实现

```html
<!-- notes.html 结构 -->
<div class="container">
    <div class="header">...</div>
    <div class="search-panel">...</div>
    <div class="stats">...</div>
    <div class="notes-grid">
        {% for note in notes %}
        <div class="note-card">...</div>
        {% endfor %}
    </div>
    <div class="pagination">...</div>
</div>

<style>
    /* 1200+ 行内嵌CSS */
</style>

<script>
    /* 200+ 行内嵌JavaScript */
</script>
```

**问题清单：**
- ❌ 无组件化设计
- ❌ 样式与结构耦合
- ❌ JavaScript逻辑混乱，无模块化
- ❌ 全局变量污染
- ❌ 无状态管理
- ❌ 无虚拟DOM，性能差（大列表）
- ❌ 无代码复用机制
- ❌ 无TypeScript类型安全
- ❌ 响应式布局不完善

### 1.5 存在的问题和瓶颈列表

#### 功能层面

| 问题分类 | 具体问题 | 严重程度 | 影响范围 |
|---------|---------|---------|---------|
| 搜索功能 | 仅支持简单文本搜索，无全文索引 | 🔴 高 | 用户体验 |
| 标签系统 | 无标签功能，无法分类管理 | 🔴 高 | 信息组织 |
| 编辑器 | 纯文本编辑，无富文本支持 | 🟡 中 | 内容创作 |
| 批量操作 | 无批量编辑/删除/导出 | 🟡 中 | 操作效率 |
| 视图模式 | 仅网格视图，无列表/时间线视图 | 🟢 低 | 浏览体验 |
| 数据洞察 | 无统计图表和数据分析 | 🟢 低 | 数据价值 |

#### 技术层面

| 问题分类 | 具体问题 | 技术债务 | 重构成本 |
|---------|---------|---------|---------|
| 前端架构 | 无现代框架，维护困难 | 🔴 严重 | 高 |
| 性能 | 大列表渲染卡顿 | 🔴 严重 | 中 |
| 代码质量 | 1497行HTML，可读性差 | 🟡 中等 | 高 |
| 测试 | 无前端测试 | 🟡 中等 | 中 |
| 移动端 | 响应式不完善 | 🟢 轻微 | 低 |

### 1.6 用户行为和痛点分析

#### 典型用户场景

**场景1：快速检索笔记**
- 用户需求：从数千条笔记中快速找到目标内容
- 现有问题：
  - 搜索仅支持简单文本匹配
  - 无搜索建议
  - 无历史搜索
  - 无高级筛选（标签、日期范围、来源组合）
- 期望改进：
  - 全文搜索 + 搜索建议
  - 多维度筛选
  - 保存搜索条件
  - 搜索结果高亮

**场景2：整理和分类**
- 用户需求：按主题组织大量笔记
- 现有问题：
  - 无标签系统
  - 无文件夹/分类
  - 仅依赖收藏功能
- 期望改进：
  - 多标签支持
  - 标签云可视化
  - 智能标签推荐
  - 分类树结构

**场景3：批量管理**
- 用户需求：一次性操作多条笔记
- 现有问题：
  - 只能单条编辑/删除
  - 无批量导出
  - 操作繁琐
- 期望改进：
  - 多选机制
  - 批量打标签
  - 批量移动/删除
  - 批量导出（Markdown/JSON）

**场景4：移动端访问**
- 用户需求：手机上查看笔记
- 现有问题：
  - 布局不适配
  - 搜索面板占用空间大
  - 触摸交互不友好
- 期望改进：
  - 完全响应式设计
  - 移动端专用布局
  - 手势操作支持

**场景5：内容编辑**
- 用户需求：编辑笔记，添加格式
- 现有问题：
  - 纯文本编辑器
  - 无Markdown支持
  - 无格式化工具栏
- 期望改进：
  - 富文本编辑器
  - Markdown支持
  - 插入图片/链接
  - 实时预览

---

## 第二部分：超详细重构方案

### 2.1 数据库设计方案

#### 2.1.1 完整Schema设计

```sql
-- =====================================================
-- 核心笔记表（重构）
-- =====================================================
CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    source_chat_id TEXT NOT NULL,
    source_name TEXT,
    
    -- 内容字段
    title TEXT,                         -- 新增：笔记标题
    message_text TEXT,                   -- 原始文本内容
    content_html TEXT,                   -- 新增：富文本HTML
    content_markdown TEXT,               -- 新增：Markdown格式
    
    -- 媒体字段
    media_type TEXT,
    media_path TEXT,
    media_group_id TEXT,
    
    -- 链接字段
    magnet_link TEXT,
    filename TEXT,
    
    -- 元数据
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 新增：更新时间
    is_favorite INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0,                  -- 新增：归档标记
    view_count INTEGER DEFAULT 0,                   -- 新增：查看次数
    
    -- 索引字段
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 全文搜索索引
CREATE VIRTUAL TABLE notes_fts USING fts5(
    title, 
    message_text, 
    content_markdown,
    content=notes,
    content_rowid=id
);

-- 触发器：自动更新FTS索引
CREATE TRIGGER notes_fts_insert AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, message_text, content_markdown)
    VALUES (new.id, new.title, new.message_text, new.content_markdown);
END;

CREATE TRIGGER notes_fts_update AFTER UPDATE ON notes BEGIN
    UPDATE notes_fts SET 
        title = new.title,
        message_text = new.message_text,
        content_markdown = new.content_markdown
    WHERE rowid = new.id;
END;

CREATE TRIGGER notes_fts_delete AFTER DELETE ON notes BEGIN
    DELETE FROM notes_fts WHERE rowid = old.id;
END;

-- =====================================================
-- 媒体文件表（新增）
-- =====================================================
CREATE TABLE media_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,            -- 文件路径
    file_type TEXT NOT NULL,            -- photo, video, animation, document
    file_size INTEGER,                  -- 文件大小（字节）
    thumbnail_path TEXT,                -- 缩略图路径
    width INTEGER,                      -- 图片/视频宽度
    height INTEGER,                     -- 图片/视频高度
    duration INTEGER,                   -- 视频时长（秒）
    mime_type TEXT,                     -- MIME类型
    display_order INTEGER DEFAULT 0,    -- 显示顺序
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
);

CREATE INDEX idx_media_note ON media_files(note_id);

-- =====================================================
-- 标签系统
-- =====================================================
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,          -- 标签名称
    color TEXT DEFAULT '#667eea',        -- 标签颜色
    icon TEXT,                          -- 标签图标（emoji）
    description TEXT,                   -- 标签描述
    parent_id INTEGER,                  -- 父标签ID（支持层级）
    use_count INTEGER DEFAULT 0,        -- 使用次数
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES tags(id) ON DELETE SET NULL
);

CREATE INDEX idx_tags_name ON tags(name);
CREATE INDEX idx_tags_parent ON tags(parent_id);

-- 笔记-标签关联表
CREATE TABLE note_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
    UNIQUE(note_id, tag_id)
);

CREATE INDEX idx_note_tags_note ON note_tags(note_id);
CREATE INDEX idx_note_tags_tag ON note_tags(tag_id);

-- =====================================================
-- 分类/文件夹系统
-- =====================================================
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER,                  -- 支持嵌套分类
    icon TEXT,
    color TEXT DEFAULT '#667eea',
    description TEXT,
    display_order INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE CASCADE
);

CREATE INDEX idx_categories_parent ON categories(parent_id);

-- 笔记-分类关联
CREATE TABLE note_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    UNIQUE(note_id, category_id)
);

-- =====================================================
-- 用户系统（增强）
-- =====================================================
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT,
    display_name TEXT,
    avatar_url TEXT,
    role TEXT DEFAULT 'user',           -- admin, user
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login_at DATETIME
);

-- 用户偏好设置
CREATE TABLE user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    theme TEXT DEFAULT 'light',         -- light, dark, auto
    view_mode TEXT DEFAULT 'grid',      -- grid, list, timeline
    notes_per_page INTEGER DEFAULT 50,
    default_sort TEXT DEFAULT 'newest', -- newest, oldest, title, updated
    sidebar_collapsed INTEGER DEFAULT 0,
    language TEXT DEFAULT 'zh-CN',
    preferences_json TEXT,              -- JSON存储其他偏好
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =====================================================
-- 搜索历史
-- =====================================================
CREATE TABLE search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    filters_json TEXT,                  -- JSON存储筛选条件
    result_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_search_user ON search_history(user_id, created_at DESC);

-- 保存的搜索
CREATE TABLE saved_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    query TEXT,
    filters_json TEXT,
    is_pinned INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =====================================================
-- 笔记版本历史（可选）
-- =====================================================
CREATE TABLE note_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    title TEXT,
    content_markdown TEXT,
    content_html TEXT,
    version_number INTEGER NOT NULL,
    created_by INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    change_description TEXT,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE INDEX idx_versions_note ON note_versions(note_id, version_number DESC);

-- =====================================================
-- 统计数据表
-- =====================================================
CREATE TABLE statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    stat_date DATE NOT NULL,
    notes_created INTEGER DEFAULT 0,
    notes_updated INTEGER DEFAULT 0,
    notes_deleted INTEGER DEFAULT 0,
    searches_count INTEGER DEFAULT 0,
    unique_sources_count INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, stat_date)
);

CREATE INDEX idx_stats_user_date ON statistics(user_id, stat_date DESC);

-- =====================================================
-- 索引优化
-- =====================================================
CREATE INDEX idx_notes_user_time ON notes(user_id, timestamp DESC);
CREATE INDEX idx_notes_source ON notes(source_chat_id);
CREATE INDEX idx_notes_favorite ON notes(user_id, is_favorite, timestamp DESC);
CREATE INDEX idx_notes_updated ON notes(updated_at DESC);
CREATE INDEX idx_notes_archived ON notes(is_archived);
```

#### 2.1.2 设计关键点对比表

| 方面 | 旧设计 | 新设计 | 改进点 |
|-----|-------|-------|--------|
| 媒体存储 | media_paths JSON字段 | 独立media_files表 | ✅ 支持单独查询、排序、管理 |
| 搜索 | LIKE查询 | FTS5全文索引 | ✅ 性能提升10-100倍 |
| 标签 | 无 | tags表 + note_tags关联 | ✅ 支持多标签、层级标签 |
| 分类 | 无 | categories表 | ✅ 支持文件夹式组织 |
| 用户偏好 | 无 | user_preferences表 | ✅ 个性化设置持久化 |
| 搜索历史 | 无 | search_history表 | ✅ 快速重复搜索 |
| 版本控制 | 无 | note_versions表 | ✅ 内容历史追溯 |
| 统计 | 实时计算 | statistics表 | ✅ 减少查询负担 |

#### 2.1.3 数据库迁移步骤

**步骤1：备份现有数据**
```bash
#!/bin/bash
# backup_database.sh
DATE=$(date +%Y%m%d_%H%M%S)
cp data/notes.db data/notes_backup_${DATE}.db
echo "✅ 备份完成: notes_backup_${DATE}.db"
```

**步骤2：创建迁移脚本**
```python
# migrate_database.py
import sqlite3
import json
from datetime import datetime

def migrate_v1_to_v2(db_path):
    """从v1迁移到v2数据库结构"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔄 开始数据库迁移...")
    
    # 1. 添加新列到notes表
    try:
        cursor.execute("ALTER TABLE notes ADD COLUMN title TEXT")
        cursor.execute("ALTER TABLE notes ADD COLUMN content_html TEXT")
        cursor.execute("ALTER TABLE notes ADD COLUMN content_markdown TEXT")
        cursor.execute("ALTER TABLE notes ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        cursor.execute("ALTER TABLE notes ADD COLUMN is_archived INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE notes ADD COLUMN view_count INTEGER DEFAULT 0")
        print("✅ 新列添加成功")
    except sqlite3.OperationalError as e:
        print(f"⚠️  列可能已存在: {e}")
    
    # 2. 创建FTS索引
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            title, message_text, content_markdown,
            content=notes, content_rowid=id
        )
    """)
    print("✅ FTS索引创建成功")
    
    # 3. 迁移现有数据到FTS
    cursor.execute("SELECT id, message_text FROM notes")
    for row in cursor.fetchall():
        cursor.execute(
            "INSERT INTO notes_fts(rowid, title, message_text) VALUES (?, ?, ?)",
            (row[0], '', row[1])
        )
    print("✅ 现有数据已迁移到FTS")
    
    # 4. 创建media_files表并迁移数据
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS media_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            thumbnail_path TEXT,
            display_order INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
        )
    """)
    
    # 迁移media_paths JSON到独立表
    cursor.execute("SELECT id, media_paths, media_type FROM notes WHERE media_paths IS NOT NULL")
    for row in cursor.fetchall():
        note_id, media_paths_json, media_type = row
        try:
            media_paths = json.loads(media_paths_json)
            for idx, path in enumerate(media_paths):
                cursor.execute("""
                    INSERT INTO media_files (note_id, file_path, file_type, display_order)
                    VALUES (?, ?, ?, ?)
                """, (note_id, path, media_type or 'unknown', idx))
        except (json.JSONDecodeError, TypeError):
            pass
    print("✅ 媒体文件迁移成功")
    
    # 5. 创建tags表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '#667eea',
            icon TEXT,
            use_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS note_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
            UNIQUE(note_id, tag_id)
        )
    """)
    print("✅ 标签系统创建成功")
    
    # 6. 创建user_preferences表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            theme TEXT DEFAULT 'light',
            view_mode TEXT DEFAULT 'grid',
            notes_per_page INTEGER DEFAULT 50,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    # 为现有用户创建默认偏好
    cursor.execute("SELECT id FROM users")
    for (user_id,) in cursor.fetchall():
        cursor.execute(
            "INSERT OR IGNORE INTO user_preferences (user_id) VALUES (?)",
            (user_id,)
        )
    print("✅ 用户偏好表创建成功")
    
    # 7. 创建索引
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_notes_user_time ON notes(user_id, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_media_note ON media_files(note_id)",
        "CREATE INDEX IF NOT EXISTS idx_note_tags_note ON note_tags(note_id)",
        "CREATE INDEX IF NOT EXISTS idx_note_tags_tag ON note_tags(tag_id)",
    ]
    for idx_sql in indexes:
        cursor.execute(idx_sql)
    print("✅ 索引创建成功")
    
    conn.commit()
    conn.close()
    
    print("🎉 数据库迁移完成！")

if __name__ == '__main__':
    migrate_v1_to_v2('data/notes.db')
```

**步骤3：验证迁移**
```python
# verify_migration.py
import sqlite3

def verify_migration(db_path):
    """验证迁移结果"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    checks = {
        "notes表新列": "SELECT title, content_html, updated_at, is_archived FROM notes LIMIT 1",
        "FTS索引": "SELECT * FROM notes_fts LIMIT 1",
        "media_files表": "SELECT COUNT(*) FROM media_files",
        "tags表": "SELECT COUNT(*) FROM tags",
        "user_preferences表": "SELECT COUNT(*) FROM user_preferences",
    }
    
    print("🔍 验证迁移结果...\n")
    
    for check_name, sql in checks.items():
        try:
            cursor.execute(sql)
            result = cursor.fetchone()
            print(f"✅ {check_name}: 通过")
        except sqlite3.Error as e:
            print(f"❌ {check_name}: 失败 - {e}")
    
    conn.close()

if __name__ == '__main__':
    verify_migration('data/notes.db')
```

---

### 2.2 前端架构设计

#### 2.2.1 技术栈选择矩阵

| 技术选项 | 优势 | 劣势 | 推荐度 | 选择 |
|---------|------|------|--------|------|
| **框架** |
| Vue 3 | ✅ 轻量、渐进式、中文文档好 | ⚠️ 生态略小于React | ⭐⭐⭐⭐⭐ | ✅ |
| React 18 | ✅ 生态最大、招聘容易 | ⚠️ 学习曲线陡、JSX语法 | ⭐⭐⭐⭐ | |
| Svelte | ✅ 性能最好、代码量少 | ❌ 生态小、社区小 | ⭐⭐⭐ | |
| **构建工具** |
| Vite | ✅ 极速热更新、现代化 | ⚠️ 对老浏览器支持需配置 | ⭐⭐⭐⭐⭐ | ✅ |
| Webpack | ✅ 成熟、配置灵活 | ❌ 配置复杂、构建慢 | ⭐⭐⭐ | |
| **UI库** |
| Element Plus | ✅ Vue 3专用、组件全 | ⚠️ 体积较大 | ⭐⭐⭐⭐⭐ | ✅ |
| Naive UI | ✅ TypeScript原生、轻量 | ⚠️ 文档略少 | ⭐⭐⭐⭐ | |
| Ant Design Vue | ✅ 企业级、成熟 | ⚠️ 设计语言偏商务 | ⭐⭐⭐⭐ | |
| 自定义UI | ✅ 完全掌控、轻量 | ❌ 开发成本高 | ⭐⭐⭐ | 部分使用 |
| **状态管理** |
| Pinia | ✅ Vue 3官方推荐、简洁 | 无 | ⭐⭐⭐⭐⭐ | ✅ |
| Vuex | ✅ 成熟 | ⚠️ 繁琐、已被Pinia取代 | ⭐⭐⭐ | |
| **类型系统** |
| TypeScript | ✅ 类型安全、IDE友好 | ⚠️ 学习成本 | ⭐⭐⭐⭐⭐ | ✅ |
| JavaScript | ✅ 简单 | ❌ 无类型安全 | ⭐⭐ | |
| **富文本编辑器** |
| TipTap | ✅ Vue友好、可扩展、现代 | ⚠️ 文档略少 | ⭐⭐⭐⭐⭐ | ✅ |
| Quill | ✅ 成熟、稳定 | ⚠️ 扩展性差 | ⭐⭐⭐⭐ | |
| ProseMirror | ✅ 强大、灵活 | ❌ 学习曲线陡 | ⭐⭐⭐ | |

**最终技术栈：**
```
Vue 3.3+ (Composition API + <script setup>)
+ Vite 5
+ TypeScript 5
+ Pinia (状态管理)
+ Vue Router 4 (路由)
+ Element Plus (UI组件库)
+ TipTap (富文本编辑器)
+ VueUse (实用工具Hooks)
+ Axios (HTTP客户端)
+ Day.js (日期处理)
+ VirtualScroller (虚拟滚动)
```

#### 2.2.2 完整项目结构

```
frontend/
├── public/
│   ├── favicon.ico
│   └── logo.png
├── src/
│   ├── main.ts                    # 应用入口
│   ├── App.vue                    # 根组件
│   ├── router/                    # 路由配置
│   │   ├── index.ts
│   │   └── guards.ts              # 路由守卫
│   ├── stores/                    # Pinia状态管理
│   │   ├── auth.ts                # 认证状态
│   │   ├── notes.ts               # 笔记状态
│   │   ├── tags.ts                # 标签状态
│   │   ├── search.ts              # 搜索状态
│   │   ├── ui.ts                  # UI状态（主题、侧边栏等）
│   │   └── user.ts                # 用户偏好
│   ├── composables/               # 组合式函数
│   │   ├── useNotes.ts            # 笔记CRUD
│   │   ├── useTags.ts             # 标签管理
│   │   ├── useSearch.ts           # 搜索逻辑
│   │   ├── useEditor.ts           # 编辑器功能
│   │   ├── useTheme.ts            # 主题切换
│   │   ├── useInfiniteScroll.ts   # 无限滚动
│   │   └── useMediaUpload.ts      # 媒体上传
│   ├── api/                       # API调用层
│   │   ├── client.ts              # Axios配置
│   │   ├── notes.ts               # 笔记API
│   │   ├── tags.ts                # 标签API
│   │   ├── auth.ts                # 认证API
│   │   └── media.ts               # 媒体API
│   ├── views/                     # 页面组件
│   │   ├── LoginView.vue
│   │   ├── NotesView.vue          # 笔记列表页
│   │   ├── NoteDetailView.vue     # 笔记详情页
│   │   ├── NoteEditView.vue       # 笔记编辑页
│   │   ├── SearchView.vue         # 搜索页
│   │   ├── TagsView.vue           # 标签管理页
│   │   ├── SettingsView.vue       # 设置页
│   │   └── StatsView.vue          # 统计页
│   ├── components/                # 组件
│   │   ├── layout/
│   │   │   ├── AppLayout.vue      # 主布局
│   │   │   ├── Sidebar.vue        # 侧边栏
│   │   │   ├── Header.vue         # 顶部栏
│   │   │   └── Footer.vue
│   │   ├── notes/
│   │   │   ├── NoteCard.vue       # 笔记卡片
│   │   │   ├── NoteList.vue       # 笔记列表
│   │   │   ├── NoteGrid.vue       # 笔记网格
│   │   │   ├── NoteTimeline.vue   # 时间线视图
│   │   │   ├── NoteFilter.vue     # 筛选器
│   │   │   └── NoteSkeleton.vue   # 骨架屏
│   │   ├── editor/
│   │   │   ├── TiptapEditor.vue   # 富文本编辑器
│   │   │   ├── EditorToolbar.vue  # 工具栏
│   │   │   ├── EditorMenuBubble.vue
│   │   │   └── EditorExtensions/  # 自定义扩展
│   │   ├── search/
│   │   │   ├── SearchBar.vue      # 搜索栏
│   │   │   ├── AdvancedSearch.vue # 高级搜索
│   │   │   ├── SearchHistory.vue  # 搜索历史
│   │   │   └── SearchSuggestions.vue
│   │   ├── tags/
│   │   │   ├── TagSelector.vue    # 标签选择器
│   │   │   ├── TagCloud.vue       # 标签云
│   │   │   ├── TagManager.vue     # 标签管理
│   │   │   └── TagInput.vue       # 标签输入
│   │   ├── media/
│   │   │   ├── MediaGallery.vue   # 媒体画廊
│   │   │   ├── MediaGrid.vue      # 媒体网格
│   │   │   ├── MediaUploader.vue  # 上传组件
│   │   │   └── MediaViewer.vue    # 媒体查看器
│   │   └── common/
│   │       ├── Button.vue
│   │       ├── Input.vue
│   │       ├── Modal.vue
│   │       ├── Toast.vue
│   │       ├── Loading.vue
│   │       ├── EmptyState.vue
│   │       └── ConfirmDialog.vue
│   ├── utils/                     # 工具函数
│   │   ├── format.ts              # 格式化函数
│   │   ├── validation.ts          # 验证函数
│   │   ├── storage.ts             # LocalStorage封装
│   │   ├── debounce.ts
│   │   └── constants.ts           # 常量定义
│   ├── types/                     # TypeScript类型定义
│   │   ├── note.ts
│   │   ├── tag.ts
│   │   ├── user.ts
│   │   ├── search.ts
│   │   └── api.ts
│   ├── styles/                    # 样式文件
│   │   ├── main.scss              # 主样式
│   │   ├── variables.scss         # CSS变量
│   │   ├── mixins.scss            # SCSS混入
│   │   ├── transitions.scss       # 过渡动画
│   │   └── utilities.scss         # 工具类
│   └── assets/                    # 静态资源
│       ├── icons/
│       ├── images/
│       └── fonts/
├── index.html
├── vite.config.ts                 # Vite配置
├── tsconfig.json                  # TypeScript配置
├── package.json
└── README.md
```

#### 2.2.3 主布局设计

**AppLayout.vue - 主布局组件**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useUIStore } from '@/stores/ui'
import Sidebar from './Sidebar.vue'
import Header from './Header.vue'

const uiStore = useUIStore()
const sidebarCollapsed = computed(() => uiStore.sidebarCollapsed)
const theme = computed(() => uiStore.theme)
</script>

<template>
  <div :class="['app-layout', `theme-${theme}`]">
    <!-- 侧边栏 -->
    <Sidebar 
      :collapsed="sidebarCollapsed"
      @toggle="uiStore.toggleSidebar"
    />
    
    <!-- 主内容区 -->
    <div 
      :class="['main-content', { 'sidebar-collapsed': sidebarCollapsed }]"
    >
      <!-- 顶部栏 -->
      <Header />
      
      <!-- 页面内容 -->
      <div class="content-wrapper">
        <router-view v-slot="{ Component, route }">
          <transition :name="route.meta.transition || 'fade'" mode="out-in">
            <component :is="Component" :key="route.path" />
          </transition>
        </router-view>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.app-layout {
  display: flex;
  min-height: 100vh;
  background-color: var(--bg-primary);
  transition: background-color 0.3s ease;
}

.main-content {
  flex: 1;
  margin-left: 260px;
  transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  
  &.sidebar-collapsed {
    margin-left: 80px;
  }
}

.content-wrapper {
  padding: 24px;
  min-height: calc(100vh - 70px);
}

// 主题样式
.theme-dark {
  --bg-primary: #1a1a1a;
  --bg-secondary: #2d2d2d;
  --text-primary: #ffffff;
  --text-secondary: #b0b0b0;
}

.theme-light {
  --bg-primary: #f5f7fa;
  --bg-secondary: #ffffff;
  --text-primary: #2c3e50;
  --text-secondary: #6c757d;
}

// 过渡动画
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
```

#### 2.2.4 侧边栏设计

**Sidebar.vue**

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useNotesStore } from '@/stores/notes'
import { useTagsStore } from '@/stores/tags'
import { 
  Home, 
  Document, 
  Collection, 
  Star, 
  Setting, 
  DataAnalysis,
  FolderOpened
} from '@element-plus/icons-vue'

interface Props {
  collapsed: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  toggle: []
}>()

const router = useRouter()
const route = useRoute()
const notesStore = useNotesStore()
const tagsStore = useTagsStore()

// 菜单项
const menuItems = computed(() => [
  {
    id: 'all',
    label: '全部笔记',
    icon: Home,
    path: '/notes',
    count: notesStore.totalCount
  },
  {
    id: 'favorites',
    label: '收藏',
    icon: Star,
    path: '/notes/favorites',
    count: notesStore.favoriteCount
  },
  {
    id: 'recent',
    label: '最近',
    icon: Document,
    path: '/notes/recent'
  },
  {
    id: 'stats',
    label: '统计',
    icon: DataAnalysis,
    path: '/stats'
  },
  {
    id: 'settings',
    label: '设置',
    icon: Setting,
    path: '/settings'
  }
])

// 标签列表（前10个）
const topTags = computed(() => tagsStore.tags.slice(0, 10))

const isActive = (path: string) => {
  return route.path === path
}

const navigateTo = (path: string) => {
  router.push(path)
}
</script>

<template>
  <aside :class="['sidebar', { collapsed }]">
    <!-- Logo区域 -->
    <div class="sidebar-header">
      <div class="logo">
        <img v-if="!collapsed" src="@/assets/logo.png" alt="Logo" />
        <span v-if="!collapsed" class="logo-text">Telegram Notes</span>
        <span v-else class="logo-icon">TN</span>
      </div>
      <button class="toggle-btn" @click="emit('toggle')">
        <el-icon><Expand /></el-icon>
      </button>
    </div>

    <!-- 菜单项 -->
    <nav class="sidebar-nav">
      <div class="nav-section">
        <h3 v-if="!collapsed" class="section-title">导航</h3>
        
        <div 
          v-for="item in menuItems" 
          :key="item.id"
          :class="['nav-item', { active: isActive(item.path) }]"
          @click="navigateTo(item.path)"
        >
          <el-icon class="nav-icon">
            <component :is="item.icon" />
          </el-icon>
          <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
          <span 
            v-if="!collapsed && item.count !== undefined" 
            class="nav-count"
          >
            {{ item.count }}
          </span>
        </div>
      </div>

      <!-- 标签快捷访问 -->
      <div v-if="!collapsed && topTags.length > 0" class="nav-section">
        <div class="section-header">
          <h3 class="section-title">标签</h3>
          <el-button 
            text 
            size="small" 
            @click="navigateTo('/tags')"
          >
            管理
          </el-button>
        </div>
        
        <div 
          v-for="tag in topTags" 
          :key="tag.id"
          class="tag-item"
          @click="navigateTo(`/notes?tag=${tag.id}`)"
        >
          <span 
            class="tag-color" 
            :style="{ backgroundColor: tag.color }"
          />
          <span class="tag-name">{{ tag.name }}</span>
          <span class="tag-count">{{ tag.use_count }}</span>
        </div>
      </div>

      <!-- 来源快捷访问 -->
      <div v-if="!collapsed" class="nav-section">
        <div class="section-header">
          <h3 class="section-title">来源</h3>
        </div>
        
        <div 
          v-for="source in notesStore.topSources" 
          :key="source.id"
          class="source-item"
          @click="navigateTo(`/notes?source=${source.id}`)"
        >
          <el-icon class="source-icon">
            <FolderOpened />
          </el-icon>
          <span class="source-name">{{ source.name }}</span>
          <span class="source-count">{{ source.count }}</span>
        </div>
      </div>
    </nav>

    <!-- 底部用户信息 -->
    <div v-if="!collapsed" class="sidebar-footer">
      <div class="user-info">
        <el-avatar :size="40">{{ userStore.username[0] }}</el-avatar>
        <div class="user-details">
          <span class="username">{{ userStore.username }}</span>
          <el-button text size="small" @click="logout">登出</el-button>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped lang="scss">
.sidebar {
  width: 260px;
  height: 100vh;
  background-color: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1000;
  
  &.collapsed {
    width: 80px;
    
    .sidebar-nav {
      padding: 12px 8px;
    }
    
    .nav-item {
      justify-content: center;
      padding: 12px;
    }
  }
}

.sidebar-header {
  height: 70px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-color);
  
  .logo {
    display: flex;
    align-items: center;
    gap: 12px;
    
    img {
      width: 36px;
      height: 36px;
    }
    
    .logo-text {
      font-size: 18px;
      font-weight: 700;
      color: var(--text-primary);
    }
    
    .logo-icon {
      font-size: 20px;
      font-weight: 700;
      color: var(--primary-color);
    }
  }
  
  .toggle-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 8px;
    border-radius: 6px;
    transition: background-color 0.2s;
    
    &:hover {
      background-color: var(--bg-hover);
    }
  }
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 20px 12px;
  
  &::-webkit-scrollbar {
    width: 6px;
  }
  
  &::-webkit-scrollbar-thumb {
    background-color: var(--border-color);
    border-radius: 3px;
  }
}

.nav-section {
  margin-bottom: 32px;
  
  .section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 12px;
    padding: 0 8px;
  }
  
  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 4px;
  
  .nav-icon {
    font-size: 20px;
    color: var(--text-secondary);
  }
  
  .nav-label {
    flex: 1;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .nav-count {
    font-size: 12px;
    color: var(--text-secondary);
    background-color: var(--bg-hover);
    padding: 2px 8px;
    border-radius: 12px;
  }
  
  &:hover {
    background-color: var(--bg-hover);
    
    .nav-icon {
      color: var(--primary-color);
    }
  }
  
  &.active {
    background-color: var(--primary-light);
    
    .nav-icon,
    .nav-label {
      color: var(--primary-color);
      font-weight: 600;
    }
  }
}

.tag-item,
.source-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
  margin-bottom: 2px;
  
  &:hover {
    background-color: var(--bg-hover);
  }
}

.tag-item {
  .tag-color {
    width: 12px;
    height: 12px;
    border-radius: 50%;
  }
  
  .tag-name {
    flex: 1;
    font-size: 13px;
    color: var(--text-primary);
  }
  
  .tag-count {
    font-size: 11px;
    color: var(--text-secondary);
  }
}

.source-item {
  .source-icon {
    font-size: 16px;
    color: var(--text-secondary);
  }
  
  .source-name {
    flex: 1;
    font-size: 13px;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .source-count {
    font-size: 11px;
    color: var(--text-secondary);
  }
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--border-color);
  
  .user-info {
    display: flex;
    align-items: center;
    gap: 12px;
    
    .user-details {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 4px;
      
      .username {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);
      }
    }
  }
}
</style>
```

#### 2.2.5 笔记列表视图

**NotesView.vue - 主笔记页面**

```vue
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNotesStore } from '@/stores/notes'
import { useSearchStore } from '@/stores/search'
import { useUIStore } from '@/stores/ui'
import SearchBar from '@/components/search/SearchBar.vue'
import NoteCard from '@/components/notes/NoteCard.vue'
import NoteList from '@/components/notes/NoteList.vue'
import NoteTimeline from '@/components/notes/NoteTimeline.vue'
import NoteFilter from '@/components/notes/NoteFilter.vue'
import NoteSkeleton from '@/components/notes/NoteSkeleton.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useInfiniteScroll } from '@/composables/useInfiniteScroll'

const route = useRoute()
const router = useRouter()
const notesStore = useNotesStore()
const searchStore = useSearchStore()
const uiStore = useUIStore()

// 视图模式
const viewMode = computed(() => uiStore.viewMode)
const setViewMode = (mode: 'grid' | 'list' | 'timeline') => {
  uiStore.setViewMode(mode)
}

// 笔记数据
const notes = computed(() => notesStore.notes)
const loading = computed(() => notesStore.loading)
const hasMore = computed(() => notesStore.hasMore)

// 筛选和搜索
const filterVisible = ref(false)
const activeFilters = computed(() => searchStore.activeFilters)

// 无限滚动
const { containerRef, isLoading: scrollLoading } = useInfiniteScroll({
  onLoad: async () => {
    if (hasMore.value && !loading.value) {
      await notesStore.loadMore()
    }
  },
  distance: 200
})

// 加载笔记
const loadNotes = async () => {
  const params = {
    search: route.query.search as string,
    source: route.query.source as string,
    tag: route.query.tag as string,
    favorite: route.query.favorite === '1',
    dateFrom: route.query.dateFrom as string,
    dateTo: route.query.dateTo as string
  }
  
  await notesStore.fetchNotes(params)
}

// 搜索处理
const handleSearch = (query: string) => {
  router.push({ 
    path: '/notes', 
    query: { ...route.query, search: query } 
  })
}

// 筛选处理
const handleFilter = (filters: any) => {
  searchStore.setFilters(filters)
  router.push({ 
    path: '/notes', 
    query: { ...route.query, ...filters } 
  })
  filterVisible.value = false
}

// 清除筛选
const clearFilters = () => {
  searchStore.clearFilters()
  router.push({ path: '/notes' })
}

// 创建笔记
const createNote = () => {
  router.push('/notes/new')
}

// 监听路由变化
watch(() => route.query, loadNotes, { deep: true })

onMounted(loadNotes)
</script>

<template>
  <div class="notes-view">
    <!-- 顶部工具栏 -->
    <div class="notes-toolbar">
      <!-- 搜索栏 -->
      <SearchBar 
        :model-value="route.query.search as string"
        @update:model-value="handleSearch"
        @advanced="filterVisible = true"
        class="search-bar"
      />
      
      <!-- 工具按钮 -->
      <div class="toolbar-actions">
        <!-- 视图切换 -->
        <el-button-group>
          <el-button 
            :type="viewMode === 'grid' ? 'primary' : ''"
            @click="setViewMode('grid')"
          >
            <el-icon><Grid /></el-icon>
          </el-button>
          <el-button 
            :type="viewMode === 'list' ? 'primary' : ''"
            @click="setViewMode('list')"
          >
            <el-icon><List /></el-icon>
          </el-button>
          <el-button 
            :type="viewMode === 'timeline' ? 'primary' : ''"
            @click="setViewMode('timeline')"
          >
            <el-icon><Timer /></el-icon>
          </el-button>
        </el-button-group>
        
        <!-- 筛选按钮 -->
        <el-badge 
          :value="Object.keys(activeFilters).length" 
          :hidden="Object.keys(activeFilters).length === 0"
        >
          <el-button @click="filterVisible = true">
            <el-icon><Filter /></el-icon>
            筛选
          </el-button>
        </el-badge>
        
        <!-- 创建按钮 -->
        <el-button type="primary" @click="createNote">
          <el-icon><Plus /></el-icon>
          新建笔记
        </el-button>
      </div>
    </div>

    <!-- 活动筛选标签 -->
    <div v-if="Object.keys(activeFilters).length > 0" class="active-filters">
      <el-tag
        v-for="(value, key) in activeFilters"
        :key="key"
        closable
        @close="clearFilters"
      >
        {{ key }}: {{ value }}
      </el-tag>
      <el-button text type="primary" @click="clearFilters">
        清除全部
      </el-button>
    </div>

    <!-- 统计信息 -->
    <div class="notes-stats">
      <span class="stats-item">
        共 <strong>{{ notesStore.totalCount }}</strong> 条笔记
      </span>
      <span v-if="activeFilters.source" class="stats-item">
        来源: <strong>{{ activeFilters.source }}</strong>
      </span>
    </div>

    <!-- 笔记内容区 -->
    <div ref="containerRef" class="notes-container">
      <!-- 加载中 -->
      <template v-if="loading && notes.length === 0">
        <NoteSkeleton :count="12" :view-mode="viewMode" />
      </template>
      
      <!-- 笔记列表 -->
      <template v-else-if="notes.length > 0">
        <!-- 网格视图 -->
        <div v-if="viewMode === 'grid'" class="notes-grid">
          <NoteCard 
            v-for="note in notes" 
            :key="note.id" 
            :note="note"
            @click="router.push(`/notes/${note.id}`)"
          />
        </div>
        
        <!-- 列表视图 -->
        <NoteList 
          v-else-if="viewMode === 'list'" 
          :notes="notes"
          @note-click="id => router.push(`/notes/${id}`)"
        />
        
        <!-- 时间线视图 -->
        <NoteTimeline 
          v-else 
          :notes="notes"
          @note-click="id => router.push(`/notes/${id}`)"
        />
        
        <!-- 加载更多指示器 -->
        <div v-if="scrollLoading" class="load-more">
          <el-icon class="is-loading"><Loading /></el-icon>
          加载中...
        </div>
        
        <!-- 没有更多 -->
        <div v-else-if="!hasMore" class="no-more">
          没有更多笔记了
        </div>
      </template>
      
      <!-- 空状态 -->
      <EmptyState 
        v-else
        title="暂无笔记"
        description="创建您的第一条笔记吧"
        :action="{ label: '创建笔记', onClick: createNote }"
      />
    </div>

    <!-- 高级筛选对话框 -->
    <NoteFilter 
      v-model="filterVisible"
      :filters="activeFilters"
      @apply="handleFilter"
      @reset="clearFilters"
    />
  </div>
</template>

<style scoped lang="scss">
.notes-view {
  max-width: 1400px;
  margin: 0 auto;
}

.notes-toolbar {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 20px;
  
  .search-bar {
    flex: 1;
    max-width: 600px;
  }
  
  .toolbar-actions {
    display: flex;
    gap: 12px;
    align-items: center;
  }
}

.active-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px;
  background-color: var(--bg-secondary);
  border-radius: 8px;
}

.notes-stats {
  display: flex;
  gap: 20px;
  align-items: center;
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--text-secondary);
  
  .stats-item {
    strong {
      color: var(--text-primary);
      font-weight: 600;
    }
  }
}

.notes-container {
  min-height: 400px;
}

.notes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.load-more,
.no-more {
  text-align: center;
  padding: 32px;
  font-size: 14px;
  color: var(--text-secondary);
}

.load-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

// 响应式
@media (max-width: 768px) {
  .notes-toolbar {
    flex-direction: column;
    align-items: stretch;
    
    .search-bar {
      max-width: none;
    }
    
    .toolbar-actions {
      justify-content: space-between;
    }
  }
  
  .notes-grid {
    grid-template-columns: 1fr;
  }
}
</style>
```

---

### 2.3 富文本编辑器设计

#### 2.3.1 TipTap编辑器集成

**TiptapEditor.vue - 核心编辑器组件**

```vue
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Image from '@tiptap/extension-image'
import Link from '@tiptap/extension-link'
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight'
import Table from '@tiptap/extension-table'
import TableRow from '@tiptap/extension-table-row'
import TableCell from '@tiptap/extension-table-cell'
import TableHeader from '@tiptap/extension-table-header'
import TaskList from '@tiptap/extension-task-list'
import TaskItem from '@tiptap/extension-task-item'
import Highlight from '@tiptap/extension-highlight'
import TextAlign from '@tiptap/extension-text-align'
import { lowlight } from 'lowlight'
import EditorToolbar from './EditorToolbar.vue'
import EditorBubbleMenu from './EditorBubbleMenu.vue'

interface Props {
  modelValue?: string
  placeholder?: string
  editable?: boolean
}

interface Emits {
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  placeholder: '开始输入...',
  editable: true
})

const emit = defineEmits<Emits>()

// 编辑器实例
const editor = useEditor({
  content: props.modelValue,
  editable: props.editable,
  extensions: [
    StarterKit.configure({
      codeBlock: false, // 使用CodeBlockLowlight替代
    }),
    Placeholder.configure({
      placeholder: props.placeholder,
    }),
    Image.configure({
      inline: true,
      allowBase64: true,
    }),
    Link.configure({
      openOnClick: false,
      HTMLAttributes: {
        target: '_blank',
        rel: 'noopener noreferrer',
      },
    }),
    CodeBlockLowlight.configure({
      lowlight,
    }),
    Table.configure({
      resizable: true,
    }),
    TableRow,
    TableCell,
    TableHeader,
    TaskList,
    TaskItem.configure({
      nested: true,
    }),
    Highlight.configure({
      multicolor: true,
    }),
    TextAlign.configure({
      types: ['heading', 'paragraph'],
    }),
  ],
  onUpdate: ({ editor }) => {
    const html = editor.getHTML()
    emit('update:modelValue', html)
    emit('change', html)
  },
})

// 监听外部value变化
watch(() => props.modelValue, (newValue) => {
  if (editor.value && newValue !== editor.value.getHTML()) {
    editor.value.commands.setContent(newValue)
  }
})

// 监听editable变化
watch(() => props.editable, (newValue) => {
  if (editor.value) {
    editor.value.setEditable(newValue)
  }
})

// 工具栏操作
const handleCommand = (command: string, value?: any) => {
  if (!editor.value) return
  
  const commands: Record<string, () => void> = {
    bold: () => editor.value!.chain().focus().toggleBold().run(),
    italic: () => editor.value!.chain().focus().toggleItalic().run(),
    strike: () => editor.value!.chain().focus().toggleStrike().run(),
    code: () => editor.value!.chain().focus().toggleCode().run(),
    h1: () => editor.value!.chain().focus().toggleHeading({ level: 1 }).run(),
    h2: () => editor.value!.chain().focus().toggleHeading({ level: 2 }).run(),
    h3: () => editor.value!.chain().focus().toggleHeading({ level: 3 }).run(),
    paragraph: () => editor.value!.chain().focus().setParagraph().run(),
    bulletList: () => editor.value!.chain().focus().toggleBulletList().run(),
    orderedList: () => editor.value!.chain().focus().toggleOrderedList().run(),
    taskList: () => editor.value!.chain().focus().toggleTaskList().run(),
    codeBlock: () => editor.value!.chain().focus().toggleCodeBlock().run(),
    blockquote: () => editor.value!.chain().focus().toggleBlockquote().run(),
    horizontalRule: () => editor.value!.chain().focus().setHorizontalRule().run(),
    undo: () => editor.value!.chain().focus().undo().run(),
    redo: () => editor.value!.chain().focus().redo().run(),
    left: () => editor.value!.chain().focus().setTextAlign('left').run(),
    center: () => editor.value!.chain().focus().setTextAlign('center').run(),
    right: () => editor.value!.chain().focus().setTextAlign('right').run(),
    justify: () => editor.value!.chain().focus().setTextAlign('justify').run(),
  }
  
  if (commands[command]) {
    commands[command]()
  } else if (command === 'link' && value) {
    editor.value.chain().focus().setLink({ href: value }).run()
  } else if (command === 'image' && value) {
    editor.value.chain().focus().setImage({ src: value }).run()
  } else if (command === 'highlight' && value) {
    editor.value.chain().focus().toggleHighlight({ color: value }).run()
  }
}

// 清理
onBeforeUnmount(() => {
  editor.value?.destroy()
})

defineExpose({
  editor,
  getHTML: () => editor.value?.getHTML() || '',
  getJSON: () => editor.value?.getJSON() || {},
  getText: () => editor.value?.getText() || '',
  setContent: (content: string) => editor.value?.commands.setContent(content),
  focus: () => editor.value?.commands.focus(),
})
</script>

<template>
  <div class="tiptap-editor">
    <!-- 工具栏 -->
    <EditorToolbar 
      v-if="editable && editor"
      :editor="editor" 
      @command="handleCommand"
    />
    
    <!-- 气泡菜单 -->
    <EditorBubbleMenu
      v-if="editable && editor"
      :editor="editor"
      @command="handleCommand"
    />
    
    <!-- 编辑器内容 -->
    <EditorContent 
      :editor="editor" 
      class="editor-content"
    />
  </div>
</template>

<style lang="scss">
.tiptap-editor {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  background-color: var(--bg-secondary);
}

.editor-content {
  .ProseMirror {
    padding: 20px;
    min-height: 300px;
    outline: none;
    font-size: 15px;
    line-height: 1.7;
    color: var(--text-primary);
    
    // Placeholder
    p.is-editor-empty:first-child::before {
      content: attr(data-placeholder);
      float: left;
      color: var(--text-secondary);
      pointer-events: none;
      height: 0;
    }
    
    // 标题
    h1, h2, h3, h4, h5, h6 {
      font-weight: 700;
      margin-top: 24px;
      margin-bottom: 16px;
      line-height: 1.3;
      color: var(--text-primary);
      
      &:first-child {
        margin-top: 0;
      }
    }
    
    h1 { font-size: 32px; }
    h2 { font-size: 24px; }
    h3 { font-size: 20px; }
    
    // 段落
    p {
      margin-bottom: 16px;
      
      &:last-child {
        margin-bottom: 0;
      }
    }
    
    // 列表
    ul, ol {
      padding-left: 24px;
      margin-bottom: 16px;
      
      li {
        margin-bottom: 8px;
        
        p {
          margin-bottom: 8px;
        }
      }
    }
    
    ul {
      list-style-type: disc;
    }
    
    ol {
      list-style-type: decimal;
    }
    
    // 任务列表
    ul[data-type="taskList"] {
      list-style: none;
      padding-left: 0;
      
      li {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        
        > label {
          flex: 0 0 auto;
          margin-top: 4px;
        }
        
        > div {
          flex: 1;
        }
      }
      
      input[type="checkbox"] {
        cursor: pointer;
      }
    }
    
    // 代码块
    code {
      background-color: var(--code-bg);
      color: var(--code-color);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.9em;
      font-family: 'Fira Code', 'Consolas', monospace;
    }
    
    pre {
      background-color: var(--code-block-bg);
      border-radius: 8px;
      padding: 16px;
      margin: 16px 0;
      overflow-x: auto;
      
      code {
        background: none;
        color: inherit;
        padding: 0;
        font-size: 14px;
        line-height: 1.6;
      }
    }
    
    // 引用
    blockquote {
      border-left: 4px solid var(--primary-color);
      padding-left: 16px;
      margin: 16px 0;
      color: var(--text-secondary);
      font-style: italic;
    }
    
    // 水平线
    hr {
      border: none;
      border-top: 2px solid var(--border-color);
      margin: 24px 0;
    }
    
    // 链接
    a {
      color: var(--primary-color);
      text-decoration: underline;
      cursor: pointer;
      
      &:hover {
        opacity: 0.8;
      }
    }
    
    // 图片
    img {
      max-width: 100%;
      height: auto;
      border-radius: 8px;
      margin: 16px 0;
    }
    
    // 高亮
    mark {
      background-color: #fef08a;
      padding: 2px 4px;
      border-radius: 3px;
    }
    
    // 表格
    table {
      border-collapse: collapse;
      width: 100%;
      margin: 16px 0;
      overflow: hidden;
      
      th, td {
        border: 1px solid var(--border-color);
        padding: 12px;
        text-align: left;
      }
      
      th {
        background-color: var(--bg-hover);
        font-weight: 600;
      }
      
      tr:hover {
        background-color: var(--bg-hover);
      }
    }
    
    // 选中样式
    ::selection {
      background-color: var(--primary-light);
    }
  }
}

// 深色模式变量
.theme-dark {
  --code-bg: #2d2d2d;
  --code-color: #e06c75;
  --code-block-bg: #1e1e1e;
}

.theme-light {
  --code-bg: #f5f5f5;
  --code-color: #e83e8c;
  --code-block-bg: #f8f8f8;
}
</style>
```

**EditorToolbar.vue - 工具栏组件**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Editor } from '@tiptap/vue-3'
import {
  Bold, Italic, Strikethrough, Code,
  Heading, List, OrderedList, CheckList,
  Quote, Link, Picture, Table,
  Undo, Redo, More
} from '@element-plus/icons-vue'

interface Props {
  editor: Editor
}

const props = defineProps<Props>()
const emit = defineEmits<{
  command: [command: string, value?: any]
}>()

// 链接对话框
const linkDialogVisible = ref(false)
const linkUrl = ref('')

// 图片对话框
const imageDialogVisible = ref(false)
const imageUrl = ref('')

// 工具按钮状态
const isActive = (name: string, attrs: any = {}) => {
  return props.editor.isActive(name, attrs)
}

const canUndo = computed(() => props.editor.can().undo())
const canRedo = computed(() => props.editor.can().redo())

// 插入链接
const insertLink = () => {
  if (linkUrl.value) {
    emit('command', 'link', linkUrl.value)
    linkDialogVisible.value = false
    linkUrl.value = ''
  }
}

// 插入图片
const insertImage = () => {
  if (imageUrl.value) {
    emit('command', 'image', imageUrl.value)
    imageDialogVisible.value = false
    imageUrl.value = ''
  }
}
</script>

<template>
  <div class="editor-toolbar">
    <div class="toolbar-group">
      <!-- 文本格式 -->
      <el-tooltip content="粗体 (Ctrl+B)">
        <el-button 
          text
          :class="{ 'is-active': isActive('bold') }"
          @click="emit('command', 'bold')"
        >
          <el-icon><Bold /></el-icon>
        </el-button>
      </el-tooltip>
      
      <el-tooltip content="斜体 (Ctrl+I)">
        <el-button 
          text
          :class="{ 'is-active': isActive('italic') }"
          @click="emit('command', 'italic')"
        >
          <el-icon><Italic /></el-icon>
        </el-button>
      </el-tooltip>
      
      <el-tooltip content="删除线">
        <el-button 
          text
          :class="{ 'is-active': isActive('strike') }"
          @click="emit('command', 'strike')"
        >
          <el-icon><Strikethrough /></el-icon>
        </el-button>
      </el-tooltip>
      
      <el-tooltip content="代码">
        <el-button 
          text
          :class="{ 'is-active': isActive('code') }"
          @click="emit('command', 'code')"
        >
          <el-icon><Code /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <el-divider direction="vertical" />

    <div class="toolbar-group">
      <!-- 标题 -->
      <el-dropdown @command="(cmd: string) => emit('command', cmd)">
        <el-button text>
          <el-icon><Heading /></el-icon>
          <span class="dropdown-label">标题</span>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="h1" :class="{ 'is-active': isActive('heading', { level: 1 }) }">
              <h1 style="margin: 0">一级标题</h1>
            </el-dropdown-item>
            <el-dropdown-item command="h2" :class="{ 'is-active': isActive('heading', { level: 2 }) }">
              <h2 style="margin: 0">二级标题</h2>
            </el-dropdown-item>
            <el-dropdown-item command="h3" :class="{ 'is-active': isActive('heading', { level: 3 }) }">
              <h3 style="margin: 0">三级标题</h3>
            </el-dropdown-item>
            <el-dropdown-item command="paragraph" :class="{ 'is-active': isActive('paragraph') }">
              正文
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <el-divider direction="vertical" />

    <div class="toolbar-group">
      <!-- 列表 -->
      <el-tooltip content="无序列表">
        <el-button 
          text
          :class="{ 'is-active': isActive('bulletList') }"
          @click="emit('command', 'bulletList')"
        >
          <el-icon><List /></el-icon>
        </el-button>
      </el-tooltip>
      
      <el-tooltip content="有序列表">
        <el-button 
          text
          :class="{ 'is-active': isActive('orderedList') }"
          @click="emit('command', 'orderedList')"
        >
          <el-icon><OrderedList /></el-icon>
        </el-button>
      </el-tooltip>
      
      <el-tooltip content="任务列表">
        <el-button 
          text
          :class="{ 'is-active': isActive('taskList') }"
          @click="emit('command', 'taskList')"
        >
          <el-icon><CheckList /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <el-divider direction="vertical" />

    <div class="toolbar-group">
      <!-- 引用 -->
      <el-tooltip content="引用">
        <el-button 
          text
          :class="{ 'is-active': isActive('blockquote') }"
          @click="emit('command', 'blockquote')"
        >
          <el-icon><Quote /></el-icon>
        </el-button>
      </el-tooltip>
      
      <!-- 链接 -->
      <el-tooltip content="插入链接">
        <el-button 
          text
          :class="{ 'is-active': isActive('link') }"
          @click="linkDialogVisible = true"
        >
          <el-icon><Link /></el-icon>
        </el-button>
      </el-tooltip>
      
      <!-- 图片 -->
      <el-tooltip content="插入图片">
        <el-button 
          text
          @click="imageDialogVisible = true"
        >
          <el-icon><Picture /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <el-divider direction="vertical" />

    <div class="toolbar-group">
      <!-- 撤销/重做 -->
      <el-tooltip content="撤销 (Ctrl+Z)">
        <el-button 
          text
          :disabled="!canUndo"
          @click="emit('command', 'undo')"
        >
          <el-icon><Undo /></el-icon>
        </el-button>
      </el-tooltip>
      
      <el-tooltip content="重做 (Ctrl+Shift+Z)">
        <el-button 
          text
          :disabled="!canRedo"
          @click="emit('command', 'redo')"
        >
          <el-icon><Redo /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <!-- 链接对话框 -->
    <el-dialog 
      v-model="linkDialogVisible" 
      title="插入链接" 
      width="500px"
    >
      <el-form @submit.prevent="insertLink">
        <el-form-item label="链接地址">
          <el-input 
            v-model="linkUrl" 
            placeholder="https://example.com"
            autofocus
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="linkDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="insertLink">插入</el-button>
      </template>
    </el-dialog>

    <!-- 图片对话框 -->
    <el-dialog 
      v-model="imageDialogVisible" 
      title="插入图片" 
      width="500px"
    >
      <el-form @submit.prevent="insertImage">
        <el-form-item label="图片地址">
          <el-input 
            v-model="imageUrl" 
            placeholder="https://example.com/image.jpg"
            autofocus
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="imageDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="insertImage">插入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
  background-color: var(--bg-hover);
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 4px;
}

.el-button {
  &.is-active {
    background-color: var(--primary-light);
    color: var(--primary-color);
  }
}

.dropdown-label {
  margin-left: 4px;
  font-size: 14px;
}

:deep(.el-dropdown-menu__item) {
  &.is-active {
    background-color: var(--primary-light);
    color: var(--primary-color);
  }
}
</style>
```

---

### 2.4 搜索和高级筛选

#### 2.4.1 SearchBar组件

**SearchBar.vue**

```vue
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { Search, Filter } from '@element-plus/icons-vue'
import { useSearchStore } from '@/stores/search'

interface Props {
  modelValue?: string
  placeholder?: string
  showAdvanced?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  placeholder: '搜索笔记...',
  showAdvanced: true
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'search', value: string): void
  (e: 'advanced'): void
}>()

const searchStore = useSearchStore()

const searchInput = ref(props.modelValue)
const suggestions = computed(() => searchStore.suggestions)
const recentSearches = computed(() => searchStore.recentSearches)
const showSuggestions = ref(false)

// 防抖搜索
const debouncedSearch = useDebounceFn((value: string) => {
  emit('update:modelValue', value)
  emit('search', value)
  
  if (value) {
    searchStore.addToHistory(value)
  }
}, 300)

watch(searchInput, debouncedSearch)

// 搜索建议点击
const selectSuggestion = (suggestion: string) => {
  searchInput.value = suggestion
  showSuggestions.value = false
  emit('search', suggestion)
}

// 清除搜索
const clearSearch = () => {
  searchInput.value = ''
  emit('update:modelValue', '')
  emit('search', '')
}

// 焦点处理
const handleFocus = () => {
  if (recentSearches.value.length > 0) {
    showSuggestions.value = true
  }
}

const handleBlur = () => {
  // 延迟隐藏，以便点击建议项生效
  setTimeout(() => {
    showSuggestions.value = false
  }, 200)
}
</script>

<template>
  <div class="search-bar">
    <el-input
      v-model="searchInput"
      :placeholder="placeholder"
      size="large"
      clearable
      @focus="handleFocus"
      @blur="handleBlur"
      @clear="clearSearch"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
      
      <template v-if="showAdvanced" #suffix>
        <el-button 
          text 
          @click="emit('advanced')"
        >
          <el-icon><Filter /></el-icon>
          高级
        </el-button>
      </template>
    </el-input>

    <!-- 搜索建议 -->
    <transition name="fade">
      <div 
        v-if="showSuggestions && (suggestions.length > 0 || recentSearches.length > 0)" 
        class="suggestions-dropdown"
      >
        <!-- 最近搜索 -->
        <div v-if="recentSearches.length > 0" class="suggestions-section">
          <div class="section-header">
            <span>最近搜索</span>
            <el-button 
              text 
              size="small" 
              @click="searchStore.clearHistory()"
            >
              清除
            </el-button>
          </div>
          <div 
            v-for="(item, index) in recentSearches.slice(0, 5)" 
            :key="index"
            class="suggestion-item recent"
            @click="selectSuggestion(item)"
          >
            <el-icon class="item-icon"><Search /></el-icon>
            <span class="item-text">{{ item }}</span>
          </div>
        </div>

        <!-- 搜索建议 -->
        <div v-if="suggestions.length > 0" class="suggestions-section">
          <div class="section-header">
            <span>建议</span>
          </div>
          <div 
            v-for="(item, index) in suggestions" 
            :key="index"
            class="suggestion-item"
            @click="selectSuggestion(item)"
          >
            <el-icon class="item-icon"><Search /></el-icon>
            <span class="item-text" v-html="highlightMatch(item, searchInput)" />
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped lang="scss">
.search-bar {
  position: relative;
  width: 100%;
}

.suggestions-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background-color: var(--bg-secondary);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  max-height: 400px;
  overflow-y: auto;
  z-index: 1000;
}

.suggestions-section {
  padding: 8px 0;
  
  &:not(:last-child) {
    border-bottom: 1px solid var(--border-color);
  }
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
  
  &:hover {
    background-color: var(--bg-hover);
  }
  
  .item-icon {
    font-size: 16px;
    color: var(--text-secondary);
  }
  
  .item-text {
    flex: 1;
    font-size: 14px;
    color: var(--text-primary);
  }
  
  &.recent {
    .item-icon {
      color: var(--primary-color);
    }
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
```

---

**(文档继续，由于字数限制，下面提供完整目录结构，您可以要求我继续编写任何特定部分)**

---

## 完整文档目录（未完待续）

### 已完成部分：
✅ 第一部分：现状分析
✅ 第二部分：超详细重构方案（2.1-2.4 部分）
  - 2.1 数据库设计方案 ✅
  - 2.2 前端架构设计 ✅
  - 2.3 富文本编辑器设计 ✅
  - 2.4 搜索和高级筛选 (部分) ✅

### 待补充部分：
- 2.4 搜索和高级筛选（完整）
- 2.5 标签和分类系统
- 2.6 多视图浏览
- 2.7 批量操作设计
- 2.8 移动端适配
- 2.9 设计系统
- 第三部分：技术实施方案
- 第四部分：CSS设计系统
- 第五部分：功能优先级和实施路线
- 第六部分：性能优化方案
- 第七部分：安全考虑
- 第八部分：部署和测试
- 第九部分：迁移计划

---

## 文档使用说明

本文档为 **Save-Restricted-Bot Web UI重构完整指导手册**，开发者可以按照文档逐步实施：

1. **阅读第一部分**：理解现状和问题
2. **研究第二部分**：学习新架构设计
3. **执行数据库迁移**：运行2.1节的迁移脚本
4. **搭建前端项目**：按照2.2节的目录结构创建
5. **实现核心组件**：复制代码示例并调整
6. **集成后端API**：参考第三部分API设计
7. **应用设计系统**：使用第四部分CSS规范
8. **分阶段上线**：遵循第五部分实施路线
9. **性能优化**：应用第六部分策略
10. **安全加固**：检查第七部分清单
11. **测试部署**：执行第八部分流程
12. **数据迁移**：按第九部分平滑过渡

---

**文档状态**: 🔄 持续编写中  
**当前完成度**: ~35%  
**预计总页数**: 200-300页
