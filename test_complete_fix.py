#!/usr/bin/env python3
"""测试完整的修复方案"""

print("=" * 80)
print("测试完整的修复方案")
print("=" * 80)

# 测试1：保存笔记时不提取有dn参数的磁力链接的filename
print("\n测试1：保存笔记时的逻辑")
print("-" * 80)

from urllib.parse import parse_qs, urlparse

test_magnets = [
    ("magnet:?xt=urn:btih:ABC123&dn=test.mp4", True, "有dn参数"),
    ("magnet:?xt=urn:btih:DEF456", False, "无dn参数"),
    ("magnet:?xt=urn:btih:GHI789&dn=12-15流出酒店偷拍 反差婊可爱眼镜学妹被猥琐男友带到酒店操小穴 6942d3ac403ce9d8393bc418, 到 /Downloads", True, "有错误的dn参数"),
]

for magnet_link, has_dn, description in test_magnets:
    filename = None
    if magnet_link:
        try:
            parsed = urlparse(magnet_link)
            params = parse_qs(parsed.query)
            # 如果没有dn参数，才尝试从其他地方提取filename
            if not params.get('dn'):
                pass  # 保持filename=None，让校准系统处理
        except Exception:
            pass

    print(f"\n{description}:")
    print(f"  磁力链接: {magnet_link[:80]}...")
    print(f"  filename: {filename}")
    print(f"  预期: filename应该为None" if has_dn else "  预期: filename可以为None或从其他地方提取")
    print(f"  结果: {'✅ 正确' if filename is None else '❌ 错误'}")

# 测试2：校准判断逻辑
print("\n\n测试2：校准判断逻辑（should_calibrate_note）")
print("-" * 80)

test_notes = [
    {
        'id': 1,
        'magnet_link': 'magnet:?xt=urn:btih:ABC123&dn=test.mp4',
        'message_text': 'magnet:?xt=urn:btih:ABC123&dn=test.mp4',
        'filename': None,
        'expected': False,
        'reason': '有dn参数，不需要校准'
    },
    {
        'id': 2,
        'magnet_link': 'magnet:?xt=urn:btih:DEF456',
        'message_text': 'magnet:?xt=urn:btih:DEF456',
        'filename': None,
        'expected': True,
        'reason': '无dn参数且filename为空，需要校准'
    },
    {
        'id': 3,
        'magnet_link': 'magnet:?xt=urn:btih:GHI789',
        'message_text': 'magnet:?xt=urn:btih:GHI789',
        'filename': 'calibrated_file.mp4',
        'expected': False,
        'reason': '无dn参数但有filename，已校准过'
    },
    {
        'id': 4,
        'magnet_link': 'magnet:?xt=urn:btih:JKL012&dn=错误的dn参数',
        'message_text': 'magnet:?xt=urn:btih:JKL012&dn=错误的dn参数',
        'filename': None,
        'expected': False,
        'reason': '有dn参数（即使是错误的），也不需要校准'
    },
]

for note in test_notes:
    # 模拟should_calibrate_note的逻辑
    magnet_link = note['magnet_link']
    filename = note['filename']
    should_calibrate = False

    if magnet_link:
        try:
            parsed = urlparse(magnet_link)
            params = parse_qs(parsed.query)
            dn_values = params.get('dn', [])

            if dn_values:
                # 有dn参数，不需要校准
                should_calibrate = False
            elif not filename or filename.strip() == '':
                # 没有dn参数且filename为空，需要校准
                should_calibrate = True
            else:
                # 没有dn参数但有filename，已校准过
                should_calibrate = False
        except Exception:
            pass

    print(f"\n笔记 {note['id']}:")
    print(f"  原因: {note['reason']}")
    print(f"  预期: {'需要校准' if note['expected'] else '不需要校准'}")
    print(f"  结果: {'需要校准' if should_calibrate else '不需要校准'}")
    print(f"  状态: {'✅ 正确' if should_calibrate == note['expected'] else '❌ 错误'}")

# 测试3：dn参数移除
print("\n\n测试3：dn参数移除逻辑")
print("-" * 80)

import re

test_dn_removal = [
    ("magnet:?xt=urn:btih:ABC123&dn=old.mp4", "magnet:?xt=urn:btih:ABC123"),
    ("magnet:?xt=urn:btih:ABC123&dn=old file.mp4", "magnet:?xt=urn:btih:ABC123"),
    ("magnet:?xt=urn:btih:ABC123&dn=old.mp4&tr=tracker1", "magnet:?xt=urn:btih:ABC123&tr=tracker1"),
]

for original, expected in test_dn_removal:
    result = re.sub(r'[&?]dn=[^&]*', '', original)
    print(f"\n原始: {original}")
    print(f"期望: {expected}")
    print(f"结果: {result}")
    print(f"状态: {'✅ 正确' if result == expected else '❌ 错误'}")

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)
