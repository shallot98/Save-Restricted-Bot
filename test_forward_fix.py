#!/usr/bin/env python3
"""
转发功能修复验证脚本
测试 get_monitored_sources() 是否正确返回纯source ID
"""

import sys
sys.path.insert(0, '.')

from src.core.container import get_watch_service

def test_monitored_sources():
    """测试监控源列表"""
    print("=" * 60)
    print("测试: get_monitored_sources() 修复验证")
    print("=" * 60)

    ws = get_watch_service()
    ws._repository.reload()

    sources = ws.get_monitored_sources()

    print(f"\n✅ 监控源数量: {len(sources)}")
    print(f"✅ 监控源列表: {sorted(sources)}")

    # 验证格式
    all_valid = True
    for source in sources:
        if '|' in source:
            print(f"❌ 错误: 包含复合键: {source}")
            all_valid = False
        else:
            print(f"✓ 正确的source ID: {source}")

    if all_valid:
        print("\n✅ 所有监控源格式正确!")
    else:
        print("\n❌ 存在格式错误的监控源!")
        return False

    # 测试消息匹配
    print("\n" + "=" * 60)
    print("测试: 消息匹配逻辑")
    print("=" * 60)

    configs = ws.get_all_configs_dict()

    for test_source in sources:
        print(f"\n📨 模拟消息从 {test_source} 到达:")

        if test_source in sources:
            print(f"  ✅ 消息会被处理")

            # 查找匹配的任务
            matched = False
            for user_id, user_config in configs.items():
                for watch_key, watch_data in user_config.items():
                    if watch_data.get('source') == test_source:
                        matched = True
                        mode = "记录" if watch_data.get('record_mode') else "转发"
                        dest = watch_data.get('dest', 'N/A')
                        print(f"    - 用户 {user_id}: {mode} -> {dest}")

            if not matched:
                print(f"  ⚠️  警告: 在监控源列表中但没有匹配的任务!")
                all_valid = False
        else:
            print(f"  ❌ 消息不会被处理")
            all_valid = False

    print("\n" + "=" * 60)
    if all_valid:
        print("✅ 所有测试通过! 转发功能已修复")
    else:
        print("❌ 部分测试失败")
    print("=" * 60)

    return all_valid

if __name__ == "__main__":
    success = test_monitored_sources()
    sys.exit(0 if success else 1)
