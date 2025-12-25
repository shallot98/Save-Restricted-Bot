#!/usr/bin/env python3
"""
测试重构后的功能
1. 测试磁力链接dn参数提取（dn=后面的文本到行结束）
2. 测试机器人回复解析（冒号到第一个逗号）
3. 测试校准后磁力链接补全
"""
import sys
import os
import re
from urllib.parse import quote, unquote

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

def test_extract_magnet_link():
    """测试磁力链接提取功能"""
    print("=" * 60)
    print("测试1: 磁力链接dn参数提取")
    print("=" * 60)

    from database import _extract_magnet_link

    # 测试用例1: 磁力链接中已有dn参数
    test_cases = [
        {
            "name": "已有dn参数（未编码）",
            "input": "magnet:?xt=urn:btih:DADA33AD593BDB64867164C8D0CC28BFE4C3CD40&dn=11-9流出酒店偷拍 牛仔裤大波妹",
            "expected_dn": "11-9流出酒店偷拍 牛仔裤大波妹"
        },
        {
            "name": "已有dn参数（URL编码）",
            "input": "magnet:?xt=urn:btih:DADA33AD593BDB64867164C8D0CC28BFE4C3CD40&dn=11-9%E6%B5%81%E5%87%BA%E9%85%92%E5%BA%97",
            "expected_dn": "11-9流出酒店"
        },
        {
            "name": "没有dn参数，从文本开头提取（文本开头不是#）",
            "input": "11-9流出酒店偷拍 牛仔裤大波妹\n#日期20251112\nmagnet:?xt=urn:btih:DADA33AD593BDB64867164C8D0CC28BFE4C3CD40",
            "expected_dn": "11-9流出酒店偷拍 牛仔裤大波妹"
        },
        {
            "name": "dn参数后面还有其他参数",
            "input": "magnet:?xt=urn:btih:DADA33AD593BDB64867164C8D0CC28BFE4C3CD40&dn=测试文件名&tr=http://tracker.example.com",
            "expected_dn": "测试文件名"
        }
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {test['name']}")
        print(f"输入: {test['input'][:100]}...")

        result = _extract_magnet_link(test['input'])
        if result:
            # 提取dn参数
            dn_match = re.search(r'[&?]dn=([^&]+)', result)
            if dn_match:
                dn_decoded = unquote(dn_match.group(1))
                print(f"提取的dn: {dn_decoded}")
                print(f"期望的dn: {test['expected_dn']}")
                if dn_decoded == test['expected_dn']:
                    print("✅ 通过")
                else:
                    print("❌ 失败")
            else:
                print("❌ 未找到dn参数")
        else:
            print("❌ 未提取到磁力链接")

def test_bot_reply_parsing():
    """测试机器人回复解析功能"""
    print("\n" + "=" * 60)
    print("测试2: 机器人回复解析（冒号到第一个逗号）")
    print("=" * 60)

    test_cases = [
        {
            "name": "标准格式",
            "input": "离线任务已添加: 11-9流出酒店偷拍 牛仔裤大波妹, DADA33AD593BDB64867164C8D0CC28BFE4C3CD40, 到 /Downloads",
            "expected": "11-9流出酒店偷拍 牛仔裤大波妹"
        },
        {
            "name": "没有逗号",
            "input": "离线任务已添加: 测试文件名",
            "expected": "测试文件名"
        },
        {
            "name": "多个逗号",
            "input": "离线任务已添加: 文件名,包含,逗号, hash值, 到 /Downloads",
            "expected": "文件名"
        },
        {
            "name": "没有冒号",
            "input": "测试文件名",
            "expected": "测试文件名"
        }
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {test['name']}")
        print(f"输入: {test['input']}")

        # 模拟calibrate_bot_helper.py中的解析逻辑
        text = test['input']
        first_line = text.split('\n')[0].strip()

        # 查找冒号位置
        colon_pos = first_line.find(':')
        if colon_pos >= 0:
            # 提取冒号后的内容
            after_colon = first_line[colon_pos + 1:].strip()

            # 查找第一个逗号位置
            comma_pos = after_colon.find(',')
            if comma_pos > 0:
                # 提取冒号到第一个逗号之间的内容
                filename = after_colon[:comma_pos].strip()
            else:
                # 如果没有逗号，返回冒号后的全部内容
                filename = after_colon.strip()
        else:
            # 如果没有冒号，返回整行内容
            filename = first_line.strip()

        print(f"提取的文件名: {filename}")
        print(f"期望的文件名: {test['expected']}")
        if filename == test['expected']:
            print("✅ 通过")
        else:
            print("❌ 失败")

def test_magnet_completion():
    """测试校准后磁力链接补全功能"""
    print("\n" + "=" * 60)
    print("测试3: 校准后磁力链接补全")
    print("=" * 60)

    # 模拟校准结果
    calibrated_results = [
        {
            'info_hash': 'DADA33AD593BDB64867164C8D0CC28BFE4C3CD40',
            'old_magnet': 'magnet:?xt=urn:btih:DADA33AD593BDB64867164C8D0CC28BFE4C3CD40&dn=1',
            'filename': '11-9流出酒店偷拍 牛仔裤大波妹和男友深夜幽会操逼的时候妹子不知为何哭了',
            'success': True
        }
    ]

    # 原始笔记文本
    original_text = """#日期20251112 #22716083 #酒店偷拍 11-9流出酒店偷拍 牛仔裤大波妹和男友深夜幽会操逼的时候妹子不知为何哭了

#磁力链接
magnet:?xt=urn:btih:DADA33AD593BDB64867164C8D0CC28BFE4C3CD40&dn=1"""

    print(f"\n原始文本:\n{original_text}")

    # 模拟update_note_with_calibrated_dns的逻辑
    updated_text = original_text
    for result in calibrated_results:
        if not result.get('success'):
            continue

        info_hash = result['info_hash']
        filename = result.get('filename', '')

        # 构建新的磁力链接（message_text中不需要URL编码，保持可读性）
        new_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={filename}"

        # 匹配磁力链接到行尾
        magnet_pattern = rf'magnet:\?xt=urn:btih:{re.escape(info_hash)}(?:[&?][^\r\n]*)?'
        updated_text = re.sub(magnet_pattern, new_magnet, updated_text, flags=re.IGNORECASE)

    print(f"\n更新后文本:\n{updated_text}")

    # 验证是否正确补全
    expected_magnet = f"magnet:?xt=urn:btih:DADA33AD593BDB64867164C8D0CC28BFE4C3CD40&dn={calibrated_results[0]['filename']}"
    if expected_magnet in updated_text:
        print("\n✅ 磁力链接补全成功")
    else:
        print("\n❌ 磁力链接补全失败")

if __name__ == "__main__":
    try:
        test_extract_magnet_link()
        test_bot_reply_parsing()
        test_magnet_completion()

        print("\n" + "=" * 60)
        print("所有测试完成")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
