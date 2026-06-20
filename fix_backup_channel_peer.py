#!/usr/bin/env python3
"""
修复备份频道Peer缓存问题
手动缓存备份频道的Peer，确保转发功能正常
"""
import sys
import time
sys.path.insert(0, '.')

from pyrogram import Client
from src.core.config import settings
from bot.services.peer_cache import cache_peer_if_needed
from bot.utils.peer import is_dest_cached, mark_dest_cached

def fix_backup_channel_peer():
    """修复备份频道Peer缓存"""
    print("=" * 70)
    print("修复备份频道Peer缓存")
    print("=" * 70)

    backup_channel = '7086222377'

    # 检查当前缓存状态
    cached = is_dest_cached(backup_channel)
    print(f"\n1. 当前Peer缓存状态: {'✅ 已缓存' if cached else '❌ 未缓存'}")

    if cached:
        print("\n✅ 备份频道Peer已缓存，无需修复")
        return True

    print(f"\n2. 开始修复Peer缓存...")

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
            backup_id = int(backup_channel)

            # 方法1: 直接尝试get_chat
            print(f"\n   方法1: 尝试直接获取频道信息...")
            try:
                chat = acc.get_chat(backup_id)
                print(f"   ✅ 成功获取频道信息:")
                print(f"      标题: {chat.title if hasattr(chat, 'title') else chat.first_name}")
                print(f"      类型: {chat.type}")
                print(f"      ID: {chat.id}")

                mark_dest_cached(backup_channel)
                print(f"\n✅ Peer缓存成功！")
                return True

            except Exception as e:
                error_msg = str(e)
                print(f"   ❌ 方法1失败: {error_msg}")

                # 方法2: 通过对话列表查找
                if "PEER_ID_INVALID" in error_msg or "Peer id invalid" in error_msg:
                    print(f"\n   方法2: 尝试通过对话列表查找...")
                    try:
                        found = False
                        for dialog in acc.get_dialogs(limit=200):
                            if dialog.chat.id == backup_id:
                                chat_name = dialog.chat.title or dialog.chat.first_name or dialog.chat.username or 'Unknown'
                                print(f"   ✅ 在对话列表中找到: {chat_name}")
                                found = True

                                # 再次尝试get_chat
                                try:
                                    chat = acc.get_chat(backup_id)
                                    mark_dest_cached(backup_channel)
                                    print(f"   ✅ Peer缓存成功！")
                                    return True
                                except Exception as e2:
                                    print(f"   ⚠️ 获取chat信息失败: {e2}")
                                break

                        if not found:
                            print(f"   ❌ 在对话列表中未找到该频道")

                            # 方法3: 如果是正数ID（用户/Bot），尝试发送消息
                            if backup_id > 0:
                                print(f"\n   方法3: 检测到用户/Bot ID，尝试建立连接...")
                                try:
                                    # 尝试发送/start命令
                                    acc.send_message(backup_id, "/start")
                                    print(f"   ✅ 已发送/start命令")
                                    time.sleep(1)

                                    # 再次尝试get_chat
                                    chat = acc.get_chat(backup_id)
                                    chat_name = chat.first_name or chat.username or "Unknown"
                                    print(f"   ✅ 成功建立连接: {chat_name}")
                                    mark_dest_cached(backup_channel)
                                    print(f"\n✅ Peer缓存成功！")
                                    return True

                                except Exception as e3:
                                    print(f"   ❌ 方法3失败: {e3}")

                    except Exception as e_dialog:
                        print(f"   ❌ 对话列表查找失败: {e_dialog}")

                # 所有方法都失败
                print(f"\n❌ 所有方法都失败，无法缓存Peer")
                print(f"\n💡 可能的原因和解决方法：")
                print(f"   1. 如果 {backup_channel} 是私聊用户：")
                print(f"      - 让该用户向Bot发送一条消息")
                print(f"      - 或者Bot主动向该用户发送一条消息")
                print(f"   2. 如果 {backup_channel} 是Bot：")
                print(f"      - 确保Bot已启动且可访问")
                print(f"      - 手动向Bot发送/start命令")
                print(f"   3. 如果 {backup_channel} 是频道：")
                print(f"      - 频道ID应该是负数（如 -1007086222377）")
                print(f"      - 请检查配置文件中的频道ID是否正确")
                print(f"   4. 确保Bot账号已加入该频道/群组")
                return False

    except Exception as e:
        print(f"\n❌ 修复过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_fix():
    """验证修复结果"""
    print("\n" + "=" * 70)
    print("验证修复结果")
    print("=" * 70)

    backup_channel = '7086222377'
    cached = is_dest_cached(backup_channel)

    print(f"\n备份频道 {backup_channel} Peer缓存状态: {'✅ 已缓存' if cached else '❌ 未缓存'}")

    if cached:
        print("\n✅ 修复成功！现在可以正常转发消息了。")
        print("\n下一步：")
        print("1. 重启Bot: docker-compose restart bot")
        print("2. 在磁力频道发送测试消息")
        print("3. 查看日志验证: docker logs -f save-restricted-bot-bot")
    else:
        print("\n❌ 修复失败，请根据上述提示手动处理。")

    return cached

def main():
    print("开始修复备份频道Peer缓存问题\n")

    success = fix_backup_channel_peer()

    if success:
        verify_fix()

    print("\n" + "=" * 70)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 修复失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
