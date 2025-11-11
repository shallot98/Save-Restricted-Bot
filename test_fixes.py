#!/usr/bin/env python3
"""
Test script to verify the two bug fixes:
1. Search panel is hidden by default
2. Bot can respond to messages in groups when mentioned or replied to
"""

import sys

def test_search_panel_hidden():
    """Test that search panel has display: none by default"""
    print("\n🧪 测试 1: 搜索面板默认隐藏")
    print("-" * 50)
    
    with open('templates/notes.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the .search-panel CSS class
    search_panel_start = content.find('.search-panel {')
    if search_panel_start == -1:
        print("❌ 未找到 .search-panel CSS 类")
        return False
    
    # Get the CSS block (up to the closing brace)
    search_panel_end = content.find('}', search_panel_start)
    search_panel_css = content[search_panel_start:search_panel_end]
    
    # Check if display: none is present
    if 'display: none' in search_panel_css or 'display:none' in search_panel_css:
        print("✅ 搜索面板 CSS 包含 display: none")
        print("   搜索面板将默认隐藏，只有点击搜索图标才会显示")
        return True
    else:
        print("❌ 搜索面板 CSS 缺少 display: none")
        print("   面板可能会在页面加载时显示")
        return False


def test_group_message_filter():
    """Test that message handler accepts group messages with mentions/replies"""
    print("\n🧪 测试 2: 群组消息处理")
    print("-" * 50)
    
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the message handler decorator
    handler_pattern = '@bot.on_message(filters.text'
    handler_start = content.find(handler_pattern)
    
    if handler_start == -1:
        print("❌ 未找到消息处理器")
        return False
    
    # Get the decorator line
    handler_end = content.find('\n', handler_start)
    handler_line = content[handler_start:handler_end]
    
    # Check for the filter modifications
    has_private = 'filters.private' in handler_line
    has_mentioned = 'filters.mentioned' in handler_line
    has_reply = 'filters.reply' in handler_line
    has_or = '|' in handler_line or ' or ' in handler_line.lower()
    
    print(f"   过滤器检查:")
    print(f"   - filters.private: {'✅' if has_private else '❌'}")
    print(f"   - filters.mentioned: {'✅' if has_mentioned else '❌'}")
    print(f"   - filters.reply: {'✅' if has_reply else '❌'}")
    print(f"   - 使用 OR 逻辑: {'✅' if has_or else '❌'}")
    
    if has_private and has_mentioned and has_reply and has_or:
        print("\n✅ 消息处理器已正确配置")
        print("   机器人将响应:")
        print("   - 私聊中的所有消息（除命令外）")
        print("   - 群组/频道中提及机器人的消息")
        print("   - 群组/频道中回复机器人的消息")
        return True
    elif has_private and not (has_mentioned or has_reply):
        print("\n❌ 消息处理器仅限私聊")
        print("   机器人在群组中无法使用")
        return False
    else:
        print("\n⚠️  消息处理器配置不完整")
        return False


def main():
    print("\n" + "=" * 60)
    print("🔧 Bug 修复验证测试")
    print("=" * 60)
    
    test1_pass = test_search_panel_hidden()
    test2_pass = test_group_message_filter()
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    print(f"测试 1 (搜索面板默认隐藏): {'✅ 通过' if test1_pass else '❌ 失败'}")
    print(f"测试 2 (群组消息处理): {'✅ 通过' if test2_pass else '❌ 失败'}")
    
    all_passed = test1_pass and test2_pass
    
    if all_passed:
        print("\n🎉 所有测试通过！")
        print("\n✨ 修复说明:")
        print("1. 搜索面板现在默认隐藏，只有点击搜索图标才会弹出")
        print("2. 机器人现在可以在群组/频道中使用，通过 @机器人 或回复机器人的消息")
        print("\n📝 使用方法:")
        print("- 在群组中: @bot_username https://t.me/...")
        print("- 或回复机器人发送的消息，然后发送链接")
    else:
        print("\n❌ 部分测试失败")
        sys.exit(1)
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
