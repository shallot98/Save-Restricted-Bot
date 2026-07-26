# Save Restricted Bot

*A Telegram Bot, Which can send you restricted content by it's post link*

## ⚠️ Important: Configuration and Data Protection

**Your configuration and data are now protected from code updates!**

✅ **Auto-protected content**:
- `data/config/config.json` - Bot configuration (TOKEN, ID, HASH, STRING)
- `data/notes.db` - Database (notes + watch tasks)
- `data/` - All user data (database, media files, configs)
- `*.session` - Session files

📖 **Details**: See [DATA_PROTECTION.md](docs/guides/DATA_PROTECTION.md)

🔄 **Safe code update**:
```bash
git pull  # Your config and data will be preserved automatically
```

---

## 📖 文档导航 | Documentation

- [🚀 快速开始 (Quick Start)](docs/guides/QUICKSTART.md) - 3分钟快速部署
- [⚙️ 详细设置指南 (Setup Guide)](docs/guides/SETUP_GUIDE.md) - 完整配置教程
- [📝 使用示例 (Usage Examples)](docs/guides/USAGE_EXAMPLES.md) - 各种使用场景
- [🇨🇳 完整中文文档 (Full Chinese Docs)](README.zh-CN.md)
- [🇬🇧 English Documentation](#english-documentation)
- [🇨🇳 中文文档](#中文文档)

---

## English Documentation

### 🚀 NEW: Auto Setup Script

**No need to manually generate Session String anymore!** 

Use our new auto-configuration script for easy setup:

```bash
python setup.py
```

The script will:
- ✅ Guide you through entering Bot Token, API ID, and API Hash
- ✅ Automatically login to Telegram and generate Session String
- ✅ Save all configuration to `.env` and `config.json`

📖 [See detailed setup guide](docs/guides/SETUP_GUIDE.md)

### Features

- Forward restricted content from Telegram channels/groups
- Support for public, private, and bot chats
- Multi-post range downloads
- Media-type aware forwarding
- Real-time download/upload progress
- **🆕 Auto Session String generation**
- **🆕 Record Mode** - Save monitored content to beautiful web notes
  - Save text, images, and video thumbnails
  - Filter and extract mode support
  - Secure web interface with authentication
  - Pagination and source filtering

### Variables

- `HASH` Your API Hash from my.telegram.org
- `ID` Your API ID from my.telegram.org
- `TOKEN` Your bot token from @BotFather
- `STRING` Your session string (can be auto-generated with `setup.py` script)

### Usage

**FOR PUBLIC CHATS**

_just send post/s link_


**FOR PRIVATE CHATS**

_first send invite link of the chat (unnecessary if the account of string session already member of the chat)
then send post/s link_


**FOR BOT CHATS**

_send link with '/b/', bot's username and message id, you might want to install some unofficial client to get the id like below_

```
https://t.me/b/botusername/4321
```

**MULTI POSTS**

_send public/private posts link as explained above with formate "from - to" to send multiple messages like below_


```
https://t.me/xxxx/1001-1010

https://t.me/c/xxxx/101 - 120
```

_note that space in between doesn't matter_

### 📝 Record Mode

Record Mode allows you to save monitored content to a beautiful web interface instead of forwarding:

**Features:**
- Save messages as web notes with text, images, and video thumbnails
- All filter rules (keywords, regex) still apply
- Extract mode works with record mode
- Secure login with admin credentials (default: admin/admin)
- Filter notes by source
- Pagination support (50 notes per page)
- Change password through admin panel
- **✏️ Edit and delete notes** - Manage your saved notes directly from web interface
- **🔒 Data protection** - All user data stored in independent `data/` directory

**How to use:**
1. Set up a monitoring task through the bot
2. Click on the task in the task list
3. Click "📝 切换记录模式" (Toggle Record Mode)
4. Messages matching your filters will be saved to the web interface

**Access the web interface:**
```bash
# Start the Flask web application
python app.py
```

Then visit `http://localhost:5000` in your browser and login with:
- Username: `admin`
- Password: `admin`

**Note:** Change the default password immediately after first login through the Admin Panel.

### 💾 Data Storage & Protection

**All user data is now stored in an independent `data/` directory:**

```
data/
├── notes.db       # Database with all saved notes, user accounts, and watch tasks
└── media/         # Downloaded images and video thumbnails
```

**Why this matters:**
- ✅ **Safe updates**: When updating bot code via `git pull`, your data is never overwritten
- ✅ **Easy backup**: Just backup the entire `data/` directory
- ✅ **Easy migration**: Move the `data/` directory to a new server to keep all your notes
- ✅ **Gitignored**: The `data/` directory is automatically ignored by git to prevent accidental commits

**Important:** 
- Watch configurations are stored in `data/notes.db` (auto-migrated from `data/config/watch_config.json` if present)
- Both `data/` directory and `*.session` are independent of code updates
- Always backup the whole `data/` directory before major system changes

### Deployment

#### Method 0: Quick Setup (Recommended for First-Time Users)

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the auto-configuration script:
```bash
python setup.py
```

Follow the prompts to:
- Enter Bot Token (from @BotFather)
- Enter API ID and Hash (from my.telegram.org)
- Optionally auto-generate Session String by logging into Telegram

4. Start the bot:
```bash
python main.py
```

Or deploy with Docker Compose:
```bash
docker-compose up -d
```

📖 [See detailed setup guide](docs/guides/SETUP_GUIDE.md)

#### Method 1: Using Docker (Manual Configuration)

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Run setup script or edit `config.json` manually:
```bash
python setup.py
```

Or manually edit `config.json`:
```json
{
    "TOKEN": "your_bot_token",
    "ID": "your_api_id",
    "HASH": "your_api_hash",
    "STRING": "your_session_string"
}
```

3. Build the Docker image:
```bash
docker build -t save-restricted-bot .
```

4. Run the container:
```bash
docker run -d --name telegram-bot -p 10000:10000 save-restricted-bot
```

Or use environment variables:
```bash
docker run -d --name telegram-bot \
  -e TOKEN="your_bot_token" \
  -e ID="your_api_id" \
  -e HASH="your_api_hash" \
  -e STRING="your_session_string" \
  -p 10000:10000 \
  save-restricted-bot
```

#### Method 2: Using Docker Compose (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Run setup script to generate configuration:
```bash
pip install pyrogram tgcrypto
python setup.py
```

This will create `.env` and `config.json` files automatically.

Or manually create `.env` file:
```env
TOKEN=your_bot_token
ID=your_api_id
HASH=your_api_hash
STRING=your_session_string
```

3. Start services (web + bot):
```bash
docker compose up -d --build
```

You can also start only one service:
```bash
docker compose up -d web
docker compose up -d bot
```

4. View logs:
```bash
docker compose logs -f
```

5. Stop services:
```bash
docker compose down
```

#### Method 3: Heroku Deployment

Use the included `Procfile` for Heroku deployment. Set the environment variables in Heroku dashboard.

---

## 中文文档

### 🚀 新功能：自动配置脚本

**无需再手动生成 Session String！**

使用我们的新自动配置脚本，轻松完成设置：

```bash
python setup.py
```

脚本会自动：
- ✅ 引导你输入 Bot Token、API ID 和 API Hash
- ✅ 自动登录 Telegram 并生成 Session String
- ✅ 保存所有配置到 `.env` 和 `config.json`

📖 [查看详细设置指南](docs/guides/SETUP_GUIDE.md)

### 功能特性

- 转发 Telegram 频道/群组的受限内容
- 支持公开、私有和机器人聊天
- 批量下载多条消息
- 智能识别媒体类型并转发
- 实时显示下载/上传进度
- **🆕 自动生成 Session String**

### 配置变量

- `HASH` 你的 API Hash，从 my.telegram.org 获取
- `ID` 你的 API ID，从 my.telegram.org 获取
- `TOKEN` 你的机器人 token，从 @BotFather 获取
- `STRING` 你的会话字符串（可通过 `setup.py` 脚本自动生成）

### 使用说明

**公开频道/群组**

_直接发送消息链接即可_


**私有频道/群组**

_首先发送频道/群组的邀请链接（如果你的会话账号已经是成员则不需要），然后发送消息链接_


**机器人聊天**

_发送包含 '/b/' 的链接，格式为机器人用户名和消息 ID，你可能需要安装一些非官方客户端来获取消息 ID，格式如下：_

```
https://t.me/b/botusername/4321
```

**批量下载多条消息**

_发送消息链接时使用 "起始 - 结束" 的格式来下载多条消息，如下所示：_

```
https://t.me/xxxx/1001-1010

https://t.me/c/xxxx/101 - 120
```

_注意：中间的空格可有可无_

### 📝 记录模式与网页笔记

记录模式允许你将监控的内容保存到美观的网页界面中，而不是转发到其他聊天：

**功能特性：**
- 保存文本、图片和视频缩略图到网页笔记
- 所有过滤规则（关键词、正则表达式）仍然有效
- 提取模式可以与记录模式配合使用
- 使用管理员账号安全登录（默认：admin/admin）
- 按来源筛选笔记
- 分页支持（每页 50 条笔记）
- 在管理面板中修改密码
- **✏️ 编辑和删除笔记** - 直接在网页界面管理你保存的笔记
- **🔒 数据保护** - 所有用户数据存储在独立的 `data/` 目录中

**使用方法：**
1. 通过机器人设置一个监控任务
2. 在任务列表中点击该任务
3. 点击 "📝 切换记录模式"
4. 符合过滤规则的消息将被保存到网页界面

**访问网页界面：**
```bash
# 启动 Flask Web 应用
python app.py
```

然后在浏览器中访问 `http://localhost:5000`，使用以下账号登录：
- 用户名：`admin`
- 密码：`admin`

**注意：** 首次登录后请立即通过管理面板修改默认密码。

### 💾 数据存储与保护

**所有用户数据现在都存储在独立的 `data/` 目录中：**

```
data/
├── notes.db       # 包含所有保存的笔记和用户账户的数据库
└── media/         # 下载的图片和视频缩略图
```

**为什么这很重要：**
- ✅ **安全更新**：使用 `git pull` 更新代码时，你的数据永远不会被覆盖
- ✅ **轻松备份**：只需备份整个 `data/` 目录
- ✅ **轻松迁移**：将 `data/` 目录移动到新服务器即可保留所有笔记
- ✅ **Git 忽略**：`data/` 目录会被 git 自动忽略，防止意外提交

**重要提示：**
- 监控配置存储在 `data/notes.db` 中（如存在 `data/config/watch_config.json` 会自动迁移一次）
- `data/` 目录和 `*.session` 都独立于代码更新
- 进行重大系统更改之前，请务必备份整个 `data/` 目录

### 部署教程

#### 方法零：快速设置（推荐首次使用）

1. 克隆仓库：
```bash
git clone <仓库地址>
cd <仓库目录>
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 运行自动配置脚本：
```bash
python setup.py
```

按提示操作：
- 输入 Bot Token（从 @BotFather 获取）
- 输入 API ID 和 Hash（从 my.telegram.org 获取）
- 选择是否自动生成 Session String（通过登录 Telegram）

4. 启动机器人：
```bash
python main.py
```

或使用 Docker Compose 部署：
```bash
docker-compose up -d
```

📖 [查看详细设置指南](docs/guides/SETUP_GUIDE.md)

#### 方法一：使用 Docker 部署（手动配置）

1. 克隆仓库：
```bash
git clone <仓库地址>
cd <仓库目录>
```

2. 运行设置脚本或手动编辑配置：
```bash
python setup.py
```

或手动编辑 `config.json`：
```json
{
    "TOKEN": "你的机器人token",
    "ID": "你的API ID",
    "HASH": "你的API Hash",
    "STRING": "你的会话字符串"
}
```

3. 构建 Docker 镜像：
```bash
docker build -t save-restricted-bot .
```

4. 运行容器：
```bash
docker run -d --name telegram-bot -p 10000:10000 save-restricted-bot
```

或者使用环境变量方式运行：
```bash
docker run -d --name telegram-bot \
  -e TOKEN="你的机器人token" \
  -e ID="你的API ID" \
  -e HASH="你的API Hash" \
  -e STRING="你的会话字符串" \
  -p 10000:10000 \
  save-restricted-bot
```

#### 方法二：使用 Docker Compose 部署（推荐）

1. 克隆仓库：
```bash
git clone <仓库地址>
cd <仓库目录>
```

2. 运行设置脚本生成配置：
```bash
pip install pyrogram tgcrypto
python setup.py
```

这将自动创建 `.env` 和 `config.json` 文件。

或手动创建 `.env` 文件：
```env
TOKEN=你的机器人token
ID=你的API ID
HASH=你的API Hash
STRING=你的会话字符串
```

3. 启动机器人：
```bash
docker-compose up -d
```

4. 查看日志：
```bash
docker-compose logs -f
```

5. 停止机器人：
```bash
docker-compose down
```

6. 重启机器人：
```bash
docker-compose restart
```

7. 更新机器人（拉取最新代码后）：
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

#### 方法三：Heroku 部署

使用包含的 `Procfile` 文件进行 Heroku 部署。在 Heroku 控制面板中设置环境变量即可。

### 获取必要的凭据

#### 🚀 推荐方式：使用自动配置脚本

最简单的方法是运行 `python setup.py`，它会自动引导你完成所有步骤！

#### 手动获取凭据

如果你想手动配置，请按以下步骤操作：

#### 1. 获取 API ID 和 API Hash

1. 访问 https://my.telegram.org
2. 使用你的手机号登录
3. 点击 "API development tools"
4. 填写应用信息（如果是第一次）
5. 你将获得 `api_id` 和 `api_hash`

#### 2. 获取 Bot Token

1. 在 Telegram 中搜索 @BotFather
2. 发送 `/newbot` 命令
3. 按照提示设置机器人名称和用户名
4. 你将获得一个 token，格式类似：`1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

#### 3. 获取 Session String

**方式 A：使用我们的自动脚本（推荐）**
```bash
python setup.py
```

**方式 B：手动生成**
1. 安装 Pyrogram：`pip install pyrogram tgcrypto`
2. 运行以下命令：
```python
python -c "from pyrogram import Client; app = Client('my_account', api_id=YOUR_API_ID, api_hash='YOUR_API_HASH'); app.start(); print(app.export_session_string())"
```
3. 输入手机号和验证码
4. 你将获得一个 session string

**方式 C：使用在线工具**
访问 https://replit.com/@bipinkrish/Generate-Pyrogram-String-Session 并按提示操作

### 常见问题

**Q: 机器人无法访问私有频道？**  
A: 确保你的会话字符串对应的账号已经加入了该频道，或者先发送频道的邀请链接给机器人。

**Q: 如何查看机器人日志？**  
A: 使用 `docker logs telegram-bot` 或 `docker-compose logs -f` 查看。

**Q: 机器人崩溃了怎么办？**  
A: 检查日志，确认配置正确，并确保你的 API 凭据有效。使用 `docker-compose restart` 重启机器人。

**Q: 如何更新机器人？**  
A: 拉取最新代码后，运行 `docker-compose down && docker-compose build --no-cache && docker-compose up -d`

### 许可证

请查看项目许可证文件。

### 免责声明

本项目仅供学习交流使用，使用者需遵守 Telegram 的服务条款和当地法律法规。
