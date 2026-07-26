#!/usr/bin/env python3
"""
诊断磁力链接转发问题
检查Peer缓存、权限和实际转发流程
"""
import sys
import os
sys.path.insert(0, '.')

from pyrogram import Client
from src.core.config import settings
from composition.container import get_watch_service
from bot.utils.peer import is_dest_cached

def check_peer_cache():
    """检查备份频道的Peer缓存状态"""
    print("=" * 70)
    print("1. 检查Peer缓存状态")
    print("=" * 70)

    backup_channel = '7086222377'

    # 检查是否已缓存
    cached = is_dest_cached(backup_channel)
    print(f"\n备份频道 {backup_channel} Peer缓存状态: {'✅ 已缓存' if cached else '❌ 未缓存'}")

    if not cached:
        print("\n⚠️ 备份频道Peer未缓存，这可能导致转发失败！")
        print("   解决方法：")
        print("   1. 确保Bot已加入备份频道")
        print("   2. 重启Bot以触发Peer缓存")

    return cached

def check_bot_permissions():
    """检查Bot在备份频道的权限"""
    print("\n" + "=" * 70)
    print("2. 检查Bot权限")
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
            backup_channel = 7086222377

            try:
                # 尝试获取频道信息
                chat = acc.get_chat(backup_channel)
                print(f"\n✅ 成功获取备份频道信息:")
                print(f"   标题: {chat.title}")
                print(f"   类型: {chat.type}")
                print(f"   ID: {chat.id}")

                # 检查Bot是否是成员
                try:
                    member = acc.get_chat_member(backup_channel, "me")
                    print(f"\n✅ Bot是频道成员:")
                    print(f"   状态: {member.status}")

                    # 检查发送消息权限
                    if hasattr(chat, 'permissions'):
                        perms = chat.permissions
                        print(f"\n频道权限:")
                        print(f"   可以发送消息: {perms.can_send_messages if hasattr(perms, 'can_send_messages') else 'N/A'}")
                        print(f"   可以发送媒体: {perms.can_send_media_messages if hasattr(perms, 'can_send_media_messages') else 'N/A'}")

                    return True

                except Exception as e:
                    print(f"\n❌ 无法获取Bot成员信息: {e}")
                    print("   可能原因：Bot不是频道成员")
                    return False

            except Exception as e:
                print(f"\n❌ 无法访问备份频道: {e}")
                print("   可能原因：")
                print("   1. Bot未加入该频道")
                print("   2. 频道ID错误")
                print("   3. Bot没有访问权限")
                return False

    except Exception as e:
        print(f"\n❌ 创建客户端失败: {e}")
        return False

def test_send_message():
    """测试向备份频道发送消息"""
    print("\n" + "=" * 70)
    print("3. 测试发送消息")
    print("=" * 70)

    try:
        acc = Client(
            "user_session",
            api_id=settings.api_id,
            api_hash=settings.api_hash,
            session_string=settings.session_string,
            in_memory=True
        )

        with acc:
            backup_channel = 7086222377
            test_message = "🧪 测试消息 - 磁力链接转发诊断\nmagnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"

            try:
                sent = acc.send_message(backup_channel, test_message)
                print(f"\n✅ 成功发送测试消息到备份频道!")
                print(f"   消息ID: {sent.id}")
                print(f"   时间: {sent.date}")

                # 尝试删除测试消息
                try:
                    acc.delete_messages(backup_channel, sent.id)
                    print(f"   ✅ 已删除测试消息")
                except:
                    print(f"   ⚠️ 无法删除测试消息（可能需要手动删除）")

                return True

            except Exception as e:
                print(f"\n❌ 发送消息失败: {e}")
                print("   可能原因：")
                print("   1. Bot没有发送消息权限")
                print("   2. 频道设置了限制")
                return False

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False

def check_watch_config():
    """检查监控配置"""
    print("\n" + "=" * 70)
    print("4. 检查监控配置")
    print("=" * 70)

    ws = get_watch_service()
    ws._repository.reload()

    magnet_channel = '-1003202156769'
    backup_channel = '7086222377'

    tasks = ws.get_tasks_for_source(magnet_channel)

    found_forward = False
    for entry in tasks:
        if len(entry) == 3:
            user_id, watch_key, task = entry
        else:
            user_id, task = entry
            watch_key = magnet_channel

        if hasattr(task, 'to_dict'):
            task_data = task.to_dict()
        else:
            task_data = task

        dest = task_data.get('dest')
        record_mode = task_data.get('record_mode', False)

        if not record_mode and dest == backup_channel:
            found_forward = True
            print(f"\n✅ 找到转发配置:")
            print(f"   源频道: {magnet_channel}")
            print(f"   目标频道: {dest}")
            print(f"   转发模式: {task_data.get('forward_mode', 'full')}")
            print(f"   提取规则: {task_data.get('extract_patterns', [])}")
            print(f"   保留来源: {task_data.get('preserve_forward_source', False)}")

    if not found_forward:
        print(f"\n❌ 未找到从磁力频道到备份频道的转发配置!")

    return found_forward

def main():
    print("开始诊断磁力链接转发问题\n")

    results = {
        'peer_cache': check_peer_cache(),
        'permissions': check_bot_permissions(),
        'send_test': test_send_message(),
        'config': check_watch_config()
    }

    print("\n" + "=" * 70)
    print("诊断结果汇总")
    print("=" * 70)

    all_passed = all(results.values())

    for check, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{check}: {status}")

    if all_passed:
        print("\n✅ 所有检查通过！转发功能应该正常工作。")
        print("\n如果仍然无法转发，请检查：")
        print("1. Bot是否正在运行")
        print("2. 查看Bot日志: docker logs -f save-restricted-bot-bot")
        print("3. 在磁力频道发送测试消息并观察日志")
    else:
        print("\n❌ 发现问题！请根据上述检查结果修复。")

    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 诊断过程出错: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
