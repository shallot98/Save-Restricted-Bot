#!/usr/bin/env python3
"""
链式转发功能测试脚本
验证磁力频道到备份频道的转发链是否正常工作
"""

import sys
sys.path.insert(0, '.')

from src.core.container import get_watch_service

def test_chain_forward():
    """测试链式转发逻辑"""
    print("=" * 70)
    print("链式转发功能测试")
    print("=" * 70)

    ws = get_watch_service()
    ws._repository.reload()

    monitored_sources = ws.get_monitored_sources()
    configs = ws.get_all_configs_dict()

    # 场景: 消息从 -1002203159247 到达
    source = '-1002203159247'
    print(f"\n📨 场景: incoming消息从 {source} 到达")
    print(f"   监控源列表: {sorted(monitored_sources)}")
    print(f"   是否在监控源: {source in monitored_sources}")

    if source not in monitored_sources:
        print("❌ 测试失败: 源不在监控列表中")
        return False

    # 步骤1: 查找第一级转发配置
    print(f"\n步骤1: 查找 {source} 的转发配置")
    first_level_dests = []
    for user_id, user_config in configs.items():
        for watch_key, watch_data in user_config.items():
            if watch_data.get('source') == source:
                dest = watch_data.get('dest')
                mode = '记录' if watch_data.get('record_mode') else '转发'
                print(f"  ✓ {mode}到: {dest}")
                if not watch_data.get('record_mode') and dest:
                    first_level_dests.append(dest)

    if not first_level_dests:
        print("❌ 测试失败: 没有找到转发配置")
        return False

    # 步骤2: 检查每个目标是否也是监控源(链式转发的关键)
    print(f"\n步骤2: 检查目标频道是否也是监控源(链式转发条件)")
    chain_forward_targets = []
    for dest in first_level_dests:
        dest_str = str(dest)
        is_monitored = dest_str in monitored_sources
        print(f"  目标 {dest}:")
        print(f"    是否在监控源: {is_monitored}")

        if is_monitored:
            print(f"    ✅ 会触发 _trigger_dest_monitoring")
            chain_forward_targets.append(dest_str)
        else:
            print(f"    ⏭️ 不会触发链式转发")

    if not chain_forward_targets:
        print("\n⚠️  警告: 没有目标频道会触发链式转发")
        return True  # 不算失败,只是没有链式转发

    # 步骤3: 对每个链式转发目标,查找其转发配置
    print(f"\n步骤3: 查找链式转发目标的配置")
    all_success = True
    for chain_target in chain_forward_targets:
        print(f"\n  链式目标: {chain_target}")
        found_config = False

        for user_id, user_config in configs.items():
            for watch_key, watch_data in user_config.items():
                if watch_data.get('source') == chain_target:
                    found_config = True
                    dest = watch_data.get('dest')
                    mode = '记录' if watch_data.get('record_mode') else '转发'

                    # 检查过滤规则
                    whitelist = watch_data.get('whitelist', [])
                    blacklist = watch_data.get('blacklist', [])
                    whitelist_regex = watch_data.get('whitelist_regex', [])
                    blacklist_regex = watch_data.get('blacklist_regex', [])

                    has_filters = any([whitelist, blacklist, whitelist_regex, blacklist_regex])

                    print(f"    ✓ 配置: {mode}到 {dest}")
                    if has_filters:
                        print(f"      过滤规则:")
                        if whitelist:
                            print(f"        whitelist: {whitelist}")
                        if blacklist:
                            print(f"        blacklist: {blacklist}")
                        if whitelist_regex:
                            print(f"        whitelist_regex: {whitelist_regex}")
                        if blacklist_regex:
                            print(f"        blacklist_regex: {blacklist_regex}")
                    else:
                        print(f"      无过滤规则(所有消息都会转发)")

        if not found_config:
            print(f"    ❌ 错误: 没有找到配置")
            all_success = False

    # 总结
    print("\n" + "=" * 70)
    if all_success:
        print("✅ 链式转发配置正确!")
        print("\n转发链路径:")
        print(f"  {source}")
        for dest in first_level_dests:
            print(f"    └─> {dest}")
            if dest in chain_forward_targets:
                for user_id, user_config in configs.items():
                    for watch_key, watch_data in user_config.items():
                        if watch_data.get('source') == dest and not watch_data.get('record_mode'):
                            final_dest = watch_data.get('dest')
                            print(f"          └─> {final_dest} (链式转发)")
    else:
        print("❌ 链式转发配置有问题")
    print("=" * 70)

    return all_success

if __name__ == "__main__":
    success = test_chain_forward()
    sys.exit(0 if success else 1)
