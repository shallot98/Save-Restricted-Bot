#!/usr/bin/env python3
"""
检查备份频道的真实ID
确定 7086222377 是频道、用户还是Bot
"""
import sys
sys.path.insert(0, '.')

from pyrogram import Client
from src.core.config import settings

def check_channel_id():
    """检查备份频道的真实ID"""
    print("=" * 70)
    print("检查备份频道ID")
    print("=" * 70)

    try:
        # 创建客户端
        acc = Client(
            "user_session",
            api_id=settings.api_id,
            api_hash=settings.api_hash,
            session_string=settings.session_string,
            in_memory=True
        )

        with acc:
            # 测试不同的ID格式
            test_ids = [
                7086222377,           # 正数（用户/Bot）
                -7086222377,          # 负数（可能的频道）
                -1007086222377,       # 标准频道ID格式
            ]

            print("\n尝试不同的ID格式:\n")

            for test_id in test_ids:
                print(f"测试ID: {test_id}")
                try:
                    chat = acc.get_chat(test_id)
                    print(f"  ✅ 成功获取信息:")
                    print(f"     类型: {chat.type}")
                    print(f"     标题: {chat.title if hasattr(chat, 'title') else chat.first_name}")
                    print(f"     ID: {chat.id}")
                    print(f"     用户名: @{chat.username}" if hasattr(chat, 'username') and chat.username else "     用户名: 无")

                    if hasattr(chat, 'is_bot'):
                        print(f"     是Bot: {chat.is_bot}")

                    print()

                    # 如果成功，这就是正确的ID
                    if chat.type in ['channel', 'supergroup']:
                        print(f"  💡 这是一个频道/超级群组，正确的ID是: {chat.id}")
                        return chat.id
                    elif hasattr(chat, 'is_bot') and chat.is_bot:
                        print(f"  💡 这是一个Bot，ID是: {chat.id}")
                        return chat.id
                    else:
                        print(f"  💡 这是一个用户，ID是: {chat.id}")
                        return chat.id

                except Exception as e:
                    print(f"  ❌ 失败: {e}\n")

            # 如果所有ID都失败，尝试搜索对话列表
            print("\n尝试在对话列表中搜索包含'备份'或'magnet'的频道:\n")

            found_channels = []
            for dialog in acc.get_dialogs(limit=100):
                chat = dialog.chat
                title = chat.title if hasattr(chat, 'title') else chat.first_name or ""

                if any(keyword in title.lower() for keyword in ['备份', 'backup', 'magnet', '磁力']):
                    print(f"找到可能的频道:")
                    print(f"  标题: {title}")
                    print(f"  类型: {chat.type}")
                    print(f"  ID: {chat.id}")
                    print(f"  用户名: @{chat.username}" if hasattr(chat, 'username') and chat.username else "  用户名: 无")
                    print()
                    found_channels.append((title, chat.id, chat.type))

            if found_channels:
                print(f"\n💡 找到 {len(found_channels)} 个可能的频道")
                print("请确认哪个是磁力备份频道，并使用其ID更新配置")
            else:
                print("\n❌ 未找到相关频道")
                print("\n💡 请确认:")
                print("   1. Bot账号是否已加入磁力备份频道")
                print("   2. 频道名称是否包含'备份'、'backup'、'magnet'等关键词")

    except Exception as e:
        print(f"\n❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("开始检查备份频道ID\n")

    correct_id = check_channel_id()

    if correct_id:
        print("\n" + "=" * 70)
        print("检查完成")
        print("=" * 70)
        print(f"\n✅ 正确的频道ID: {correct_id}")
        print(f"\n下一步:")
        print(f"1. 如果ID不是 7086222377，请更新配置文件")
        print(f"2. 重启Bot: docker-compose restart bot")
        print(f"3. 测试转发功能")
    else:
        print("\n" + "=" * 70)
        print("检查失败")
        print("=" * 70)
        print("\n请手动确认磁力备份频道的ID")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 执行失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
