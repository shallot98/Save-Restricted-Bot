#!/usr/bin/env python3
"""测试校准逻辑修复"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.services.calibration_manager import get_calibration_manager

def test_should_calibrate():
    """测试should_calibrate_note逻辑"""
    manager = get_calibration_manager()

    print("=" * 60)
    print("测试校准逻辑")
    print("=" * 60)

    # 测试用例1：有dn参数的磁力链接（不应该校准）
    note_with_dn = {
        'id': 1,
        'magnet_link': 'magnet:?xt=urn:btih:ABC123&dn=test_file.mp4',
        'message_text': 'magnet:?xt=urn:btih:ABC123&dn=test_file.mp4',
        'filename': 'test_file.mp4'
    }

    result1 = manager.should_calibrate_note(note_with_dn)
    print(f"\n测试1 - 有dn参数的磁力链接:")
    print(f"  结果: {'需要校准' if result1 else '不需要校准'} ✅" if not result1 else f"  结果: {'需要校准' if result1 else '不需要校准'} ❌")
    print(f"  预期: 不需要校准")

    # 测试用例2：没有dn参数的磁力链接（应该校准）
    note_without_dn = {
        'id': 2,
        'magnet_link': 'magnet:?xt=urn:btih:DEF456',
        'message_text': 'magnet:?xt=urn:btih:DEF456',
        'filename': None
    }

    result2 = manager.should_calibrate_note(note_without_dn)
    print(f"\n测试2 - 没有dn参数的磁力链接:")
    print(f"  结果: {'需要校准' if result2 else '不需要校准'} ✅" if result2 else f"  结果: {'需要校准' if result2 else '不需要校准'} ❌")
    print(f"  预期: 需要校准")

    # 测试用例3：没有dn参数但有filename（已校准过，不应该再校准）
    note_calibrated = {
        'id': 3,
        'magnet_link': 'magnet:?xt=urn:btih:GHI789',
        'message_text': 'magnet:?xt=urn:btih:GHI789',
        'filename': 'calibrated_file.mp4'
    }

    result3 = manager.should_calibrate_note(note_calibrated)
    print(f"\n测试3 - 没有dn参数但有filename（已校准）:")
    print(f"  结果: {'需要校准' if result3 else '不需要校准'} ✅" if not result3 else f"  结果: {'需要校准' if result3 else '不需要校准'} ❌")
    print(f"  预期: 不需要校准")

    # 测试用例4：911笔记（修复后应该需要校准）
    from database import get_note_by_id
    note_911 = get_note_by_id(911)
    if note_911:
        result4 = manager.should_calibrate_note(note_911)
        print(f"\n测试4 - 911笔记（修复后）:")
        print(f"  magnet_link: {note_911.get('magnet_link')}")
        print(f"  filename: {note_911.get('filename')}")
        print(f"  结果: {'需要校准' if result4 else '不需要校准'} ✅" if result4 else f"  结果: {'需要校准' if result4 else '不需要校准'} ❌")
        print(f"  预期: 需要校准")

    # 测试用例5：912笔记（修复后应该需要校准）
    note_912 = get_note_by_id(912)
    if note_912:
        result5 = manager.should_calibrate_note(note_912)
        print(f"\n测试5 - 912笔记（修复后）:")
        print(f"  magnet_link: {note_912.get('magnet_link')}")
        print(f"  filename: {note_912.get('filename')}")
        print(f"  结果: {'需要校准' if result5 else '不需要校准'} ✅" if result5 else f"  结果: {'需要校准' if result5 else '不需要校准'} ❌")
        print(f"  预期: 需要校准")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == '__main__':
    test_should_calibrate()
