#!/usr/bin/env python3
"""
诊断校准数据丢失问题的完整脚本
"""
import sys
import json
from database import get_note_by_id
from bot.utils.magnet_utils import extract_all_dns_from_note

def diagnose_note(note_id: int):
    """诊断笔记的校准数据"""
    print(f"\n{'='*60}")
    print(f"诊断笔记 ID: {note_id}")
    print('='*60)

    # 1. 从数据库读取
    note = get_note_by_id(note_id)
    if not note:
        print(f"❌ 笔记 {note_id} 不存在")
        return

    print("\n1️⃣ 数据库原始数据:")
    print(f"   filename: {note.get('filename', 'None')}")
    print(f"   magnet_link: {note.get('magnet_link', 'None')[:100]}...")
    print(f"   message_text (前200字符): {note.get('message_text', 'None')[:200]}...")

    # 2. 提取磁力链接信息（模拟前端）
    all_dns = extract_all_dns_from_note(note)

    print(f"\n2️⃣ extract_all_dns_from_note 提取结果:")
    print(f"   共提取到 {len(all_dns)} 个磁力链接")
    for idx, dn_info in enumerate(all_dns, 1):
        print(f"\n   磁力链接 #{idx}:")
        print(f"      info_hash: {dn_info.get('info_hash', 'None')}")
        print(f"      dn: {dn_info.get('dn', 'None')}")
        print(f"      magnet: {dn_info.get('magnet', 'None')[:80]}...")

    # 3. 分析问题
    print(f"\n3️⃣ 问题分析:")
    if note.get('filename'):
        print(f"   ✅ filename字段有值: {note['filename']}")
    else:
        print(f"   ❌ filename字段为空")

    if all_dns:
        if all_dns[0].get('dn'):
            print(f"   ✅ 第一个磁力链接有dn: {all_dns[0]['dn']}")
        else:
            print(f"   ❌ 第一个磁力链接的dn为空")
            print(f"   📋 这是问题所在！前端从message_text提取dn时失败了")
    else:
        print(f"   ❌ 没有提取到任何磁力链接")

    # 4. 检查message_text中的磁力链接
    message_text = note.get('message_text', '')
    if 'magnet:' in message_text:
        print(f"\n4️⃣ message_text中的磁力链接检查:")
        import re
        magnets = re.findall(r'magnet:\?xt=urn:btih:[^\s]+', message_text, re.IGNORECASE)
        for idx, magnet in enumerate(magnets, 1):
            print(f"\n   磁力链接 #{idx}: {magnet[:100]}...")
            if '&dn=' in magnet or '?dn=' in magnet:
                print(f"      ✅ 包含dn参数")
            else:
                print(f"      ❌ 不包含dn参数")

    return note, all_dns

if __name__ == '__main__':
    if len(sys.argv) > 1:
        note_id = int(sys.argv[1])
    else:
        note_id = 979  # 默认测试979

    note, all_dns = diagnose_note(note_id)

    # 输出JSON供分析
    print(f"\n5️⃣ JSON输出（供调试）:")
    result = {
        'note_id': note_id,
        'filename': note.get('filename'),
        'has_dn_in_extracted': bool(all_dns and all_dns[0].get('dn')),
        'extracted_dns_count': len(all_dns) if all_dns else 0,
        'extracted_first_dn': all_dns[0].get('dn') if all_dns and all_dns[0].get('dn') else None
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
