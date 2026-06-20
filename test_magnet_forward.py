#!/usr/bin/env python3
"""
测试磁力链接转发功能
验证从磁力频道到备份频道的转发是否正常
"""

import sys
import re
sys.path.insert(0, '.')

from src.core.container import get_watch_service
from bot.filters.extract import extract_content

def test_magnet_extraction():
    """测试磁力链接提取功能"""
    print("=" * 70)
    print("测试1: 磁力链接提取功能")
    print("=" * 70)

    # 测试消息示例
    test_messages = [
        "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678",
        "下载链接：magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=test",
        "这是一条测试消息",
        "magnet:?xt=urn:btih:ABCD1234\nmagnet:?xt=urn:btih:EFGH5678",
    ]

    extract_pattern = r"magnet:\?xt=urn:btih:[^\r\n]+"

    for i, msg in enumerate(test_messages, 1):
        print(f"\n消息 {i}: {msg[:50]}...")
        extracted = extract_content(msg, [extract_pattern])
        if extracted:
            print(f"  ✅ 提取成功: {extracted[:100]}")
        else:
            print(f"  ❌ 提取失败")

    return True

def test_forward_config():
    """测试磁力频道的转发配置"""
    print("\n" + "=" * 70)
    print("测试2: 磁力频道转发配置")
    print("=" * 70)

    ws = get_watch_service()
    ws._repository.reload()

    source = '-1003202156769'

    # 检查是否在监控源列表
    monitored_sources = ws.get_monitored_sources()
    print(f"\n1. 磁力频道 {source} 是否在监控: {source in monitored_sources}")

    # 获取配置
    tasks = ws.get_tasks_for_source(source)
    print(f"\n2. 找到 {len(list(tasks))} 个配置:")

    tasks = ws.get_tasks_for_source(source)  # 重新获取（迭代器）
    for entry in tasks:
        if len(entry) == 3:
            user_id, watch_key, task = entry
        else:
            user_id, task = entry
            watch_key = source

        if hasattr(task, 'to_dict'):
            task_data = task.to_dict()
        else:
            task_data = task

        dest = task_data.get('dest')
        record_mode = task_data.get('record_mode', False)
        forward_mode = task_data.get('forward_mode', 'full')
        extract_patterns = task_data.get('extract_patterns', [])

        print(f"\n  配置: {watch_key}")
        print(f"    用户: {user_id}")
        print(f"    目标: {dest}")
        print(f"    记录模式: {record_mode}")
        print(f"    转发模式: {forward_mode}")
        if extract_patterns:
            print(f"    提取模式: {extract_patterns}")

    return True

def test_filter_check():
    """测试过滤规则"""
    print("\n" + "=" * 70)
    print("测试3: 过滤规则检查")
    print("=" * 70)

    from src.domain.services.filter_service import FilterService
    from src.domain.entities.watch import WatchTask

    ws = get_watch_service()
    ws._repository.reload()

    source = '-1003202156769'
    tasks = ws.get_tasks_for_source(source)

    test_message = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"

    print(f"\n测试消息: {test_message}")

    for entry in tasks:
        if len(entry) == 3:
            user_id, watch_key, task = entry
        else:
            user_id, task = entry
            watch_key = source

        if hasattr(task, 'to_dict'):
            task_data = task.to_dict()
        else:
            task_data = task

        # 创建WatchTask对象
        watch_task = WatchTask(
            source=str(task_data.get('source') or ''),
            dest=task_data.get('dest'),
            whitelist=task_data.get('whitelist', []),
            blacklist=task_data.get('blacklist', []),
            whitelist_regex=task_data.get('whitelist_regex', []),
            blacklist_regex=task_data.get('blacklist_regex', []),
            preserve_forward_source=bool(task_data.get('preserve_forward_source', False)),
            forward_mode=task_data.get('forward_mode', 'full'),
            extract_patterns=task_data.get('extract_patterns', []),
            record_mode=bool(task_data.get('record_mode', False)),
        )

        should_forward = FilterService.should_forward(watch_task, test_message)

        dest = task_data.get('dest')
        record_mode = task_data.get('record_mode', False)
        mode = '记录' if record_mode else f'转发到 {dest}'

        print(f"\n  配置: {mode}")
        print(f"    过滤结果: {'✅ 通过' if should_forward else '❌ 不通过'}")

    return True

if __name__ == "__main__":
    try:
        print("开始测试磁力链接转发功能\n")

        # 运行所有测试
        test_magnet_extraction()
        test_forward_config()
        test_filter_check()

        print("\n" + "=" * 70)
        print("✅ 所有测试完成")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
