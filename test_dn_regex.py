#!/usr/bin/env python3
"""测试DN参数正则匹配"""
import re
from urllib.parse import unquote_plus

magnet = "magnet:?xt=urn:btih:7098083BDAD310B3F2076261A04E7FD2B1409984&dn=%E7%B4%84%E5%AB%96%E9%81%94%E4%BA%BA%EF%BD%9C%E8%83%96%E7%88%BA%E7%9A%84%E5%A5%87%E5%A6%99%E4%B9%8B%E6%97%85%EF%BD%9C%E5%90%88%E8%BC%AF%20%E7%B4%84%E5%90%84%E8%89%B2%E7%A8%9A%E5%AB%A9%E5%AD%B8%E7%94%9F%E5%A6%B9%E7%A9%BF%E7%B5%B2%E8%A5%AA%E5%88%B6%E6%9C%8D%E9%9C%B2%E8%87%89%E6%89%93%E7%82%AE%2044V"

DN_PARAMETER_PATTERN = r'[&?]dn=([^\n\r&]+)'

print("测试磁力链接:")
print(magnet)
print()

match = re.search(DN_PARAMETER_PATTERN, magnet)
if match:
    dn_encoded = match.group(1)
    print(f"正则匹配到的编码dn: {dn_encoded}")
    print()

    dn_decoded = unquote_plus(dn_encoded)
    print(f"URL解码后的dn: {dn_decoded}")
else:
    print("❌ 正则没有匹配到dn参数!")

print()
print("="*80)
print("问题分析:")

# 检查是否有空格
if ' ' in magnet:
    space_pos = magnet.index(' ')
    print(f"✓ 磁力链接中包含空格,位置: {space_pos}")
    print(f"  空格前的内容: ...{magnet[space_pos-20:space_pos]}")
    print(f"  空格后的内容: {magnet[space_pos:space_pos+20]}...")
