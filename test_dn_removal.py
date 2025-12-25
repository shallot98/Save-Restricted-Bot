#!/usr/bin/env python3
"""测试dn参数移除逻辑"""

import re

# 测试用例
test_cases = [
    # 简单的dn参数
    ("magnet:?xt=urn:btih:ABC123&dn=test.mp4", "magnet:?xt=urn:btih:ABC123"),
    # dn参数后面还有其他参数
    ("magnet:?xt=urn:btih:ABC123&dn=test.mp4&tr=tracker1", "magnet:?xt=urn:btih:ABC123&tr=tracker1"),
    # dn参数包含空格
    ("magnet:?xt=urn:btih:ABC123&dn=test file.mp4", "magnet:?xt=urn:btih:ABC123"),
    # dn参数包含特殊字符（URL编码）
    ("magnet:?xt=urn:btih:ABC123&dn=%E6%B5%8B%E8%AF%95.mp4", "magnet:?xt=urn:btih:ABC123"),
]

print("=" * 80)
print("测试dn参数移除")
print("=" * 80)

# 方法1：简单的正则（当前的问题方法）
pattern1 = r'[&?]dn=[^&]*'

print("\n方法1：r'[&?]dn=[^&]*'")
for original, expected in test_cases:
    result = re.sub(pattern1, '', original)
    status = "✅" if result == expected else "❌"
    print(f"{status} {original}")
    print(f"   期望: {expected}")
    print(f"   结果: {result}")

# 方法2：更精确的正则
# 匹配 &dn= 或 ?dn= 后面的所有内容，直到遇到 & 或字符串结束
pattern2 = r'[&?]dn=[^&]*'

print("\n方法2：r'[&?]dn=[^&]*' (same as 方法1)")
for original, expected in test_cases:
    result = re.sub(pattern2, '', original)
    status = "✅" if result == expected else "❌"
    print(f"{status} {original}")
    print(f"   期望: {expected}")
    print(f"   结果: {result}")

# 方法3：使用urlparse重新构建
from urllib.parse import urlparse, parse_qs, urlencode

print("\n方法3：使用urlparse重新构建")
for original, expected in test_cases:
    try:
        parsed = urlparse(original)
        params = parse_qs(parsed.query)
        # 移除dn参数
        params.pop('dn', None)
        # 重新构建query
        new_query = urlencode(params, doseq=True)
        result = f"{parsed.scheme}:{parsed.path}"
        if new_query:
            result += f"?{new_query}"
        status = "✅" if result == expected else "❌"
        print(f"{status} {original}")
        print(f"   期望: {expected}")
        print(f"   结果: {result}")
    except Exception as e:
        print(f"❌ {original}")
        print(f"   错误: {e}")
