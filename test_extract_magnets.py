#!/usr/bin/env python3
"""测试extract_all_magnets是否截断磁力链接"""
import sys
sys.path.insert(0, '/root/Save-Restricted-Bot')

from database import get_note_by_id
from bot.utils.magnet_utils import MagnetLinkParser

# 获取笔记979
note = get_note_by_id(979)
message_text = note.get('message_text', '')

print("="*80)
print("笔记979的message_text:")
print(message_text[:300])
print("...")
print()

# 从message_text中提取磁力链接
magnets = MagnetLinkParser.extract_all_magnets(message_text)

print("="*80)
print(f"从message_text中提取到 {len(magnets)} 个磁力链接:")
for idx, magnet in enumerate(magnets, 1):
    print(f"\n{idx}. 长度: {len(magnet)}")
    print(f"   内容: {magnet}")

    # 检查是否包含dn参数
    if '&dn=' in magnet or '?dn=' in magnet:
        print("   ✓ 包含dn参数")
    else:
        print("   ❌ 不包含dn参数")

print("\n" + "="*80)
print("数据库中的magnet_link:")
db_magnet = note.get('magnet_link', '')
print(f"长度: {len(db_magnet)}")
print(f"内容: {db_magnet}")

print("\n" + "="*80)
print("对比:")
if magnets:
    print(f"message_text提取的长度: {len(magnets[0])}")
    print(f"数据库magnet_link长度: {len(db_magnet)}")
    if len(magnets[0]) < len(db_magnet):
        print(f"❌ message_text提取的磁力链接被截断了 (少了 {len(db_magnet) - len(magnets[0])} 字符)")
