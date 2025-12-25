"""
Message Constants
=================

User-facing message templates.
"""


class Messages:
    """User-facing message templates"""

    USAGE = """**📌 公开频道/群组**

__直接发送帖子链接即可__

**🔒 私有频道/群组**

__首先发送频道邀请链接（如果 String Session 账号已加入则不需要）
然后发送帖子链接__

**🤖 机器人聊天**

__发送带有 '/b/'、机器人用户名和消息 ID 的链接，你可能需要使用一些非官方客户端来获取 ID，如下所示__

```
https://t.me/b/botusername/4321
```

**📦 批量下载**

__按照上述方式发送公开/私有帖子链接，使用 "from - to" 格式发送多条消息，如下所示__

```
https://t.me/xxxx/1001-1010

https://t.me/c/xxxx/101 - 120
```

__注意：中间的空格无关紧要__
"""

    # Error messages
    ERROR_UNAUTHORIZED = "❌ 未授权访问"
    ERROR_NOT_FOUND = "❌ 未找到资源"
    ERROR_INTERNAL = "❌ 内部错误，请稍后重试"

    # Success messages
    SUCCESS_SAVED = "✅ 保存成功"
    SUCCESS_DELETED = "✅ 删除成功"
    SUCCESS_UPDATED = "✅ 更新成功"

    # Status messages
    STATUS_LOADING = "⏳ 加载中..."
    STATUS_PROCESSING = "⏳ 处理中..."
