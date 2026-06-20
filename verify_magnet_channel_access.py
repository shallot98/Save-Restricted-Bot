#!/usr/bin/env python3
"""
验证Bot是否能接收磁力频道的消息
"""
import sys
sys.path.insert(0, '.')

from src.core.container import get_watch_service

def verify_access():
    print("=" * 70)
    print("验证Bot对磁力频道的访问")
    print("=" * 70)

    ws = get_watch_service()
    ws._repository.reload()

    magnet_channel = '-1003202156769'

    # 检查是否在监控源列表
    monitored_sources = ws.get_monitored_sources()
    print(f"\n1. 磁力频道是否在监控列表: {magnet_channel in monitored_sources}")

    if magnet_channel not in monitored_sources:
        print("\n❌ 磁力频道不在监控列表中！")
        print("   原因可能是配置文件有问题")
        return False

    # 检查转发配置
    tasks = ws.get_tasks_for_source(magnet_channel)
    task_list = list(tasks)

    print(f"\n2. 找到 {len(task_list)} 个转发配置:")

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

        if not record_mode and dest == '7086222377':
            found_backup = True
            print(f"   ✅ 找到备份频道转发配置: {magnet_channel} → {dest}")
            print(f"      转发模式: {task_data.get('forward_mode', 'full')}")
            print(f"      提取规则: {task_data.get('extract_patterns', [])}")

    if not found_backup:
        print("\n   ❌ 没有找到到备份频道的转发配置！")
        return False

    print("\n" + "=" * 70)
    print("✅ 配置验证通过！")
    print("\n下一步：")
    print("1. 确保已将Bot添加为磁力频道管理员")
    print("2. 直接发送包含磁力链接的消息到磁力频道")
    print("3. 查看日志验证: docker logs -f save-restricted-bot-bot")
    print("=" * 70)

    return True

if __name__ == "__main__":
    verify_access()
