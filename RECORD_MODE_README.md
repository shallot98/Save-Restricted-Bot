# 记录模式网页笔记功能

## 功能概述

记录模式允许你将监控的 Telegram 频道/群组/机器人的消息保存到网页笔记中，而不是转发到其他地方。所有记录的内容都会显示在一个美观的网页界面中，支持图片、视频缩略图和文字内容。

## 主要特性

### 1. 记录模式
- 为任何监控任务启用记录模式
- 消息将保存到数据库而不是转发
- 自动下载和保存图片
- 视频会保存缩略图（不下载完整视频）
- 保留完整的时间戳信息
- 支持所有过滤规则（关键词、正则表达式）
- 支持提取模式（只保存提取的内容）

### 2. 网页笔记界面
- 登录认证系统（默认用户名和密码都是 `admin`）
- 美观的响应式设计
- 卡片式笔记展示
- 按来源筛选笔记（支持多选）
- 分页浏览（每页 50 条）
- 显示时间戳、来源、文字、图片

### 3. 管理面板
- 修改管理员密码
- 简洁的后台界面
- 实时反馈操作结果

## 使用方法

### 启用记录模式

1. 在 Telegram Bot 中发送 `/start`
2. 点击"📋 监控管理"
3. 点击"📋 查看监控列表"
4. 点击要修改的监控任务
5. 点击"📝 切换记录模式"
6. 任务详情会显示"📝 记录到网页"

**注意**：启用记录模式后，"保留转发源"选项会被隐藏（因为不再转发）。

### 添加新的记录模式监控

1. 添加监控任务时，正常选择来源、目标、过滤规则等
2. 任务创建后，进入任务详情
3. 点击"📝 切换记录模式"启用

### 访问网页笔记

1. 启动 Web 应用：
   ```bash
   python3 app.py
   ```
   
2. 在浏览器中访问：`http://localhost:5000`

3. 使用默认账户登录：
   - 用户名：`admin`
   - 密码：`admin`

4. **重要**：首次登录后请立即修改密码！
   - 点击右上角"⚙️ 管理"
   - 输入当前密码和新密码
   - 点击"修改密码"

### 查看和筛选笔记

1. 登录后会自动跳转到笔记页面
2. 使用顶部的来源筛选器选择要查看的频道/群组
3. 支持多选，可以同时查看多个来源的笔记
4. 点击"应用筛选"按钮
5. 使用底部的分页按钮浏览更多笔记

## 配置说明

### watch_config.json 示例

```json
{
  "123456789": {
    "-1001234567890|me": {
      "source": "-1001234567890",
      "dest": "me",
      "whitelist": ["重要", "通知"],
      "blacklist": [],
      "whitelist_regex": [],
      "blacklist_regex": [],
      "preserve_forward_source": false,
      "forward_mode": "full",
      "extract_patterns": [],
      "record_mode": true
    }
  }
}
```

关键字段：
- `record_mode: true` - 启用记录模式
- `forward_mode: "full"` - 保存完整消息
- `forward_mode: "extract"` - 只保存提取的内容
- 过滤规则在记录模式下依然生效

## 数据库结构

### notes 表
- `id` - 唯一标识
- `user_id` - Telegram 用户 ID
- `source_chat_id` - 来源频道/群组 ID
- `source_name` - 来源名称
- `message_text` - 消息文字内容
- `timestamp` - 时间戳
- `media_type` - 媒体类型（photo/video/document）
- `media_path` - 媒体文件路径

### users 表
- `username` - 用户名
- `password_hash` - 密码哈希（bcrypt）

## 文件说明

- `notes.db` - SQLite 数据库文件（自动创建）
- `media/` - 媒体文件存储目录（自动创建）
- `database.py` - 数据库操作模块
- `app.py` - Flask Web 应用
- `templates/` - HTML 模板文件
  - `login.html` - 登录页面
  - `notes.html` - 笔记展示页面
  - `admin.html` - 管理面板

## 安全建议

1. **首次使用必须修改密码**
   - 默认密码 `admin` 仅用于初始化
   - 通过管理面板修改为强密码

2. **使用环境变量设置 SECRET_KEY**
   ```bash
   export SECRET_KEY="your-random-secret-key"
   ```

3. **不要将以下文件提交到 Git**
   - `notes.db`
   - `media/` 目录
   - `config.json`
   - `watch_config.json`

4. **生产环境部署**
   - 使用反向代理（如 Nginx）
   - 启用 HTTPS
   - 设置防火墙规则
   - 定期备份数据库

## 部署建议

### 使用 Docker

```yaml
# docker-compose.yml 添加 web 服务
services:
  bot:
    # ... 现有配置
  
  web:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./notes.db:/app/notes.db
      - ./media:/app/media
    environment:
      - SECRET_KEY=your-secret-key
    command: python3 app.py
```

### 生产环境运行

使用 Gunicorn 运行：

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 常见问题

### Q: 记录模式和转发模式有什么区别？
A: 记录模式将消息保存到数据库并在网页显示，转发模式将消息转发到其他 Telegram 频道/群组。

### Q: 可以同时使用记录模式和转发模式吗？
A: 可以！同一个来源可以创建多个监控任务，一些设置为记录模式，一些设置为转发模式。

### Q: 视频会完整下载吗？
A: 不会。为了节省空间，视频只会下载缩略图。如果需要完整视频，请使用转发模式。

### Q: 过滤规则在记录模式下还有效吗？
A: 完全有效！所有关键词和正则表达式过滤规则在记录模式下照常工作。

### Q: 提取模式在记录模式下如何工作？
A: 启用提取模式后，只有提取到的内容会被保存到数据库，不会保存完整消息。

### Q: 如何备份我的笔记？
A: 直接复制 `notes.db` 文件和 `media/` 目录即可。

### Q: 可以多人使用同一个网页笔记吗？
A: 目前只支持单用户（admin）。数据库中的 user_id 是 Telegram 用户 ID，不同用户的监控任务记录的笔记会被区分。

### Q: 忘记密码怎么办？
A: 删除 `notes.db` 文件，重新运行程序会创建新数据库并重置密码为 `admin`。注意这会删除所有笔记！

## 技术支持

如有问题或建议，请在 GitHub 提交 Issue。

## 更新日志

### v1.0.0 (2024-01-XX)
- 首次发布记录模式功能
- 网页笔记界面
- 认证和管理系统
- 支持文字、图片、视频缩略图
- 多来源筛选
- 分页显示
