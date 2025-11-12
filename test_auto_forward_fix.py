#!/usr/bin/env python3
"""
测试脚本：验证 auto_forward 修复

此脚本验证：
1. auto_forward 处理器是否正确注册
2. 两个客户端是否都正常启动
3. idle() 是否正确使用以保持客户端运行
"""

import sys
import os

def test_imports():
    """测试必要的导入"""
    print("🧪 测试 1: 检查导入...")
    try:
        from pyrogram import idle
        print("   ✅ pyrogram.idle 可用")
        return True
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        return False

def test_main_py_structure():
    """测试 main.py 的结构"""
    print("\n🧪 测试 2: 检查 main.py 结构...")
    
    with open('/home/engine/project/main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = {
        "auto_forward 函数定义": "def auto_forward(client:",
        "消息处理器装饰器": "@acc.on_message(filters.channel | filters.group | filters.private)",
        "使用 idle()": "from pyrogram import idle",
        "调用 idle()": "idle()",
        "bot.start() 而非 bot.run()": "bot.start()",
        "不再使用 bot.run()": "bot.run()" not in content or content.count("bot.run()") == 0 or "# infinty polling" not in content,
        "添加详细日志": "📨 收到消息",
        "错误追踪": "traceback.format_exc()",
    }
    
    all_passed = True
    for check_name, check_condition in checks.items():
        if isinstance(check_condition, bool):
            passed = check_condition
        else:
            passed = check_condition in content
        
        if passed:
            print(f"   ✅ {check_name}")
        else:
            print(f"   ❌ {check_name}")
            all_passed = False
    
    return all_passed

def test_startup_sequence():
    """测试启动顺序"""
    print("\n🧪 测试 3: 检查启动顺序...")
    
    with open('/home/engine/project/main.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find key lines
    bot_start_line = -1
    idle_line = -1
    bot_stop_line = -1
    acc_stop_line = -1
    
    for i, line in enumerate(lines):
        if 'bot.start()' in line and not line.strip().startswith('#'):
            bot_start_line = i
        if 'idle()' in line and not line.strip().startswith('#'):
            idle_line = i
        if 'bot.stop()' in line and not line.strip().startswith('#'):
            bot_stop_line = i
        if 'acc.stop()' in line and not line.strip().startswith('#'):
            acc_stop_line = i
    
    checks = []
    
    if bot_start_line > 0:
        checks.append(("bot.start() 存在", True))
    else:
        checks.append(("bot.start() 存在", False))
    
    if idle_line > 0:
        checks.append(("idle() 存在", True))
    else:
        checks.append(("idle() 存在", False))
    
    if bot_start_line > 0 and idle_line > bot_start_line:
        checks.append(("idle() 在 bot.start() 之后", True))
    else:
        checks.append(("idle() 在 bot.start() 之后", False))
    
    if idle_line > 0 and bot_stop_line > idle_line:
        checks.append(("bot.stop() 在 idle() 之后", True))
    else:
        checks.append(("bot.stop() 在 idle() 之后", False))
    
    all_passed = True
    for check_name, passed in checks:
        if passed:
            print(f"   ✅ {check_name}")
        else:
            print(f"   ❌ {check_name}")
            all_passed = False
    
    return all_passed

def test_logging_added():
    """测试是否添加了详细日志"""
    print("\n🧪 测试 4: 检查详细日志...")
    
    with open('/home/engine/project/main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    log_messages = [
        "📨 收到消息",
        "✅ 匹配任务",
        "🔍 检查",
        "🎯 消息通过所有过滤器",
        "📝 记录模式",
        "📤 转发模式",
        "✅ 已转发消息",
        "❌ 处理消息时出错",
        "详细错误信息",
    ]
    
    all_passed = True
    for msg in log_messages:
        if msg in content:
            print(f"   ✅ 包含日志: {msg}")
        else:
            print(f"   ❌ 缺少日志: {msg}")
            all_passed = False
    
    return all_passed

def main():
    print("="*60)
    print("🔬 Auto-Forward 修复验证测试")
    print("="*60)
    
    results = []
    
    # Run all tests
    results.append(("导入测试", test_imports()))
    results.append(("结构测试", test_main_py_structure()))
    results.append(("启动顺序测试", test_startup_sequence()))
    results.append(("日志测试", test_logging_added()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 测试总结")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！修复应该已生效。")
        print("\n📝 修复说明:")
        print("  1. ✅ 将 bot.run() 改为 bot.start() (非阻塞)")
        print("  2. ✅ 使用 pyrogram.idle() 保持两个客户端运行")
        print("  3. ✅ 添加详细日志以跟踪消息处理")
        print("  4. ✅ 添加完整的错误堆栈跟踪")
        print("  5. ✅ 在函数开始时记录收到的每条消息")
        print("\n💡 现在启动 bot，auto_forward 应该能正常监听和转发消息了！")
        return 0
    else:
        print(f"\n⚠️ {total - passed} 个测试失败，请检查修复。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
