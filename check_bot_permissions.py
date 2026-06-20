#!/usr/bin/env python3
"""
检查Bot在各个频道的权限状态
"""
import sys
import asyncio
sys.path.insert(0, '.')

from pyrogram import Client
from bot.config import API_ID, API_HASH, SESSION_STRING

async def check_channel_permissions():
    """检查Bot在关键频道的权限"""

    async with Client(
        "check_permissions",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING
    ) as app:

        channels = {
            "-1002203159247": "源频道",
            "-1003202156769": "磁力频道",
            "-1003407587019": "普通目标频道"
        }

        print("=" * 70)
        print("检查Bot在各频道的权限")
        print("=" * 70)

        for chat_id, name in channels.items():
            try:
                chat = await app.get_chat(int(chat_id))
                print(f"\n📢 {name} ({chat_id})")
                print(f"   名称: {chat.title}")
                print(f"   类型: {chat.type}")

                # 检查Bot的权限
                try:
                    me = await app.get_chat_member(int(chat_id), "me")
                    print(f"   Bot状态: {me.status}")

                    if me.status == "administrator":
                        privileges = me.privileges
                        print(f"   管理员权限:")
                        if privileges:
                            print(f"     - 发送消息: {privileges.can_post_messages if hasattr(privileges, 'can_post_messages') else 'N/A'}")
                            print(f"     - 编辑消息: {privileges.can_edit_messages if hasattr(privileges, 'can_edit_messages') else 'N/A'}")
                            print(f"     - 删除消息: {privileges.can_delete_messages if hasattr(privileges, 'can_delete_messages') else 'N/A'}")
                    else:
                        print(f"   ⚠️ Bot不是管理员，无法接收频道的incoming消息")

                except Exception as e:
                    print(f"   ❌ 无法获取Bot成员信息: {e}")

            except Exception as e:
                print(f"\n❌ {name} ({chat_id})")
                print(f"   错误: {e}")

        print("\n" + "=" * 70)

if __name__ == "__main__":
    asyncio.run(check_channel_permissions())
