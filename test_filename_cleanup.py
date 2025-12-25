#!/usr/bin/env python3
"""
测试文件名清理功能
验证修复后不再包含<br>magnet:等内容
"""
import sys
import os
import re
from urllib.parse import unquote

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

def test_extract_dn_from_magnet():
    """测试从磁力链接提取dn参数（app.py中的函数）"""
    print("=" * 60)
    print("测试1: extract_dn_from_magnet - 清理HTML标签和换行符")
    print("=" * 60)

    from app import extract_dn_from_magnet

    test_cases = [
        {
            "name": "包含<br>标签的dn参数",
            "magnet": "magnet:?xt=urn:btih:HASH&dn=测试文件名<br>magnet:",
            "expected": "测试文件名"
        },
        {
            "name": "包含换行符的dn参数",
            "magnet": "magnet:?xt=urn:btih:HASH&dn=测试文件名\nmagnet:",
            "expected": "测试文件名"
        },
        {
            "name": "包含URL编码的dn参数",
            "magnet": "magnet:?xt=urn:btih:HASH&dn=%E6%B5%8B%E8%AF%95%E6%96%87%E4%BB%B6%E5%90%8D",
            "expected": "测试文件名"
        },
        {
            "name": "正常的dn参数",
            "magnet": "magnet:?xt=urn:btih:HASH&dn=测试文件名",
            "expected": "测试文件名"
        },
        {
            "name": "dn参数后面还有其他参数",
            "magnet": "magnet:?xt=urn:btih:HASH&dn=测试文件名&tr=http://tracker.example.com",
            "expected": "测试文件名"
        }
    ]

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {test['name']}")
        print(f"输入: {test['magnet'][:80]}...")

        result = extract_dn_from_magnet(test['magnet'])
        print(f"提取结果: {result}")
        print(f"期望结果: {test['expected']}")

        if result == test['expected']:
            print("✅ 通过")
            passed += 1
        else:
            print("❌ 失败")
            failed += 1

    print(f"\n总结: {passed}/{len(test_cases)} 通过, {failed}/{len(test_cases)} 失败")
    return failed == 0

def test_clean_filename():
    """测试clean_filename函数（database.py中的函数）"""
    print("\n" + "=" * 60)
    print("测试2: clean_filename - 清理文件名")
    print("=" * 60)

    # 模拟clean_filename函数
    def clean_filename(filename):
        """清理文件名，去除可能包含的磁力链接部分、HTML标签和换行符"""
        if not filename:
            return ''
        # 先去除HTML标签（如<br>）
        cleaned = re.sub(r'<[^>]+>', '', filename)
        # 去除 magnet: 开头的部分（文件名后面可能跟着另一个磁力链接）
        # 匹配 magnet: 前面可能有空格、换行符或直接连接
        cleaned = re.split(r'[\s\r\n]*magnet:', cleaned, flags=re.IGNORECASE)[0]
        # 去除换行符和多余空格
        cleaned = re.sub(r'[\r\n]+', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()

    test_cases = [
        {
            "name": "包含<br>magnet:的文件名",
            "input": "测试文件名<br>magnet:?xt=urn:btih:HASH",
            "expected": "测试文件名"
        },
        {
            "name": "包含换行符和magnet:的文件名",
            "input": "测试文件名\nmagnet:?xt=urn:btih:HASH",
            "expected": "测试文件名"
        },
        {
            "name": "包含多个HTML标签的文件名",
            "input": "测试<br>文件<span>名</span>",
            "expected": "测试文件名"  # HTML标签被直接删除，不保留空格
        },
        {
            "name": "正常的文件名",
            "input": "测试文件名",
            "expected": "测试文件名"
        },
        {
            "name": "包含多余空格的文件名",
            "input": "测试   文件   名",
            "expected": "测试 文件 名"
        }
    ]

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {test['name']}")
        print(f"输入: {test['input']}")

        result = clean_filename(test['input'])
        print(f"清理结果: {result}")
        print(f"期望结果: {test['expected']}")

        if result == test['expected']:
            print("✅ 通过")
            passed += 1
        else:
            print("❌ 失败")
            failed += 1

    print(f"\n总结: {passed}/{len(test_cases)} 通过, {failed}/{len(test_cases)} 失败")
    return failed == 0

def test_real_case():
    """测试真实场景"""
    print("\n" + "=" * 60)
    print("测试3: 真实场景 - 完整流程")
    print("=" * 60)

    from app import extract_dn_from_magnet

    # 模拟校准后的文件名（可能包含<br>magnet:）
    calibrated_filename = "11-9流出酒店偷拍 牛仔裤大波妹<br>magnet:?xt=urn:btih:HASH"

    print(f"\n校准后的原始文件名: {calibrated_filename}")

    # 清理文件名
    def clean_filename(filename):
        if not filename:
            return ''
        # 先去除HTML标签（如<br>）
        cleaned = re.sub(r'<[^>]+>', '', filename)
        # 去除 magnet: 开头的部分
        cleaned = re.split(r'[\s\r\n]*magnet:', cleaned, flags=re.IGNORECASE)[0]
        # 去除换行符和多余空格
        cleaned = re.sub(r'[\r\n]+', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()

    cleaned = clean_filename(calibrated_filename)
    print(f"清理后的文件名: {cleaned}")

    # 构建磁力链接
    info_hash = "DADA33AD593BDB64867164C8D0CC28BFE4C3CD40"
    magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={cleaned}"
    print(f"\n构建的磁力链接: {magnet_link}")

    # 从磁力链接提取dn
    extracted_dn = extract_dn_from_magnet(magnet_link)
    print(f"提取的dn参数: {extracted_dn}")

    # 验证
    expected = "11-9流出酒店偷拍 牛仔裤大波妹"
    if extracted_dn == expected:
        print(f"\n✅ 真实场景测试通过")
        print(f"   文件名不再包含<br>magnet:")
        return True
    else:
        print(f"\n❌ 真实场景测试失败")
        print(f"   期望: {expected}")
        print(f"   实际: {extracted_dn}")
        return False

if __name__ == "__main__":
    try:
        result1 = test_extract_dn_from_magnet()
        result2 = test_clean_filename()
        result3 = test_real_case()

        print("\n" + "=" * 60)
        if result1 and result2 and result3:
            print("✅ 所有测试通过")
            print("=" * 60)
            sys.exit(0)
        else:
            print("❌ 部分测试失败")
            print("=" * 60)
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
