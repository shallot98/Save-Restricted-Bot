#!/usr/bin/env python3
"""
测试校准判断逻辑：区分从dn参数提取的filename和真正校准得到的filename
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.services.calibration_manager import CalibrationManager

def test_calibration_logic():
    """测试校准判断逻辑"""
    print("=" * 60)
    print("测试校准判断逻辑")
    print("=" * 60)

    manager = CalibrationManager()

    # 测试用例
    test_cases = [
        {
            "name": "849笔记：filename来自dn参数",
            "note": {
                'magnet_link': 'magnet:?xt=urn:btih:54ffce3a29f67e33814243e734201a67221a73eb&dn=%E7%86%9F%E5%A5%B3%E7%A9%BA%E5%BF%85%E5%A4%87%EF%BC%81%E4%B8%9D%E8%A2%9C%E7%86%9F%E5%A5%B3%E5%9B%A2%E9%98%9F%E3%80%90%E6%9C%AA%E7%9F%A5%E5%A7%93%E5%90%8D%E3%80%91%E7%B3%BB%E5%88%97',
                'message_text': '熟女空必备！丝袜熟女团队【未知姓名】系列  #合集',
                'filename': '熟女空必备！丝袜熟女团队【未知姓名】系列'
            },
            "should_calibrate": True,
            "reason": "filename与dn参数一致，应该校准"
        },
        {
            "name": "filename为空",
            "note": {
                'magnet_link': 'magnet:?xt=urn:btih:ABC123',
                'message_text': '测试笔记',
                'filename': None
            },
            "should_calibrate": True,
            "reason": "filename为空，应该校准"
        },
        {
            "name": "filename不为空且与dn不一致（真正校准过）",
            "note": {
                'magnet_link': 'magnet:?xt=urn:btih:ABC123&dn=old_name',
                'message_text': '测试笔记',
                'filename': 'Real_Calibrated_Name.mkv'
            },
            "should_calibrate": False,
            "reason": "filename与dn不一致，说明是真正校准过的"
        },
        {
            "name": "无dn参数但有filename",
            "note": {
                'magnet_link': 'magnet:?xt=urn:btih:ABC123',
                'message_text': '测试笔记',
                'filename': 'Some_File.mkv'
            },
            "should_calibrate": False,
            "reason": "无dn参数但有filename，说明是真正校准过的"
        },
        {
            "name": "无magnet_link但message_text中有磁力链接",
            "note": {
                'magnet_link': None,
                'message_text': '下载: magnet:?xt=urn:btih:ABC123',
                'filename': None
            },
            "should_calibrate": True,
            "reason": "message_text中有磁力链接且filename为空"
        }
    ]

    passed = 0
    failed = 0

    for case in test_cases:
        should_calibrate = manager.should_calibrate_note(case['note'])
        expected = case['should_calibrate']

        if should_calibrate == expected:
            status = "✅ 通过"
            passed += 1
        else:
            status = "❌ 失败"
            failed += 1

        print(f"\n{status} - {case['name']}")
        print(f"  预期: {expected}, 实际: {should_calibrate}")
        print(f"  原因: {case['reason']}")

    print("\n" + "=" * 60)
    print(f"测试结果: 通过 {passed}/{len(test_cases)}, 失败 {failed}/{len(test_cases)}")
    print("=" * 60)

    return failed == 0

if __name__ == '__main__':
    success = test_calibration_logic()
    sys.exit(0 if success else 1)
