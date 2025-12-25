#!/usr/bin/env python3
"""
测试三个修复功能：
1. 登录页面保存密码功能
2. 自动校准功能（检测message_text中的磁力链接）
3. 多条磁力链接逐条检测
"""
import re
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_magnet_detection():
    """测试磁力链接检测逻辑"""
    print("=" * 60)
    print("测试1: 磁力链接检测逻辑")
    print("=" * 60)

    # 测试用例
    test_cases = [
        {
            "name": "单条磁力链接",
            "text": "这是一个测试 magnet:?xt=urn:btih:ABC123DEF456 下载链接",
            "expected": True
        },
        {
            "name": "多条磁力链接",
            "text": """
            第一个: magnet:?xt=urn:btih:ABC123DEF456
            第二个: magnet:?xt=urn:btih:789GHI012JKL
            第三个: magnet:?xt=urn:btih:345MNO678PQR
            """,
            "expected": True
        },
        {
            "name": "无磁力链接",
            "text": "这是一个普通的笔记，没有磁力链接",
            "expected": False
        },
        {
            "name": "空文本",
            "text": "",
            "expected": False
        }
    ]

    magnet_pattern = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+'

    for case in test_cases:
        has_magnet = bool(re.search(magnet_pattern, case['text'], re.IGNORECASE))
        status = "✅ 通过" if has_magnet == case['expected'] else "❌ 失败"
        print(f"\n{status} - {case['name']}")
        print(f"  预期: {case['expected']}, 实际: {has_magnet}")

        if has_magnet:
            magnets = re.findall(magnet_pattern, case['text'], re.IGNORECASE)
            print(f"  找到 {len(magnets)} 个磁力链接")

def test_multi_magnet_extraction():
    """测试多条磁力链接提取"""
    print("\n" + "=" * 60)
    print("测试2: 多条磁力链接提取")
    print("=" * 60)

    from bot.services.calibration_manager import CalibrationManager

    manager = CalibrationManager()

    # 测试笔记
    test_note = {
        'message_text': """
        电影资源合集：
        1. 电影A: magnet:?xt=urn:btih:ABC123DEF456&dn=Movie_A.mkv
        2. 电影B: magnet:?xt=urn:btih:789GHI012JKL&dn=Movie_B.mp4
        3. 电影C: magnet:?xt=urn:btih:345MNO678PQR&dn=Movie_C.avi
        """,
        'magnet_link': None
    }

    all_dns = manager.extract_all_dns_from_note(test_note)

    print(f"\n找到 {len(all_dns)} 个磁力链接:")
    for idx, dn_info in enumerate(all_dns, 1):
        print(f"  {idx}. Hash: {dn_info['info_hash']}")
        print(f"     Magnet: {dn_info['magnet'][:60]}...")

    if len(all_dns) == 3:
        print("\n✅ 多条磁力链接提取测试通过")
    else:
        print(f"\n❌ 多条磁力链接提取测试失败（预期3个，实际{len(all_dns)}个）")

def test_calibration_trigger():
    """测试自动校准触发条件"""
    print("\n" + "=" * 60)
    print("测试3: 自动校准触发条件")
    print("=" * 60)

    from bot.services.calibration_manager import CalibrationManager

    manager = CalibrationManager()

    # 测试用例
    test_cases = [
        {
            "name": "有magnet_link字段",
            "note": {
                'magnet_link': 'magnet:?xt=urn:btih:ABC123',
                'message_text': '测试笔记',
                'filename': None
            },
            "should_calibrate": True
        },
        {
            "name": "message_text中有磁力链接",
            "note": {
                'magnet_link': None,
                'message_text': '下载: magnet:?xt=urn:btih:ABC123',
                'filename': None
            },
            "should_calibrate": True
        },
        {
            "name": "多条磁力链接",
            "note": {
                'magnet_link': None,
                'message_text': 'magnet:?xt=urn:btih:ABC123\nmagnet:?xt=urn:btih:DEF456',
                'filename': None
            },
            "should_calibrate": True
        },
        {
            "name": "无磁力链接",
            "note": {
                'magnet_link': None,
                'message_text': '普通笔记',
                'filename': None
            },
            "should_calibrate": False
        },
        {
            "name": "已校准过（有filename）",
            "note": {
                'magnet_link': 'magnet:?xt=urn:btih:ABC123',
                'message_text': '测试笔记',
                'filename': 'Movie.mkv'
            },
            "should_calibrate": False
        }
    ]

    for case in test_cases:
        should_calibrate = manager.should_calibrate_note(case['note'])
        status = "✅ 通过" if should_calibrate == case['should_calibrate'] else "❌ 失败"
        print(f"\n{status} - {case['name']}")
        print(f"  预期: {case['should_calibrate']}, 实际: {should_calibrate}")

def test_login_remember_logic():
    """测试登录记住密码逻辑"""
    print("\n" + "=" * 60)
    print("测试4: 登录记住密码逻辑")
    print("=" * 60)

    print("\n检查app.py中的登录逻辑...")

    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查关键代码
    checks = [
        ("获取remember参数", "remember = request.form.get('remember')"),
        ("设置session.permanent", "session.permanent = True"),
        ("设置30天有效期", "timedelta(days=30)"),
        ("处理不记住的情况", "session.permanent = False")
    ]

    all_passed = True
    for name, code in checks:
        if code in content:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} - 未找到代码: {code}")
            all_passed = False

    if all_passed:
        print("\n✅ 登录记住密码逻辑检查通过")
    else:
        print("\n❌ 登录记住密码逻辑检查失败")

def main():
    """运行所有测试"""
    print("\n🔧 开始测试修复功能...\n")

    try:
        test_magnet_detection()
        test_multi_magnet_extraction()
        test_calibration_trigger()
        test_login_remember_logic()

        print("\n" + "=" * 60)
        print("✅ 所有测试完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
