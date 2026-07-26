#!/usr/bin/env python3
"""
诊断磁力链接转发问题
分析配置和可能的问题
"""
import sys
sys.path.insert(0, '.')

from composition.container import get_watch_service
from bot.utils.peer import is_dest_cached

def analyze_config():
    """分析转发配置"""
    print("=" * 70)
    print("1. 分析磁力频道转发配置")
    print("=" * 70)

    ws = get_watch_service()
    ws._repository.reload()

    magnet_channel = '-1003202156769'
    backup_channel = '7086222377'

    # 检查磁力频道是否在监控列表
    monitored_sources = ws.get_monitored_sources()
    print(f"\n磁力频道 {magnet_channel} 是否在监控: {'✅ 是' if magnet_channel in monitored_sources else '❌ 否'}")

    if magnet_channel not in monitored_sources:
        print("\n❌ 问题: 磁力频道不在监控列表中！")
        return False

    # 获取转发配置
    tasks = ws.get_tasks_for_source(magnet_channel)
    task_list = list(tasks)

    print(f"\n找到 {len(task_list)} 个配置:")

    found_backup = False
    for entry in task_list:
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
        forward_mode = task_data.get('forward_mode', 'full')
        extract_patterns = task_data.get('extract_patterns', [])

        print(f"\n  配置 {watch_key}:")
        print(f"    用户: {user_id}")
        print(f"    目标: {dest}")
        print(f"    记录模式: {record_mode}")
        print(f"    转发模式: {forward_mode}")

        if extract_patterns:
            print(f"    提取规则: {extract_patterns}")

        if not record_mode and dest == backup_channel:
            found_backup = True
            print(f"    ✅ 这是到备份频道的转发配置")

    if not found_backup:
        print(f"\n❌ 问题: 没有找到到备份频道 {backup_channel} 的转发配置！")
        return False

    print(f"\n✅ 配置正常")
    return True

def check_peer_cache():
    """检查Peer缓存状态"""
    print("\n" + "=" * 70)
    print("2. 检查Peer缓存状态")
    print("=" * 70)

    backup_channel = '7086222377'
    cached = is_dest_cached(backup_channel)

    print(f"\n备份频道 {backup_channel} Peer缓存状态: {'✅ 已缓存' if cached else '❌ 未缓存'}")

    if not cached:
        print(f"\n⚠️ 问题: 备份频道Peer未缓存！")
        print(f"\n这会导致转发失败，因为Bot无法找到目标频道。")
        return False

    return True

def check_channel_id_format():
    """检查频道ID格式"""
    print("\n" + "=" * 70)
    print("3. 检查频道ID格式")
    print("=" * 70)

    backup_channel = '7086222377'
    backup_id = int(backup_channel)

    print(f"\n备份频道ID: {backup_channel}")
    print(f"ID类型: {'正数' if backup_id > 0 else '负数'}")

    if backup_id > 0:
        print(f"\n⚠️ 警告: 备份频道ID是正数！")
        print(f"\n在Telegram中:")
        print(f"  - 正数ID通常表示: 用户或Bot")
        print(f"  - 负数ID通常表示: 频道或群组")
        print(f"\n如果 {backup_channel} 是一个频道，正确的ID格式应该是:")
        print(f"  - 标准格式: -100{backup_channel}")
        print(f"  - 即: -1007086222377")
        print(f"\n💡 建议:")
        print(f"  1. 确认 {backup_channel} 是频道还是用户/Bot")
        print(f"  2. 如果是频道，请更新配置文件中的ID为 -1007086222377")
        print(f"  3. 如果是用户/Bot，请确保Bot已与该用户建立对话")
        return False
    else:
        print(f"\n✅ ID格式正常（频道/群组）")
        return True

def provide_solutions():
    """提供解决方案"""
    print("\n" + "=" * 70)
    print("解决方案")
    print("=" * 70)

    print("\n根据诊断结果，可能的问题和解决方法：")
    print("\n【问题1】备份频道ID格式错误")
    print("  症状: ID是正数 7086222377")
    print("  解决:")
    print("    1. 确认备份频道的真实ID")
    print("    2. 如果是频道，ID应该是 -1007086222377")
    print("    3. 更新配置文件: data/watch_config.json")
    print("    4. 重启Bot: docker-compose restart bot")

    print("\n【问题2】Peer缓存未初始化")
    print("  症状: Peer缓存状态显示'未缓存'")
    print("  解决:")
    print("    1. 确保Bot账号已加入备份频道")
    print("    2. 重启Bot以触发Peer缓存初始化")
    print("    3. 查看启动日志，确认Peer缓存成功")

    print("\n【问题3】Bot没有发送消息权限")
    print("  症状: 日志中显示权限错误")
    print("  解决:")
    print("    1. 确保Bot在备份频道中有发送消息权限")
    print("    2. 如果是私有频道，确保Bot是管理员")

    print("\n【调试步骤】")
    print("  1. 查看Bot日志:")
    print("     docker logs -f save-restricted-bot-bot")
    print("  2. 在磁力频道发送测试消息:")
    print("     magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678")
    print("  3. 观察日志中的转发过程和错误信息")

def main():
    print("开始诊断磁力链接转发问题\n")

    results = {
        'config': analyze_config(),
        'peer_cache': check_peer_cache(),
        'id_format': check_channel_id_format()
    }

    print("\n" + "=" * 70)
    print("诊断结果汇总")
    print("=" * 70)

    all_passed = all(results.values())

    for check, passed in results.items():
        status = "✅ 正常" if passed else "❌ 异常"
        print(f"  {check}: {status}")

    if all_passed:
        print("\n✅ 所有检查通过！")
        print("\n如果仍然无法转发，请:")
        print("  1. 查看Bot日志: docker logs -f save-restricted-bot-bot")
        print("  2. 在磁力频道发送测试消息")
        print("  3. 观察日志中的错误信息")
    else:
        provide_solutions()

    print("\n" + "=" * 70)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 诊断失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
