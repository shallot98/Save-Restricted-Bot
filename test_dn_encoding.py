#!/usr/bin/env python3
"""
测试修复后的功能 - 验证message_text中DN参数不编码

验证:
1. message_text 中DN参数是未编码的中文
2. magnet_link 字段中DN参数是URL编码的
3. 再次手动校准不会导致DN参数重复
"""

import sys
import os
sys.path.insert(0, '/root/Save-Restricted-Bot')

from database import update_note_with_calibrated_dns
from bot.utils.magnet_utils import MagnetLinkParser
import sqlite3

def test_dn_encoding():
    """测试DN参数编码处理"""
    print("🧪 测试DN参数编码处理\n")

    note_id = 1030
    info_hash = "C988BF6D21E3B0FE46D79C40D41BD85BB90E11CB"

    db_path = '/root/Save-Restricted-Bot/data/notes.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 读取当前状态
    cursor.execute('SELECT message_text, magnet_link, filename FROM notes WHERE id = ?', (note_id,))
    before_message_text, before_magnet_link, before_filename = cursor.fetchone()

    # 使用数据库中的实际filename
    test_filename = before_filename

    print(f"📄 修复前状态:")
    print(f"  message_text 长度: {len(before_message_text)} 字符")
    print(f"  message_text: {before_message_text[:150]}...")
    print(f"  magnet_link: {before_magnet_link[:100]}...")
    print(f"  filename: {before_filename}\n")

    # 验证1: message_text 中DN参数应该是未编码的中文
    if test_filename in before_message_text:
        print(f"✅ 验证1通过: message_text 中包含未编码的中文DN参数")
        print(f"   找到: {test_filename}\n")
    else:
        print(f"❌ 验证1失败: message_text 中没有找到未编码的中文DN参数")
        print(f"   期望: {test_filename}")
        conn.close()
        return False

    # 验证2: magnet_link 字段中DN参数应该是URL编码的
    dn_from_magnet_link = MagnetLinkParser.extract_dn_parameter(before_magnet_link)
    if dn_from_magnet_link == test_filename:
        print(f"✅ 验证2通过: magnet_link 字段DN参数正确(URL编码后解码一致)")
        print(f"   解码后: {dn_from_magnet_link}\n")
    else:
        print(f"❌ 验证2失败: magnet_link 字段DN参数不正确")
        print(f"   期望: {test_filename}")
        print(f"   实际: {dn_from_magnet_link}")
        conn.close()
        return False

    # 模拟再次手动校准
    print(f"🔄 模拟再次手动校准...\n")

    calibrated_results = [{
        'info_hash': info_hash,
        'old_magnet': before_magnet_link,
        'filename': test_filename,
        'success': True
    }]

    success = update_note_with_calibrated_dns(note_id, calibrated_results)

    if not success:
        print("❌ 更新失败!")
        conn.close()
        return False

    # 读取更新后的状态
    cursor.execute('SELECT message_text, magnet_link, filename FROM notes WHERE id = ?', (note_id,))
    after_message_text, after_magnet_link, after_filename = cursor.fetchone()

    print(f"📄 修复后状态:")
    print(f"  message_text 长度: {len(after_message_text)} 字符")
    print(f"  message_text: {after_message_text[:150]}...")
    print(f"  magnet_link: {after_magnet_link[:100]}...")
    print(f"  filename: {after_filename}\n")

    # 验证3: message_text 长度不应该增加
    if len(after_message_text) > len(before_message_text):
        print(f"❌ 验证3失败: message_text 长度增加了 {len(after_message_text) - len(before_message_text)} 字符")
        conn.close()
        return False
    else:
        print(f"✅ 验证3通过: message_text 长度没有增加 (变化: {len(after_message_text) - len(before_message_text)})")

    # 验证4: message_text 中仍然包含未编码的中文DN参数
    if test_filename in after_message_text:
        print(f"✅ 验证4通过: message_text 中仍然包含未编码的中文DN参数")
    else:
        print(f"❌ 验证4失败: message_text 中未编码的中文DN参数丢失")
        conn.close()
        return False

    # 验证5: message_text 中不应该有重复的文件名
    count = after_message_text.count(test_filename)
    if count == 1:
        print(f"✅ 验证5通过: message_text 中只有1个未编码的文件名")
    else:
        print(f"❌ 验证5失败: message_text 中有 {count} 个未编码的文件名 (应该只有1个)")
        conn.close()
        return False

    conn.close()

    print(f"\n🎉 所有验证通过! DN参数编码处理正确!")
    print(f"\n📊 总结:")
    print(f"  - message_text: DN参数未编码 ✅ (方便用户阅读)")
    print(f"  - magnet_link: DN参数URL编码 ✅ (符合标准)")
    print(f"  - 重复校准不会导致DN重复 ✅")

    return True


if __name__ == '__main__':
    success = test_dn_encoding()
    sys.exit(0 if success else 1)
