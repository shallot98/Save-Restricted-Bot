#!/usr/bin/env python3
"""测试磁力链接正则表达式"""

import re
from urllib.parse import unquote

# 原始message_text
text_911 = """#日期20251217 #23264185 #酒店偷拍 #反差婊

【新片速遞】12-17流出酒店偷拍 反差婊可爱眼镜学妹被猥琐男友带到酒店操小穴[1848MB/MP4/02:00:01]

magnet:?xt=urn:btih:609D0C47FD957FD2CCE391F618C3ECEC2B3BA913&dn=12-15流出酒店偷拍 反差婊可爱眼镜学妹被猥琐男友带到酒店操小穴 6942d3ac403ce9d8393bc418, 到 /Downloads 反差婊可爱眼镜学妹被猥琐男友带到酒店操小穴"""

# 当前的正则表达式
MAGNET_PATTERN = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+(?:[&?][^&\s\n]*?(?=(?:magnet:|$|[\s\n])))*'

print("=" * 80)
print("测试当前正则表达式")
print("=" * 80)

match = re.search(MAGNET_PATTERN, text_911, re.IGNORECASE)
if match:
    magnet_link = match.group(0)
    print(f"\n提取的磁力链接长度: {len(magnet_link)}")
    print(f"\n提取的磁力链接:\n{magnet_link}")

    # 提取dn参数
    if '&dn=' in magnet_link:
        dn_pos = magnet_link.find('dn=')
        dn_text = magnet_link[dn_pos + 3:].rstrip()
        amp_pos = dn_text.find('&')
        if amp_pos > 0:
            dn_text = dn_text[:amp_pos]
        dn_decoded = unquote(dn_text)
        print(f"\n提取的dn参数:\n{dn_decoded}")
else:
    print("未匹配到磁力链接")

print("\n" + "=" * 80)
print("测试改进的正则表达式（允许dn参数包含空格）")
print("=" * 80)

# 改进的正则表达式：dn参数可以包含空格，直到遇到换行或另一个magnet链接
IMPROVED_PATTERN = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+(?:&(?:dn=[^\n\r]*?(?=(?:\s+magnet:|$|[\n\r]))|[^&\s\n]+))*'

match2 = re.search(IMPROVED_PATTERN, text_911, re.IGNORECASE)
if match2:
    magnet_link2 = match2.group(0).rstrip()
    print(f"\n提取的磁力链接长度: {len(magnet_link2)}")
    print(f"\n提取的磁力链接:\n{magnet_link2}")

    # 提取dn参数
    if '&dn=' in magnet_link2:
        dn_pos = magnet_link2.find('dn=')
        dn_text = magnet_link2[dn_pos + 3:].rstrip()
        amp_pos = dn_text.find('&')
        if amp_pos > 0:
            dn_text = dn_text[:amp_pos]
        dn_decoded = unquote(dn_text)
        print(f"\n提取的dn参数:\n{dn_decoded}")
else:
    print("未匹配到磁力链接")
