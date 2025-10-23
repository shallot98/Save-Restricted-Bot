# Save Restricted Bot - 完整部署教程

> 一个 Telegram 机器人，可以通过消息链接转发受限内容  
> 本教程包含从零开始的详细步骤，跟着操作即可完成部署

---

## 📋 目录

- [功能介绍](#功能介绍)
- [准备工作](#准备工作)
- [第一步：获取必要的凭据](#第一步获取必要的凭据)
  - [1.1 获取 API ID 和 API Hash](#11-获取-api-id-和-api-hash)
  - [1.2 获取 Bot Token](#12-获取-bot-token)
  - [1.3 获取 Session String](#13-获取-session-string可选)
- [第二步：安装必要软件](#第二步安装必要软件)
  - [Windows 系统](#windows-系统)
  - [macOS 系统](#macos-系统)
  - [Linux 系统](#linux-系统)
- [第三步：部署机器人](#第三步部署机器人)
  - [方法一：Docker Compose 部署（推荐，最简单）](#方法一docker-compose-部署推荐最简单)
  - [方法二：Docker 部署](#方法二docker-部署)
  - [方法三：本地 Python 部署](#方法三本地-python-部署)
  - [方法四：Heroku 部署](#方法四heroku-部署)
- [第四步：测试机器人](#第四步测试机器人)
- [使用教程](#使用教程)
- [常见问题解决](#常见问题解决)
- [维护操作](#维护操作)

---

## 功能介绍

✨ **主要功能：**
- 📥 转发 Telegram 频道/群组的受限内容（即使设置了"转发保护"）
- 🔓 支持公开频道、私有频道和机器人聊天
- 📦 批量下载多条消息（支持范围下载）
- 🎯 智能识别媒体类型（图片、视频、文档、音频等）
- ⚡ 实时显示下载/上传进度
- 🔄 自动重试失败的下载
- 👀 自动监控频道并转发新消息（/watch 功能）
- 🇨🇳 全中文界面和命令提示

---

## 准备工作

在开始之前，你需要准备：

- ✅ 一个 Telegram 账号（用于获取 API 凭据）
- ✅ 一个手机号（用于接收验证码）
- ✅ 一台能联网的电脑或服务器
- ✅ 大约 15-30 分钟的时间

**不需要编程经验，只需要按照步骤操作即可！**

---

## 第一步：获取必要的凭据

在部署机器人之前，我们需要获取 4 个重要的凭据。不用担心，下面会手把手教你如何获取。

### 1.1 获取 API ID 和 API Hash

**这是什么？** Telegram 提供的应用开发凭据，用于让你的机器人与 Telegram 服务器通信。

**详细步骤：**

1. **打开浏览器**，访问 Telegram 官方 API 页面：
   ```
   https://my.telegram.org
   ```

2. **登录你的 Telegram 账号**：
   - 在页面上输入你的手机号（带国家代码，例如：`+86 138xxxx8888`）
   - 点击 "Next"（下一步）
   
3. **输入验证码**：
   - Telegram 会发送一个验证码到你的 Telegram 客户端（手机或电脑版）
   - 在网页上输入这个验证码
   - 如果需要，还可能要求输入两步验证密码

4. **创建应用**：
   - 登录成功后，点击 "API development tools"（API 开发工具）
   - 如果是第一次使用，需要填写应用信息：
     - **App title（应用标题）**：随便填，例如 "My Bot"
     - **Short name（短名称）**：随便填，例如 "bot"
     - **Platform（平台）**：选择 "Other"
     - **Description（描述）**：可以不填
   - 点击 "Create application"（创建应用）

5. **保存凭据**：
   - 创建成功后，你会看到两个重要的值：
     - **App api_id**：一串数字，例如 `12345678`
     - **App api_hash**：一串字母和数字，例如 `0123456789abcdef0123456789abcdef`
   - **把这两个值复制保存到记事本**，后面会用到

   > 💡 **提示**：api_id 是纯数字，api_hash 是 32 位的字母数字组合

---

### 1.2 获取 Bot Token

**这是什么？** 你的机器人的唯一标识符，就像机器人的身份证。

**详细步骤：**

1. **打开 Telegram**（手机版或电脑版都可以）

2. **搜索 BotFather**：
   - 在搜索框输入 `@BotFather`
   - 点击官方的 BotFather（有蓝色认证标志✓）

3. **创建新机器人**：
   - 发送命令：`/newbot`
   - BotFather 会要求你输入机器人的名字

4. **设置机器人名称**：
   - **Display Name（显示名称）**：输入机器人的名字，可以用中文，例如 "我的转发助手"
   - 按回车发送

5. **设置机器人用户名**：
   - **Username（用户名）**：必须以 `bot` 结尾，只能用英文和数字，例如 `my_forward_bot`
   - 如果用户名已被占用，换一个再试
   - 按回车发送

6. **保存 Token**：
   - 创建成功后，BotFather 会发送一条消息，里面包含你的 **Bot Token**
   - Token 格式类似：`1234567890:ABCdefGHIjklMNOpqrsTUVwxyz-1234567`
   - **把这个 Token 复制保存到记事本**，后面会用到

   > 💡 **提示**：Token 由数字、冒号和字母组成，中间有一个冒号

7. **可选：关闭隐私模式（推荐）**：
   - 发送命令：`/setprivacy`
   - 选择你刚创建的机器人
   - 选择 "Disable"
   - 这样机器人可以读取群组消息

---

### 1.3 获取 Session String（可选）

**这是什么？** 你的 Telegram 用户账号的会话凭据，用于访问私有频道和受限内容。

**是否必需？**
- ❌ **如果只转发公开频道内容**：不需要，可以跳过这一步
- ✅ **如果需要转发私有频道或受限内容**：必须获取

**详细步骤：**

#### 方法 A：使用在线工具生成（最简单）

1. **访问 Replit 在线工具**：
   ```
   https://replit.com/@bipinkrish/Generate-Pyrogram-String-Session
   ```

2. **点击 "Run"（运行）**按钮（绿色的三角形）

3. **按提示输入信息**：
   - **API ID**：输入你在 1.1 步骤保存的 api_id
   - **API Hash**：输入你在 1.1 步骤保存的 api_hash
   - **Phone Number**：输入你的手机号（带国家代码，例如 `+8613800138000`）
   - 按回车

4. **输入验证码**：
   - Telegram 会发送验证码到你的手机
   - 在网页输入这个验证码

5. **输入两步验证密码**（如果有）：
   - 如果你的账号开启了两步验证，需要输入密码
   - 没有就直接按回车

6. **保存 Session String**：
   - 生成成功后，会显示一长串字符，这就是你的 Session String
   - **把这个字符串完整复制保存到记事本**，后面会用到

   > 💡 **提示**：Session String 是一长串看起来像乱码的字符，通常以 `1` 开头

#### 方法 B：使用本地脚本生成（更安全）

如果你不信任在线工具，可以在本地生成：

1. **安装 Python**（如果还没安装）：
   - 访问 https://www.python.org/downloads/
   - 下载并安装最新版本的 Python 3

2. **打开命令行**：
   - Windows：按 `Win + R`，输入 `cmd`，回车
   - macOS：打开 "终端"
   - Linux：打开 "Terminal"

3. **安装 Pyrogram**：
   ```bash
   pip install pyrogram tgcrypto
   ```

4. **下载生成脚本**：
   - 访问 https://gist.github.com/bipinkrish/0940b30ed66a5537ae1b5aaaee716897
   - 复制脚本内容，保存为 `generate_session.py`

5. **运行脚本**：
   ```bash
   python generate_session.py
   ```

6. **按照提示输入信息**（同方法 A 的步骤 3-6）

---

**✅ 凭据获取完成！**

现在你应该在记事本里保存了以下内容：
- ✅ API ID（一串数字）
- ✅ API Hash（32 位字母数字）
- ✅ Bot Token（带冒号的长字符串）
- ✅ Session String（可选，一长串字符）

接下来进入部署环节！

---

## 第二步：安装必要软件

根据你的操作系统选择对应的安装方式：

### Windows 系统

#### 安装 Docker Desktop

1. **下载 Docker Desktop**：
   - 访问：https://www.docker.com/products/docker-desktop/
   - 点击 "Download for Windows"

2. **安装 Docker Desktop**：
   - 双击下载的 `Docker Desktop Installer.exe`
   - 跟着安装向导一步步点击 "Next"
   - 安装完成后，点击 "Close and restart"（关闭并重启）

3. **启动 Docker Desktop**：
   - 电脑重启后，双击桌面上的 Docker Desktop 图标
   - 第一次启动可能需要几分钟，等待直到状态显示 "Docker Desktop is running"

4. **验证安装**：
   - 按 `Win + R`，输入 `cmd`，回车打开命令提示符
   - 输入以下命令并回车：
     ```bash
     docker --version
     ```
   - 如果显示版本号（如 `Docker version 24.0.x`），说明安装成功

#### 安装 Git

1. **下载 Git**：
   - 访问：https://git-scm.com/download/win
   - 下载会自动开始

2. **安装 Git**：
   - 双击下载的安装包
   - 一路点击 "Next"，使用默认设置即可
   - 安装完成后点击 "Finish"

3. **验证安装**：
   - 打开命令提示符（同上）
   - 输入：
     ```bash
     git --version
     ```
   - 如果显示版本号，说明安装成功

---

### macOS 系统

#### 安装 Docker Desktop

1. **下载 Docker Desktop**：
   - 访问：https://www.docker.com/products/docker-desktop/
   - 点击 "Download for Mac"
   - 根据你的 Mac 芯片选择：
     - Apple Silicon（M1/M2/M3）：选择 "Mac with Apple chip"
     - Intel：选择 "Mac with Intel chip"

2. **安装 Docker Desktop**：
   - 打开下载的 `.dmg` 文件
   - 将 Docker 图标拖到 Applications 文件夹
   - 打开 Applications，双击 Docker
   - 第一次打开需要输入密码授权

3. **启动 Docker Desktop**：
   - 等待 Docker 启动完成（菜单栏会出现 Docker 图标）
   - 图标变成静止状态说明启动完成

4. **验证安装**：
   - 打开 "终端"（Terminal）
   - 输入：
     ```bash
     docker --version
     ```
   - 如果显示版本号，说明安装成功

#### 安装 Git

macOS 通常自带 Git，验证一下：

1. **打开终端**
2. **输入**：
   ```bash
   git --version
   ```
3. **如果没有安装**，系统会提示安装 Xcode Command Line Tools，点击 "Install" 即可

---

### Linux 系统

#### 安装 Docker 和 Docker Compose

**Ubuntu/Debian 系统：**

```bash
# 更新包列表
sudo apt update

# 安装 Docker
sudo apt install -y docker.io docker-compose

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 将当前用户添加到 docker 组（避免每次都用 sudo）
sudo usermod -aG docker $USER

# 重新登录或运行（使用户组变更生效）
newgrp docker

# 验证安装
docker --version
docker-compose --version
```

**CentOS/RHEL 系统：**

```bash
# 安装 Docker
sudo yum install -y docker docker-compose

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 将当前用户添加到 docker 组
sudo usermod -aG docker $USER
newgrp docker

# 验证安装
docker --version
docker-compose --version
```

#### 安装 Git

```bash
# Ubuntu/Debian
sudo apt install -y git

# CentOS/RHEL
sudo yum install -y git

# 验证安装
git --version
```

---

**✅ 软件安装完成！**

确保以下命令都能正常显示版本号：
```bash
docker --version
docker-compose --version
git --version
```

---

## 第三步：部署机器人

选择一种部署方法，推荐使用**方法一：Docker Compose 部署**（最简单）。

---

### 方法一：Docker Compose 部署（推荐，最简单）

这是最简单的部署方式，只需要几个命令就能完成！

#### 步骤 1：下载项目代码

1. **打开命令行/终端**：
   - Windows：按 `Win + R`，输入 `cmd`，回车
   - macOS/Linux：打开 "终端"

2. **选择一个放置项目的位置**：
   ```bash
   # Windows 示例：进入 D 盘
   d:
   cd \
   
   # macOS/Linux 示例：进入家目录
   cd ~
   ```

3. **克隆项目代码**：
   ```bash
   git clone https://github.com/bipinkrish/Save-Restricted-Content-Bot-Repo.git
   ```
   
   > 💡 **注意**：如果上面的地址不对，请替换为实际的仓库地址

4. **进入项目目录**：
   ```bash
   cd Save-Restricted-Content-Bot-Repo
   ```

#### 步骤 2：配置凭据

1. **创建配置文件**：
   ```bash
   # Windows
   copy .env.example .env
   
   # macOS/Linux
   cp .env.example .env
   ```

2. **编辑配置文件**：
   
   **Windows：**
   ```bash
   notepad .env
   ```
   
   **macOS：**
   ```bash
   open -e .env
   ```
   
   **Linux：**
   ```bash
   nano .env
   ```

3. **填入你的凭据**：
   
   将文件内容修改为（替换为你在第一步保存的实际值）：
   ```env
   # Telegram Bot Configuration
   # Copy this file to .env and fill in your credentials
   
   # Your bot token from @BotFather
   TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz-1234567
   
   # Your API ID from my.telegram.org
   ID=12345678
   
   # Your API Hash from my.telegram.org
   HASH=0123456789abcdef0123456789abcdef
   
   # Your session string (optional, leave empty if not needed)
   STRING=你的session_string（如果不需要就删除这行或留空）
   ```
   
   > 💡 **重要提示**：
   > - `TOKEN` 后面跟你的 Bot Token
   > - `ID` 后面跟你的 API ID（纯数字，不需要引号）
   > - `HASH` 后面跟你的 API Hash
   > - `STRING` 后面跟你的 Session String（如果没有就留空或删除）
   > - **等号前后不要有空格！**

4. **保存文件**：
   - Windows Notepad：点击 "文件" → "保存"
   - macOS TextEdit：按 `Cmd + S`
   - Linux Nano：按 `Ctrl + O`（保存），然后按 `Ctrl + X`（退出）

#### 步骤 3：启动机器人

1. **一键启动**：
   ```bash
   docker-compose up -d
   ```
   
   这个命令会：
   - 自动下载所需的镜像
   - 构建机器人容器
   - 在后台启动机器人
   
   > 💡 **第一次运行会比较慢**（需要下载镜像），可能需要 3-5 分钟，请耐心等待

2. **等待启动完成**：
   
   当看到类似以下输出说明成功：
   ```
   Creating save-restricted-bot ... done
   ```

#### 步骤 4：查看运行状态

1. **查看容器状态**：
   ```bash
   docker-compose ps
   ```
   
   如果显示 "Up"，说明机器人正在运行

2. **查看日志**（确认是否正常启动）：
   ```bash
   docker-compose logs -f
   ```
   
   正常情况下，你会看到类似的输出：
   ```
   Bot started successfully
   Waiting for messages...
   ```
   
   按 `Ctrl + C` 可以退出日志查看（机器人会继续运行）

**🎉 恭喜！机器人已经成功启动！**

跳转到 [第四步：测试机器人](#第四步测试机器人) 验证是否正常工作。

---

### 方法二：Docker 部署

如果你不想使用 Docker Compose，也可以直接使用 Docker 命令。

#### 步骤 1：下载项目代码

```bash
# 选择位置
cd ~

# 克隆代码
git clone https://github.com/bipinkrish/Save-Restricted-Content-Bot-Repo.git

# 进入目录
cd Save-Restricted-Content-Bot-Repo
```

#### 步骤 2：构建镜像

```bash
docker build -t save-restricted-bot .
```

这个过程需要几分钟，耐心等待。

#### 步骤 3：运行容器

**方式 A：使用 config.json 文件**

1. **编辑配置文件**：
   ```bash
   # Windows
   notepad config.json
   
   # macOS
   open -e config.json
   
   # Linux
   nano config.json
   ```

2. **填入凭据**：
   ```json
   {
       "TOKEN": "你的Bot_Token",
       "ID": "你的API_ID",
       "HASH": "你的API_Hash",
       "STRING": "你的Session_String或null"
   }
   ```

3. **运行容器**：
   ```bash
   docker run -d --name telegram-bot -p 10000:10000 save-restricted-bot
   ```

**方式 B：使用环境变量**

直接在命令中指定凭据：

```bash
docker run -d --name telegram-bot \
  -e TOKEN="你的Bot_Token" \
  -e ID="你的API_ID" \
  -e HASH="你的API_Hash" \
  -e STRING="你的Session_String" \
  -p 10000:10000 \
  save-restricted-bot
```

> 💡 **提示**：Windows 用户需要去掉 `\` 并把所有内容写在一行

#### 步骤 4：查看状态

```bash
# 查看容器状态
docker ps

# 查看日志
docker logs -f telegram-bot
```

**🎉 部署完成！**

---

### 方法三：本地 Python 部署

如果你不想使用 Docker，可以直接在本地运行 Python 脚本。

#### 前置要求

- Python 3.7 或更高版本
- pip（Python 包管理器）

#### 步骤 1：安装 Python

**Windows：**
- 访问 https://www.python.org/downloads/
- 下载并安装最新版本
- **安装时勾选 "Add Python to PATH"**

**macOS：**
```bash
# 使用 Homebrew 安装
brew install python3
```

**Linux：**
```bash
# Ubuntu/Debian
sudo apt install python3 python3-pip

# CentOS/RHEL
sudo yum install python3 python3-pip
```

验证安装：
```bash
python3 --version
pip3 --version
```

#### 步骤 2：下载项目代码

```bash
# 克隆代码
git clone https://github.com/bipinkrish/Save-Restricted-Content-Bot-Repo.git

# 进入目录
cd Save-Restricted-Content-Bot-Repo
```

#### 步骤 3：安装依赖

```bash
pip3 install -r requirements.txt
```

或者手动安装：
```bash
pip3 install pyrogram tgcrypto flask
```

#### 步骤 4：配置凭据

编辑 `config.json`：

```bash
# Windows
notepad config.json

# macOS
open -e config.json

# Linux
nano config.json
```

填入你的凭据：
```json
{
    "TOKEN": "你的Bot_Token",
    "ID": "你的API_ID",
    "HASH": "你的API_Hash",
    "STRING": "你的Session_String或null"
}
```

#### 步骤 5：运行机器人

```bash
# 前台运行（会显示日志）
python3 main.py
```

或者后台运行（Linux/macOS）：
```bash
# 后台运行
nohup python3 main.py > bot.log 2>&1 &

# 查看日志
tail -f bot.log
```

**Windows 后台运行：**
```bash
start /B python main.py
```

#### 步骤 6：同时运行 Web 服务（可选）

另开一个终端窗口：
```bash
python3 app.py
```

**🎉 部署完成！**

---

### 方法四：Heroku 部署

如果你想部署到云端（免费/付费），可以使用 Heroku。

#### 步骤 1：注册 Heroku

1. 访问 https://www.heroku.com/
2. 点击 "Sign Up" 注册账号（免费）
3. 验证邮箱

#### 步骤 2：安装 Heroku CLI

**Windows：**
- 访问 https://devcenter.heroku.com/articles/heroku-cli
- 下载并安装 Heroku CLI

**macOS：**
```bash
brew tap heroku/brew && brew install heroku
```

**Linux：**
```bash
curl https://cli-assets.heroku.com/install.sh | sh
```

#### 步骤 3：登录 Heroku

```bash
heroku login
```

按任意键会打开浏览器，点击 "Log in" 完成登录。

#### 步骤 4：创建应用

```bash
# 进入项目目录
cd Save-Restricted-Content-Bot-Repo

# 创建 Heroku 应用（名字要唯一）
heroku create your-bot-name
```

#### 步骤 5：设置环境变量

```bash
heroku config:set TOKEN="你的Bot_Token"
heroku config:set ID="你的API_ID"
heroku config:set HASH="你的API_Hash"
heroku config:set STRING="你的Session_String"
```

#### 步骤 6：部署

```bash
# 添加 Git 远程仓库（如果还没添加）
git remote | grep heroku || heroku git:remote -a your-bot-name

# 提交代码（如果有修改）
git add .
git commit -m "Initial commit"

# 推送到 Heroku
git push heroku main
```

如果你的分支不是 `main`，使用：
```bash
git push heroku master
```

#### 步骤 7：启动机器人

```bash
# 启动一个 worker dyno
heroku ps:scale worker=1

# 查看日志
heroku logs --tail
```

#### 步骤 8：查看状态

```bash
# 查看应用状态
heroku ps

# 打开应用仪表板
heroku open
```

**🎉 Heroku 部署完成！**

> 💡 **注意**：Heroku 免费版有每月运行时长限制，如果需要 24/7 运行，可能需要升级到付费套餐。

---

## 第四步：测试机器人

现在机器人应该已经在运行了，让我们测试一下是否正常工作。

### 测试步骤

1. **打开 Telegram**（手机或电脑版）

2. **找到你的机器人**：
   - 搜索你在创建机器人时设置的用户名（例如 `@my_forward_bot`）
   - 或者点击 BotFather 发给你的机器人链接

3. **启动机器人**：
   - 点击 "START" 按钮
   - 或者发送 `/start` 命令

4. **查看欢迎消息**：
   
   如果一切正常，机器人会回复类似的消息：
   ```
   👋 欢迎使用内容转发机器人！
   
   📖 使用说明：
   - 发送 Telegram 消息链接，我会帮你转发内容
   - 支持公开频道、私有频道、机器人聊天
   - 支持批量下载多条消息
   
   💡 示例：
   https://t.me/channelname/123
   ```

5. **测试转发功能**：
   
   找一个公开频道的消息，复制链接发送给机器人。
   
   **如何获取消息链接：**
   - 在 Telegram 中打开任意公开频道
   - 右键点击某条消息
   - 选择 "Copy Link"（复制链接）或 "Copy Message Link"
   - 发送给你的机器人

6. **查看结果**：
   
   机器人应该会：
   - 显示 "正在处理..." 的进度消息
   - 下载该消息的内容
   - 转发给你（文字、图片、视频等）

**✅ 如果以上步骤都成功，说明机器人工作正常！**

### 如果机器人没有响应

检查以下几点：

1. **确认机器人在运行**：
   ```bash
   # Docker Compose
   docker-compose ps
   
   # Docker
   docker ps
   
   # 查看日志
   docker-compose logs -f
   # 或
   docker logs -f telegram-bot
   ```

2. **检查日志中是否有错误**：
   - 常见错误：`Invalid token`（Token 错误）
   - 常见错误：`API ID invalid`（API ID 错误）
   - 根据错误提示修复配置

3. **重启机器人**：
   ```bash
   # Docker Compose
   docker-compose restart
   
   # Docker
   docker restart telegram-bot
   ```

4. **查看 [常见问题解决](#常见问题解决) 部分**

---

## 使用教程

机器人支持多种使用场景，下面详细说明：

### 场景 1：转发公开频道内容

**最简单的用法，适合 90% 的场景。**

#### 操作步骤：

1. 找到你想转发的公开频道消息
2. 右键点击消息 → "Copy Link"（复制链接）
3. 把链接发送给机器人
4. 等待机器人转发内容

#### 示例：

**单条消息：**
```
https://t.me/durov/123
```
发送后，机器人会转发 ID 为 123 的那条消息。

**批量下载多条消息：**
```
https://t.me/durov/100-110
```
发送后，机器人会转发 ID 从 100 到 110 的所有消息（共 11 条）。

**带空格的格式也支持：**
```
https://t.me/durov/100 - 110
```

> 💡 **提示**：消息 ID 就是链接最后的数字

---

### 场景 2：转发私有频道内容

**需要 Session String 才能使用。**

私有频道的链接格式通常是：`https://t.me/c/1234567890/123`

#### 操作步骤：

**方式 A：如果你的账号已经加入该频道**

1. 直接发送消息链接给机器人
2. 机器人会自动转发内容

示例：
```
https://t.me/c/1234567890/123
```

**方式 B：如果你的账号还没加入该频道**

1. 先获取频道的邀请链接（例如 `https://t.me/+ABCdefGHIJ`）
2. 把邀请链接发送给机器人
3. 机器人会自动加入频道
4. 然后发送消息链接
5. 机器人转发内容

示例：
```
# 第一步：发送邀请链接
https://t.me/+ABCdefGHIJ

# 等待机器人回复 "已加入频道"

# 第二步：发送消息链接
https://t.me/c/1234567890/123
```

---

### 场景 3：转发机器人聊天内容

**特殊场景，需要特殊格式的链接。**

有些内容在机器人聊天中，链接格式需要包含 `/b/`。

#### 链接格式：

```
https://t.me/b/机器人用户名/消息ID
```

#### 示例：

```
https://t.me/b/testbot/4321
```

> 💡 **如何获取机器人消息的 ID？**
>
> 官方 Telegram 客户端不显示机器人消息 ID，你可能需要使用第三方客户端（如 Telegram X、Plus Messenger）来查看。

---

### 批量下载技巧

**格式：** `起始ID-结束ID` 或 `起始ID - 结束ID`（空格可选）

#### 示例：

**下载 10 条消息：**
```
https://t.me/durov/100-109
```

**下载 100 条消息：**
```
https://t.me/durov/1000-1099
```

**下载 1000 条消息：**
```
https://t.me/durov/1-1000
```

> ⚠️ **注意事项：**
> - 批量下载大量消息时，可能需要较长时间
> - Telegram API 有速率限制，下载太快可能会被临时限制
> - 建议一次不要超过 500 条消息
> - 机器人会显示实时进度

#### 进度显示示例：

```
📥 正在下载消息...
进度：23/100
已下载：23 条
剩余：77 条
预计时间：2 分钟
```

---

### 支持的媒体类型

机器人可以转发以下类型的内容：

- ✅ 纯文字消息
- ✅ 图片（Photo）
- ✅ 视频（Video）
- ✅ 文档（Document/File）
- ✅ 音频（Audio）
- ✅ 语音消息（Voice）
- ✅ 动图（Animation/GIF）
- ✅ 贴纸（Sticker）
- ✅ 投票（Poll）

> 💡 **媒体文件大小限制：**
> - Telegram Bot API 限制：最大 50 MB
> - 超过 50 MB 的文件可能无法转发
> - 建议使用原始链接直接下载大文件

---

### 场景 4：自动监控频道并转发（/watch 功能）

**🎯 新功能！监控频道/群组，自动将新消息转发到指定位置。**

**需要 Session String 才能使用。**

#### 功能说明：

使用 `/watch` 命令可以设置自动监控任务，一旦被监控的频道/群组有新消息，机器人会自动转发到你指定的目标位置。

#### 可用命令：

**1. 查看监控列表：**
```
/watch list
```
或直接发送：
```
/watch
```

**2. 添加监控任务：**
```
/watch add <来源频道> <目标位置>
```

**3. 删除监控任务：**
```
/watch remove <任务编号>
```

#### 使用示例：

**示例 1：监控频道并转发到另一个频道**
```
/watch add @source_channel @my_channel
```
这会监控 `@source_channel`，并将所有新消息自动转发到 `@my_channel`。

**示例 2：监控频道并保存到个人收藏**
```
/watch add @source_channel me
```
所有新消息会自动保存到你的 "Saved Messages"（个人收藏）。

**示例 3：使用频道 ID 监控（适用于私有频道）**
```
/watch add -1001234567890 @my_channel
```
使用频道的数字 ID 进行监控。

**示例 4：查看所有监控任务**
```
/watch list
```
返回示例：
```
📋 你的监控任务列表：

1. `-1001234567890` ➡️ `-1009876543210`
2. `-1001111111111` ➡️ `me`

总计：2 个监控任务
```

**示例 5：删除监控任务**
```
/watch remove 1
```
删除列表中的第 1 个监控任务。

#### 注意事项：

> ⚠️ **重要提示：**
> - 必须配置 Session String 才能使用此功能
> - 你的账号必须已加入被监控的频道/群组
> - 转发到频道时，你的账号必须是该频道的管理员
> - 使用 `me` 作为目标可以保存到个人收藏
> - 每个用户可以设置多个监控任务
> - 监控配置会自动保存，重启后依然有效
> - 只会转发新消息，不会转发历史消息

#### 如何获取频道 ID：

**方法 1：使用 Web 版 Telegram**
1. 在 Web 版打开频道：`https://web.telegram.org`
2. 查看浏览器地址栏，例如：`https://web.telegram.org/k/#-1001234567890`
3. 最后的数字就是频道 ID

**方法 2：转发消息查看**
1. 转发频道的任意消息到 @userinfobot
2. 机器人会显示频道的 ID

**方法 3：使用第三方客户端**
某些第三方客户端（如 Telegram X）可以直接显示频道 ID。

---

### 机器人命令列表

使用 `/help` 命令可以查看所有可用命令：

**基本命令：**
- `/start` - 启动机器人并查看使用说明
- `/help` - 显示帮助信息和命令列表
- `/watch` - 管理频道监控任务

**消息转发功能：**
直接发送 Telegram 消息链接即可

**监控功能：**
- `/watch list` - 查看所有监控任务
- `/watch add <来源> <目标>` - 添加监控任务
- `/watch remove <编号>` - 删除监控任务

---

## 常见问题解决

### ❓ 问题 1：机器人无响应

**症状：** 发送消息给机器人，没有任何回复。

**解决方法：**

1. **检查机器人是否在运行：**
   ```bash
   docker-compose ps
   ```
   
   如果状态不是 "Up"，尝试重启：
   ```bash
   docker-compose restart
   ```

2. **查看日志找到错误原因：**
   ```bash
   docker-compose logs -f
   ```

3. **确认配置文件正确：**
   - 检查 `.env` 文件中的 `TOKEN` 是否正确
   - 确保等号前后没有多余空格
   - Token 格式：`数字:字母数字-字母数字`

4. **重新部署：**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

---

### ❓ 问题 2：提示 "Invalid token"

**症状：** 日志中显示 `Invalid bot token` 或类似错误。

**原因：** Bot Token 填写错误。

**解决方法：**

1. **重新获取 Token：**
   - 打开 Telegram，找到 @BotFather
   - 发送 `/mybots`
   - 选择你的机器人
   - 选择 "API Token"
   - 复制新的 Token

2. **更新配置：**
   - 编辑 `.env` 文件
   - 替换 `TOKEN=` 后面的值
   - 确保完整复制，包括冒号和所有字符

3. **重启机器人：**
   ```bash
   docker-compose restart
   ```

---

### ❓ 问题 3：无法访问私有频道

**症状：** 发送私有频道链接后，机器人提示 "无法访问" 或 "找不到频道"。

**原因：**
- 没有配置 Session String
- Session String 对应的账号没有加入该频道

**解决方法：**

1. **确认已配置 Session String：**
   - 检查 `.env` 文件中 `STRING=` 是否有值
   - 如果没有，参考 [1.3 获取 Session String](#13-获取-session-string可选) 获取

2. **先发送频道邀请链接：**
   - 获取私有频道的邀请链接（格式：`https://t.me/+XXXXXXX`）
   - 发送给机器人
   - 等待机器人回复 "已加入频道"
   - 再发送消息链接

3. **确认账号已加入频道：**
   - 用 Session String 对应的账号手动加入该频道
   - 然后再发送链接给机器人

---

### ❓ 问题 4：提示 "API_ID_INVALID" 或 "API_HASH_INVALID"

**症状：** 日志中显示 API ID 或 API Hash 无效。

**解决方法：**

1. **重新获取 API 凭据：**
   - 访问 https://my.telegram.org
   - 登录后进入 "API development tools"
   - 复制正确的 `api_id` 和 `api_hash`

2. **检查配置格式：**
   - `ID` 应该是纯数字，不需要引号
   - `HASH` 应该是 32 位的字母数字组合，不需要引号
   
   正确示例：
   ```env
   ID=12345678
   HASH=0123456789abcdef0123456789abcdef
   ```
   
   错误示例：
   ```env
   ID="12345678"          # 不需要引号
   HASH=0123456789abc     # 长度不对
   ```

3. **重启机器人：**
   ```bash
   docker-compose restart
   ```

---

### ❓ 问题 5：机器人频繁崩溃

**症状：** 机器人运行一段时间后自动停止。

**解决方法：**

1. **查看完整日志：**
   ```bash
   docker-compose logs --tail=100
   ```

2. **常见崩溃原因：**
   
   **原因 A：内存不足**
   - 增加服务器内存
   - 或减少同时下载的文件数量

   **原因 B：网络问题**
   - 检查服务器网络连接
   - 如果在国内，可能需要代理

   **原因 C：Session String 失效**
   - 重新生成 Session String
   - 更新配置并重启

3. **设置自动重启：**
   
   Docker Compose 默认会自动重启，确保 `docker-compose.yml` 中有：
   ```yaml
   restart: unless-stopped
   ```

---

### ❓ 问题 6：下载速度慢

**症状：** 下载大文件或批量消息时速度很慢。

**解决方法：**

1. **这是正常现象：**
   - Telegram API 有速率限制
   - 避免被封禁，机器人会控制下载速度

2. **优化建议：**
   - 避免一次下载太多消息（建议单次不超过 100 条）
   - 大文件下载需要时间，请耐心等待
   - 如果服务器在国内，速度可能较慢

3. **查看实时进度：**
   
   机器人会显示下载进度，例如：
   ```
   📥 正在下载：5/50
   ⏱️ 预计剩余时间：3 分钟
   ```

---

### ❓ 问题 7：端口被占用

**症状：** 启动时提示 "port 10000 is already in use"（端口已被占用）。

**解决方法：**

**方式 A：更换端口**

编辑 `docker-compose.yml`：
```yaml
ports:
  - "8080:10000"  # 改为其他端口，如 8080
```

然后重启：
```bash
docker-compose down
docker-compose up -d
```

**方式 B：停止占用端口的程序**

查找占用端口的程序：

```bash
# Linux/macOS
lsof -i :10000

# Windows
netstat -ano | findstr :10000
```

然后停止该程序，再启动机器人。

---

### ❓ 问题 8：Session String 获取失败

**症状：** 运行生成脚本时报错或无法生成。

**解决方法：**

**错误 A："Phone number invalid"**
- 检查手机号格式是否正确（需要带国家代码，如 `+8613800138000`）
- 确保手机号已注册 Telegram

**错误 B："API_ID_INVALID"**
- 检查输入的 API ID 是否正确
- 重新从 https://my.telegram.org 获取

**错误 C："Two-step verification enabled"**
- 输入你的两步验证密码
- 如果忘记密码，需要先重置

**错误 D："Flood wait"**
- 请求过于频繁，等待几分钟后重试
- 或者等待提示的时间（如 "Flood wait: 3600 seconds"）

---

### ❓ 问题 9：无法下载某些文件

**症状：** 机器人提示 "无法下载此文件" 或下载失败。

**原因：**
- 文件过大（超过 50 MB）
- 文件已被删除
- 文件类型不支持

**解决方法：**

1. **检查文件大小：**
   - Telegram Bot API 限制最大 50 MB
   - 超过限制的文件无法通过 Bot 转发

2. **使用用户账号下载：**
   - 确保配置了 Session String
   - 用户账号下载限制更宽松

3. **直接保存原始链接：**
   - 如果是视频或文档，考虑直接保存链接
   - 然后手动下载

---

### ❓ 问题 10：Docker 命令权限错误

**症状（Linux）：** 运行 Docker 命令时提示 "permission denied"。

**解决方法：**

```bash
# 方法 1：将用户添加到 docker 组
sudo usermod -aG docker $USER

# 重新登录或运行
newgrp docker

# 方法 2：使用 sudo（临时）
sudo docker-compose up -d
```

---

### 🆘 还是解决不了？

如果以上方法都无法解决你的问题：

1. **查看完整日志：**
   ```bash
   docker-compose logs --tail=200 > bot-error.log
   ```

2. **收集以下信息：**
   - 操作系统及版本
   - Docker 版本（`docker --version`）
   - 完整错误日志（去除敏感信息）
   - 配置文件内容（隐藏 Token 等敏感信息）

3. **寻求帮助：**
   - 在项目 Issues 页面提交问题
   - 附上上述信息
   - 详细描述问题和已尝试的解决方法

---

## 维护操作

### 查看日志

**实时查看日志：**
```bash
# Docker Compose
docker-compose logs -f

# Docker
docker logs -f telegram-bot

# 只看最后 100 行
docker-compose logs --tail=100
```

**保存日志到文件：**
```bash
docker-compose logs > bot.log
```

---

### 重启机器人

**正常重启：**
```bash
# Docker Compose
docker-compose restart

# Docker
docker restart telegram-bot
```

**完全重启（重新构建）：**
```bash
docker-compose down
docker-compose up -d --build
```

---

### 停止机器人

**临时停止：**
```bash
# Docker Compose
docker-compose stop

# Docker
docker stop telegram-bot
```

**完全停止并删除容器：**
```bash
# Docker Compose
docker-compose down

# Docker
docker stop telegram-bot
docker rm telegram-bot
```

---

### 更新机器人

当项目有新版本时，按以下步骤更新：

```bash
# 1. 进入项目目录
cd Save-Restricted-Content-Bot-Repo

# 2. 停止机器人
docker-compose down

# 3. 拉取最新代码
git pull

# 4. 重新构建镜像
docker-compose build --no-cache

# 5. 启动机器人
docker-compose up -d

# 6. 查看日志确认正常
docker-compose logs -f
```

---

### 备份配置

定期备份你的配置文件：

```bash
# 备份 .env 文件
cp .env .env.backup

# 备份 config.json（如果使用）
cp config.json config.json.backup

# 备份到其他位置
cp .env ~/backup/.env.backup-$(date +%Y%m%d)
```

---

### 修改配置

如果需要修改配置（如更换 Token）：

```bash
# 1. 编辑配置文件
nano .env

# 2. 修改需要的内容

# 3. 保存并重启机器人
docker-compose restart

# 4. 查看日志确认新配置生效
docker-compose logs -f
```

---

### 清理旧数据

**清理 Docker 缓存：**
```bash
# 清理未使用的镜像
docker image prune -a

# 清理所有未使用的资源
docker system prune -a
```

**清理下载的临时文件：**
```bash
# 进入容器
docker-compose exec telegram-bot sh

# 清理临时文件
rm -rf /tmp/*

# 退出容器
exit
```

---

### 迁移到新服务器

如果需要将机器人迁移到新服务器：

```bash
# === 在旧服务器上 ===

# 1. 备份配置
tar -czf bot-backup.tar.gz .env docker-compose.yml

# 2. 下载备份到本地
scp user@old-server:/path/to/bot-backup.tar.gz ~/

# === 在新服务器上 ===

# 1. 安装 Docker（参考前面的安装步骤）

# 2. 克隆项目
git clone <repository-url>
cd <project-directory>

# 3. 上传备份
scp ~/bot-backup.tar.gz user@new-server:/path/to/project/

# 4. 解压配置
tar -xzf bot-backup.tar.gz

# 5. 启动机器人
docker-compose up -d
```

---

### 性能监控

**查看资源使用情况：**
```bash
# 查看容器资源占用
docker stats telegram-bot

# 查看磁盘使用
docker-compose exec telegram-bot df -h

# 查看内存使用
docker-compose exec telegram-bot free -h
```

---

## 高级技巧

### 自定义端口

编辑 `docker-compose.yml`：
```yaml
ports:
  - "自定义端口:10000"
```

例如改为 8080：
```yaml
ports:
  - "8080:10000"
```

---

### 使用代理（适用于网络受限地区）

如果你的服务器访问 Telegram 需要代理，编辑代码或使用环境变量。

**方法 1：修改 Docker Compose**

编辑 `docker-compose.yml`，添加代理环境变量：
```yaml
environment:
  - TOKEN=${TOKEN}
  - ID=${ID}
  - HASH=${HASH}
  - STRING=${STRING}
  - HTTP_PROXY=http://proxy-server:port
  - HTTPS_PROXY=http://proxy-server:port
```

**方法 2：系统级代理**

在运行 Docker 之前设置代理：
```bash
export HTTP_PROXY=http://proxy-server:port
export HTTPS_PROXY=http://proxy-server:port
docker-compose up -d
```

---

### 多机器人实例

如果需要运行多个机器人：

```bash
# 1. 复制项目目录
cp -r Save-Restricted-Content-Bot-Repo Bot2

# 2. 进入新目录
cd Bot2

# 3. 修改 docker-compose.yml 中的容器名和端口
nano docker-compose.yml

# 修改为：
services:
  telegram-bot:
    container_name: save-restricted-bot-2
    ports:
      - "10001:10000"  # 改为不同端口

# 4. 创建新的 .env 文件，填入不同的 Token
nano .env

# 5. 启动第二个机器人
docker-compose up -d
```

---

### 设置定时重启

**使用 cron（Linux）：**

```bash
# 编辑 crontab
crontab -e

# 添加定时重启（每天凌晨 3 点重启）
0 3 * * * cd /path/to/project && docker-compose restart
```

---

## 安全建议

### 保护你的凭据

- ✅ **不要**将 `.env` 或 `config.json` 提交到 Git
- ✅ **不要**在公共场合分享你的 Token 和 Session String
- ✅ **定期**更换 Bot Token（通过 @BotFather）
- ✅ **使用**强密码保护你的服务器
- ✅ **启用**两步验证保护你的 Telegram 账号

### Session String 安全

- ⚠️ Session String 等同于你的账号登录凭据
- ⚠️ 如果泄露，他人可以完全控制你的账号
- ⚠️ 不要在不信任的机器上生成 Session String
- ✅ 定期重新生成 Session String
- ✅ 如果怀疑泄露，立即在 Telegram 设置中终止所有会话

**如何终止会话：**
1. 打开 Telegram
2. 设置 → 隐私和安全 → 活动会话
3. 点击 "终止所有其他会话"

---

## 许可证与免责声明

### 开源许可证

本项目采用 [MIT License]（或查看项目 LICENSE 文件）。

### 免责声明

- ⚠️ 本项目仅供学习和研究使用
- ⚠️ 使用者应遵守 Telegram 服务条款和当地法律法规
- ⚠️ 不得用于侵犯他人版权或隐私
- ⚠️ 开发者不对使用本项目造成的任何后果负责
- ⚠️ 转发内容时请尊重原作者的知识产权

### Telegram 服务条款

使用本机器人时，请遵守 Telegram 的使用条款：
https://telegram.org/tos

特别注意：
- 不要发送垃圾信息
- 不要滥用 API（频繁请求可能导致封禁）
- 不要侵犯他人隐私和版权

---

## 结语

🎉 **恭喜你完成了机器人的部署！**

如果你在使用过程中遇到任何问题，请参考 [常见问题解决](#常见问题解决) 部分。

如果本教程对你有帮助，欢迎给项目点个 Star ⭐！

**祝你使用愉快！**

---

## 快速参考

### 常用命令速查

```bash
# === Docker Compose ===

# 启动
docker-compose up -d

# 停止
docker-compose down

# 重启
docker-compose restart

# 查看日志
docker-compose logs -f

# 查看状态
docker-compose ps

# 更新
git pull && docker-compose down && docker-compose build --no-cache && docker-compose up -d

# === Docker ===

# 查看所有容器
docker ps -a

# 查看日志
docker logs -f telegram-bot

# 重启
docker restart telegram-bot

# 停止
docker stop telegram-bot

# 删除
docker rm telegram-bot

# === 系统 ===

# 查看 Docker 版本
docker --version

# 查看资源使用
docker stats

# 清理未使用资源
docker system prune -a
```

---

## 更新日志

### 最新版本

- ✨ 支持批量下载多条消息
- ✨ 实时显示下载进度
- 🐛 修复私有频道访问问题
- 🔧 优化下载速度和稳定性

---

**📖 本文档最后更新：2024 年**

如有任何疑问或建议，欢迎在 GitHub Issues 中反馈！
