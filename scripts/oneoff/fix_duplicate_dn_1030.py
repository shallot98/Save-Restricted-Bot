#!/usr/bin/env python3
"""
修复笔记1030中重复的DN参数问题

问题: 由于多次手动校准,message_text字段中的磁力链接DN参数被重复追加了5次
解决方案: 清理重复的DN参数,只保留一个正确的DN参数
"""

import sqlite3
import re
from urllib.parse import quote
from src.domain.magnet import MagnetLinkParser

def fix_note_1030():
    """修复笔记1030的重复DN参数"""
    db_path = '/root/Save-Restricted-Bot/data/notes.db'
    note_id = 1030

    print(f"🔧 开始修复笔记 {note_id} 的重复DN参数问题...")

    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 读取当前笔记数据
        cursor.execute('SELECT message_text, magnet_link, filename FROM notes WHERE id = ?', (note_id,))
        row = cursor.fetchone()

        if not row:
            print(f"❌ 笔记 {note_id} 不存在")
            return False

        message_text, magnet_link, filename = row

        print(f"\n📄 当前状态:")
        print(f"  message_text 长度: {len(message_text)} 字符")
        print(f"  magnet_link: {magnet_link[:100]}...")
        print(f"  filename: {filename}")

        # 从magnet_link提取正确的DN参数
        correct_dn = MagnetLinkParser.extract_dn_parameter(magnet_link)
        if not correct_dn:
            correct_dn = filename  # 如果magnet_link没有DN,使用filename字段

        print(f"\n✅ 正确的DN参数: {correct_dn}")

        # 提取info_hash
        info_hash = MagnetLinkParser.extract_info_hash(magnet_link)
        if not info_hash:
            print(f"❌ 无法提取info_hash")
            return False

        print(f"✅ Info Hash: {info_hash}")

        # 修复message_text中的重复DN参数
        # 策略: 替换为未编码的中文文件名(方便用户阅读)
        correct_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={correct_dn}"

        # 正则匹配该hash的所有磁力链接(包括所有参数和后续的重复文本)
        # 匹配到下一个 # 号或magnet:或字符串结尾
        magnet_pattern = rf'magnet:\?xt=urn:btih:\s*{re.escape(info_hash)}[^\n#]*?(?=\s*(?:#|magnet:|$))'

        # 查找所有匹配项
        matches = list(re.finditer(magnet_pattern, message_text, flags=re.IGNORECASE))
        print(f"\n🔍 找到 {len(matches)} 个该hash的磁力链接")

        for i, match in enumerate(matches, 1):
            matched_text = match.group()
            print(f"  匹配 {i} (长度 {len(matched_text)}): {matched_text[:100]}...")

        # 替换所有匹配项为正确的磁力链接
        fixed_message_text = re.sub(magnet_pattern, correct_magnet, message_text, flags=re.IGNORECASE)

        print(f"\n📝 修复后的 message_text 长度: {len(fixed_message_text)} 字符")

        # 更新数据库
        cursor.execute(
            'UPDATE notes SET message_text = ? WHERE id = ?',
            (fixed_message_text, note_id)
        )

        conn.commit()

        print(f"\n✅ 笔记 {note_id} 已成功修复!")
        print(f"\n📊 修复统计:")
        print(f"  修复前长度: {len(message_text)} 字符")
        print(f"  修复后长度: {len(fixed_message_text)} 字符")
        print(f"  减少字符: {len(message_text) - len(fixed_message_text)} 字符")

        # 验证修复结果
        cursor.execute('SELECT message_text FROM notes WHERE id = ?', (note_id,))
        new_message_text = cursor.fetchone()[0]

        # 检查是否还有重复
        new_matches = list(re.finditer(magnet_pattern, new_message_text, flags=re.IGNORECASE))
        print(f"\n🔍 验证: 修复后找到 {len(new_matches)} 个该hash的磁力链接")

        if len(new_matches) == 1:
            print("✅ 验证通过: 现在只有1个正确的磁力链接")
        else:
            print(f"⚠️ 警告: 修复后仍有 {len(new_matches)} 个磁力链接")

        return True

    except Exception as e:
        print(f"❌ 修复过程出错: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == '__main__':
    fix_note_1030()
