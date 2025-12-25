#!/usr/bin/env python3
"""测试从笔记979提取dn参数"""
import sys
sys.path.insert(0, '/root/Save-Restricted-Bot')

from database import get_note_by_id
from bot.utils.magnet_utils import extract_all_dns_from_note
from urllib.parse import unquote

# 获取笔记979
note = get_note_by_id(979)

print("="*80)
print("笔记979数据:")
print(f"ID: {note['id']}")
print(f"Filename: {note.get('filename')}")
print(f"Magnet Link:")
print(f"  {note.get('magnet_link')}")
print()

# 提取所有dn
all_dns = extract_all_dns_from_note(note)

print("="*80)
print(f"提取到 {len(all_dns)} 个磁力链接:")
for idx, item in enumerate(all_dns, 1):
    print(f"\n{idx}. Info Hash: {item.get('info_hash')}")
    print(f"   DN: {item.get('dn')}")
    print(f"   Magnet (前100字符): {item.get('magnet', '')[:100]}")

# 解码dn参数以便阅读
if all_dns and all_dns[0].get('dn'):
    print("\n" + "="*80)
    print("第一个dn参数:")
    print(f"  {all_dns[0].get('dn')}")
