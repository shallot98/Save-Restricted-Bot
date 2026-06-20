#!/usr/bin/env python3
"""
测试修复后的 update_note_with_calibrated_dns 函数

验证:
1. DN参数不会重复追加
2. URL编码正确处理
3. 正则表达式能正确匹配和替换磁力链接
"""

import sys
import os
sys.path.insert(0, '/root/Save-Restricted-Bot')

from database import update_note_with_calibrated_dns
from bot.utils.magnet_utils import MagnetLinkParser
import sqlite3

def test_update_calibrated_dns():
    """测试校准后的DNS更新功能"""
    print("🧪 测试修复后的 update_note_with_calibrated_dns 函数\n")

    # 测试用例: 模拟对笔记1030的再次手动校准
    note_id = 1030
    test_filename = "【重磅核弹】电报大神 【路少】 游走各大会所红灯区 第一视角（中）"
    info_hash = "C988BF6D21E3B0FE46D79C40D41BD85BB90E11CB"

    # 读取修复前的状态
    db_path = '/root/Save-Restricted-Bot/data/notes.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT message_text, magnet_link, filename FROM notes WHERE id = ?', (note_id,))
    before_message_text, before_magnet_link, before_filename = cursor.fetchone()

    print(f"📄 修复前状态:")
    print(f"  message_text 长度: {len(before_message_text)} 字符")
    print(f"  magnet_link: {before_magnet_link[:100]}...")
    print(f"  filename: {before_filename}\n")

    # 构造校准结果(模拟再次手动校准)
    calibrated_results = [{
        'info_hash': info_hash,
        'old_magnet': before_magnet_link,
        'filename': test_filename,
        'success': True
    }]

    print(f"🔄 模拟手动校准: 使用相同的filename再次校准...")

    # 执行更新
    success = update_note_with_calibrated_dns(note_id, calibrated_results)

    if not success:
        print("❌ 更新失败!")
        conn.close()
        return False

    # 读取更新后的状态
    cursor.execute('SELECT message_text, magnet_link, filename FROM notes WHERE id = ?', (note_id,))
    after_message_text, after_magnet_link, after_filename = cursor.fetchone()

    print(f"\n📄 修复后状态:")
    print(f"  message_text 长度: {len(after_message_text)} 字符")
    print(f"  magnet_link: {after_magnet_link[:100]}...")
    print(f"  filename: {after_filename}\n")

    # 验证1: message_text 长度不应该增加
    if len(after_message_text) > len(before_message_text):
        print(f"❌ 验证失败: message_text 长度增加了 {len(after_message_text) - len(before_message_text)} 字符")
        print(f"   这说明DN参数可能被重复追加了!")
        conn.close()
        return False
    else:
        print(f"✅ 验证1通过: message_text 长度没有增加 (长度变化: {len(after_message_text) - len(before_message_text)})")

    # 验证2: message_text 中只有一个该hash的磁力链接
    magnet_pattern = rf'magnet:\?xt=urn:btih:\s*{info_hash}'
    import re
    matches = list(re.finditer(magnet_pattern, after_message_text, flags=re.IGNORECASE))

    if len(matches) != 1:
        print(f"❌ 验证失败: message_text 中有 {len(matches)} 个该hash的磁力链接 (应该只有1个)")
        conn.close()
        return False
    else:
        print(f"✅ 验证2通过: message_text 中只有1个该hash的磁力链接")

    # 验证3: 磁力链接的DN参数应该是URL编码的
    dn_param = MagnetLinkParser.extract_dn_parameter(after_magnet_link)

    if dn_param == test_filename:
        print(f"✅ 验证3通过: DN参数正确解码为: {dn_param}")
    else:
        print(f"❌ 验证失败: DN参数解码不正确")
        print(f"   期望: {test_filename}")
        print(f"   实际: {dn_param}")
        conn.close()
        return False

    # 验证4: message_text 中不应该有未编码的重复文件名
    repeat_count = after_message_text.count(test_filename)
    if repeat_count > 1:
        print(f"⚠️ 警告: message_text 中发现 {repeat_count} 次未编码的文件名 (可能是正常的)")
    else:
        print(f"✅ 验证4通过: message_text 中未编码的文件名出现次数正常 ({repeat_count} 次)")

    conn.close()

    print(f"\n🎉 所有验证通过! 修复成功!")
    return True


if __name__ == '__main__':
    success = test_update_calibrated_dns()
    sys.exit(0 if success else 1)
