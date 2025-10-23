# Save Restricted Bot

*一个 Telegram 机器人，可以通过消息链接发送受限内容*

## 功能特性

- 转发 Telegram 频道/群组的受限内容
- 支持公开、私有和机器人聊天
- 批量下载多条消息
- 智能识别媒体类型并转发
- 实时显示下载/上传进度

## 配置变量

- `HASH` 你的 API Hash，从 my.telegram.org 获取
- `ID` 你的 API ID，从 my.telegram.org 获取
- `TOKEN` 你的机器人 token，从 @BotFather 获取
- `STRING` 你的会话字符串，可以通过运行 [这个脚本](https://gist.github.com/bipinkrish/0940b30ed66a5537ae1b5aaaee716897#file-main-py) 在本地获取

## 使用说明

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

## 部署教程

### 方法一：使用 Docker 部署

1. 克隆仓库：
```bash
git clone <仓库地址>
cd <仓库目录>
```

2. 编辑 `config.json` 文件，填入你的凭据：
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

### 方法二：使用 Docker Compose 部署（推荐）

1. 克隆仓库：
```bash
git clone <仓库地址>
cd <仓库目录>
```

2. 创建 `.env` 文件（可以从 `.env.example` 复制）：
```bash
cp .env.example .env
```

3. 编辑 `.env` 文件，填入你的凭据：
```env
TOKEN=你的机器人token
ID=你的API ID
HASH=你的API Hash
STRING=你的会话字符串
```

4. 启动机器人：
```bash
docker-compose up -d
```

5. 查看日志：
```bash
docker-compose logs -f
```

6. 停止机器人：
```bash
docker-compose down
```

7. 重启机器人：
```bash
docker-compose restart
```

8. 更新机器人（拉取最新代码后）：
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### 方法三：Heroku 部署

使用包含的 `Procfile` 文件进行 Heroku 部署。在 Heroku 控制面板中设置环境变量即可。

## 获取必要的凭据

### 1. 获取 API ID 和 API Hash

1. 访问 https://my.telegram.org
2. 使用你的手机号登录
3. 点击 "API development tools"
4. 填写应用信息（如果是第一次）
5. 你将获得 `api_id` 和 `api_hash`

### 2. 获取 Bot Token

1. 在 Telegram 中搜索 @BotFather
2. 发送 `/newbot` 命令
3. 按照提示设置机器人名称和用户名
4. 你将获得一个 token，格式类似：`1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

### 3. 获取 Session String

1. 下载会话生成脚本：https://gist.github.com/bipinkrish/0940b30ed66a5537ae1b5aaaee716897#file-main-py
2. 安装 Pyrogram：`pip install pyrogram`
3. 运行脚本并输入你的 API ID、API Hash 和手机号
4. 输入收到的验证码
5. 你将获得一个 session string

## 常见问题

**Q: 机器人无法访问私有频道？**  
A: 确保你的会话字符串对应的账号已经加入了该频道，或者先发送频道的邀请链接给机器人。

**Q: 如何查看机器人日志？**  
A: 使用 `docker logs telegram-bot` 或 `docker-compose logs -f` 查看。

**Q: 机器人崩溃了怎么办？**  
A: 检查日志，确认配置正确，并确保你的 API 凭据有效。使用 `docker-compose restart` 重启机器人。

**Q: 如何更新机器人？**  
A: 拉取最新代码后，运行 `docker-compose down && docker-compose build --no-cache && docker-compose up -d`

**Q: 端口 10000 被占用怎么办？**  
A: 修改 `docker-compose.yml` 中的端口映射，例如改为 `"8080:10000"`

**Q: 需要 Session String 吗？**  
A: 如果只转发公开频道的内容，不需要。如果需要访问私有频道或受限内容，则必须提供。

## 许可证

请查看项目许可证文件。

## 免责声明

本项目仅供学习交流使用，使用者需遵守 Telegram 的服务条款和当地法律法规。
