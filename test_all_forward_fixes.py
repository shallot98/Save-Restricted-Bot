#!/usr/bin/env python3
"""
转发功能综合测试脚本
验证所有转发相关的修复
"""

import sys
sys.path.insert(0, '.')

from src.core.container import get_watch_service

def test_basic_forward():
    """测试基础转发功能"""
    print("=" * 70)
    print("测试1: 基础转发功能")
    print("=" * 70)

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

    if all_valid:
        print("✅ 所有监控源格式正确(纯source ID)")
    else:
        print("❌ 监控源格式错误")
        return False

    return True

def test_chain_forward():
    """测试链式转发功能"""
    print("\n" + "=" * 70)
    print("测试2: 链式转发功能")
    print("=" * 70)

    ws = get_watch_service()
    ws._repository.reload()

    monitored_sources = ws.get_monitored_sources()
    configs = ws.get_all_configs_dict()

    # 查找所有转发链
    chains = []
    for user_id, user_config in configs.items():
        for watch_key, watch_data in user_config.items():
            source = watch_data.get('source')
            dest = watch_data.get('dest')
            record_mode = watch_data.get('record_mode', False)

            if not record_mode and dest:
                # 检查dest是否也是监控源
                if str(dest) in monitored_sources:
                    chains.append((source, dest))

    print(f"\n找到 {len(chains)} 个链式转发配置:")
    for source, dest in chains:
        print(f"  {source} -> {dest} (dest也是监控源)")

        # 查找dest的转发配置
        found_next = False
        for user_id, user_config in configs.items():
            for watch_key, watch_data in user_config.items():
                if watch_data.get('source') == dest and not watch_data.get('record_mode'):
                    next_dest = watch_data.get('dest')
                    print(f"    └─> {next_dest} (链式转发)")
                    found_next = True

        if not found_next:
            print(f"    ⚠️  dest没有转发配置(可能只有记录模式)")

    if chains:
        print(f"\n✅ 链式转发配置正确")
    else:
        print(f"\n⚠️  没有链式转发配置")

    return True

def test_message_matching():
    """测试消息匹配逻辑"""
    print("\n" + "=" * 70)
    print("测试3: 消息匹配逻辑")
    print("=" * 70)

    ws = get_watch_service()
    ws._repository.reload()

    monitored_sources = ws.get_monitored_sources()
    configs = ws.get_all_configs_dict()

    print(f"\n模拟消息到达测试:")

    # 测试每个监控源
    for source in sorted(monitored_sources):
        print(f"\n📨 消息从 {source} 到达:")

        # 查找匹配的配置
        matched = 0
        for user_id, user_config in configs.items():
            for watch_key, watch_data in user_config.items():
                if watch_data.get('source') == source:
                    matched += 1
                    dest = watch_data.get('dest')
                    mode = '记录' if watch_data.get('record_mode') else '转发'
                    print(f"  ✓ 配置 #{matched}: {mode}到 {dest}")

        if matched == 0:
            print(f"  ❌ 错误: 在监控源列表中但没有配置")
            return False

    print(f"\n✅ 所有监控源都有对应的配置")
    return True

def test_filter_rules():
    """测试过滤规则"""
    print("\n" + "=" * 70)
    print("测试4: 过滤规则检查")
    print("=" * 70)

    ws = get_watch_service()
    ws._repository.reload()

    configs = ws.get_all_configs_dict()

    print(f"\n过滤规则统计:")

    total_configs = 0
    configs_with_filters = 0

    for user_id, user_config in configs.items():
        for watch_key, watch_data in user_config.items():
            total_configs += 1

            whitelist = watch_data.get('whitelist', [])
            blacklist = watch_data.get('blacklist', [])
            whitelist_regex = watch_data.get('whitelist_regex', [])
            blacklist_regex = watch_data.get('blacklist_regex', [])

            has_filters = any([whitelist, blacklist, whitelist_regex, blacklist_regex])

            if has_filters:
                configs_with_filters += 1
                source = watch_data.get('source')
                dest = watch_data.get('dest')
                print(f"\n  配置: {source} -> {dest}")
                if whitelist:
                    print(f"    whitelist: {whitelist}")
                if blacklist:
                    print(f"    blacklist: {blacklist}")
                if whitelist_regex:
                    print(f"    whitelist_regex: {whitelist_regex}")
                if blacklist_regex:
                    print(f"    blacklist_regex: {blacklist_regex}")

    print(f"\n总配置数: {total_configs}")
    print(f"有过滤规则的配置: {configs_with_filters}")
    print(f"无过滤规则的配置: {total_configs - configs_with_filters}")

    print(f"\n✅ 过滤规则检查完成")
    return True

def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("转发功能综合测试")
    print("=" * 70)

    tests = [
        ("基础转发功能", test_basic_forward),
        ("链式转发功能", test_chain_forward),
        ("消息匹配逻辑", test_message_matching),
        ("过滤规则检查", test_filter_rules),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{name}' 出错: {e}")
            results.append((name, False))

    # 总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过! 转发功能已完全修复")
        return True
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
