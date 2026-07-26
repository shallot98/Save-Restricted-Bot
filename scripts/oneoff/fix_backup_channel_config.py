#!/usr/bin/env python3
"""
修复备份频道ID配置
将正数ID转换为正确的频道ID格式
"""
import sys
import json
sys.path.insert(0, '.')

from config import load_watch_config

def fix_channel_id():
    """修复备份频道ID"""
    print("=" * 70)
    print("修复备份频道ID配置")
    print("=" * 70)

    # 加载当前配置
    config = load_watch_config()

    old_id = '7086222377'
    new_id = '-1007086222377'  # 标准频道ID格式

    print(f"\n当前备份频道ID: {old_id}")
    print(f"修正后的频道ID: {new_id}")

    # 查找并更新配置
    updated = False
    for user_id, watches in config.items():
        for watch_key, watch_data in watches.items():
            if isinstance(watch_data, dict):
                dest = watch_data.get('dest')

                if dest == old_id:
                    print(f"\n找到需要更新的配置:")
                    print(f"  用户: {user_id}")
                    print(f"  配置: {watch_key}")
                    print(f"  当前目标: {dest}")

                    # 更新ID
                    watch_data['dest'] = new_id
                    updated = True

                    print(f"  ✅ 已更新为: {new_id}")

    if not updated:
        print(f"\n⚠️ 未找到使用 {old_id} 的配置")
        print(f"\n可能的原因:")
        print(f"  1. 配置已经是正确的")
        print(f"  2. 备份频道ID不是 {old_id}")
        return False

    # 保存更新后的配置
    config_file = 'data/watch_config.json'
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 配置已保存到: {config_file}")
        return True

    except Exception as e:
        print(f"\n❌ 保存配置失败: {e}")
        return False

def verify_fix():
    """验证修复结果"""
    print("\n" + "=" * 70)
    print("验证修复结果")
    print("=" * 70)

    # 重新加载配置
    config = load_watch_config()

    new_id = '-1007086222377'
    found = False

    for user_id, watches in config.items():
        for watch_key, watch_data in watches.items():
            if isinstance(watch_data, dict):
                dest = watch_data.get('dest')

                if dest == new_id:
                    found = True
                    print(f"\n✅ 找到更新后的配置:")
                    print(f"  用户: {user_id}")
                    print(f"  配置: {watch_key}")
                    print(f"  目标: {dest}")

    if found:
        print(f"\n✅ 配置修复成功！")
        return True
    else:
        print(f"\n❌ 未找到更新后的配置")
        return False

def main():
    print("开始修复备份频道ID配置\n")

    print("⚠️ 重要提示:")
    print("  此脚本将把备份频道ID从 7086222377 更新为 -1007086222377")
    print("  这是Telegram频道的标准ID格式")
    print()

    response = input("是否继续？(y/n): ")

    if response.lower() != 'y':
        print("\n❌ 操作已取消")
        return

    success = fix_channel_id()

    if success:
        verify_fix()

        print("\n" + "=" * 70)
        print("下一步操作")
        print("=" * 70)
        print("\n1. 重启Bot以应用新配置:")
        print("   docker-compose restart bot")
        print("\n2. 查看启动日志，确认Peer缓存成功:")
        print("   docker logs -f save-restricted-bot-bot")
        print("\n3. 在磁力频道发送测试消息:")
        print("   magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678")
        print("\n4. 检查备份频道是否收到转发的消息")
    else:
        print("\n❌ 修复失败")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 修复失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
