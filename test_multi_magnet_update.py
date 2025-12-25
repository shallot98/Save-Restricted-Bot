#!/usr/bin/env python3
"""
测试多条磁力链接更新逻辑
"""
import re
from urllib.parse import quote

def clean_filename(filename):
    """清理文件名"""
    if not filename:
        return ''
    cleaned = re.sub(r'<[^>]+>', '', filename)
    cleaned = re.split(r'[\s\r\n]*magnet:', cleaned, flags=re.IGNORECASE)[0]
    cleaned = re.sub(r'[\r\n]+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def test_multi_magnet_update():
    """测试多条磁力链接更新"""
    print("=" * 60)
    print("测试多条磁力链接更新逻辑")
    print("=" * 60)

    # 模拟849笔记的原始内容（3条磁力链接）
    original_text = """熟女空必备！丝袜熟女团队【未知姓名】系列  #合集
magnet:?xt=urn:btih:54FFCE3A29F67E33814243E734201A67221A73EB&dn=old1
magnet:?xt=urn:btih:ABC123DEF456789012345678901234567890ABCD&dn=old2
magnet:?xt=urn:btih:XYZ789GHI012345678901234567890123456WXYZ&dn=old3"""

    # 模拟校准结果
    calibrated_results = [
        {
            'success': True,
            'info_hash': '54FFCE3A29F67E33814243E734201A67221A73EB',
            'old_magnet': 'magnet:?xt=urn:btih:54FFCE3A29F67E33814243E734201A67221A73EB&dn=old1',
            'filename': '熟女空必备！丝袜熟女团队【未知姓名】系列01'
        },
        {
            'success': True,
            'info_hash': 'ABC123DEF456789012345678901234567890ABCD',
            'old_magnet': 'magnet:?xt=urn:btih:ABC123DEF456789012345678901234567890ABCD&dn=old2',
            'filename': '熟女空必备！丝袜熟女团队【未知姓名】系列02'
        },
        {
            'success': True,
            'info_hash': 'XYZ789GHI012345678901234567890123456WXYZ',
            'old_magnet': 'magnet:?xt=urn:btih:XYZ789GHI012345678901234567890123456WXYZ&dn=old3',
            'filename': '熟女空必备！丝袜熟女团队【未知姓名】系列03'
        }
    ]

    print("\n原始文本:")
    print(original_text)
    print()

    # 使用旧的正则（有问题的）
    print("=" * 60)
    print("测试旧的正则表达式（贪婪匹配）:")
    print("=" * 60)
    updated_text_old = original_text
    for result in calibrated_results:
        if not result.get('success'):
            continue

        info_hash = result['info_hash']
        raw_filename = result.get('filename', '')
        filename = clean_filename(raw_filename)

        new_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={filename}"

        # 旧的正则（贪婪匹配）
        magnet_pattern = rf'magnet:\?xt=urn:btih:{re.escape(info_hash)}(?:[&?][^\r\n]*)?'
        updated_text_old = re.sub(magnet_pattern, new_magnet, updated_text_old, flags=re.IGNORECASE)

    print("\n更新后的文本:")
    print(updated_text_old)

    # 统计磁力链接数量
    magnet_count_old = len(re.findall(r'magnet:\?xt=urn:btih:', updated_text_old, re.IGNORECASE))
    print(f"\n磁力链接数量: {magnet_count_old}")
    if magnet_count_old == 3:
        print("✅ 旧正则测试通过（保留了3条磁力链接）")
    else:
        print(f"❌ 旧正则测试失败（只剩{magnet_count_old}条磁力链接）")

    # 使用新的正则（修复后的）
    print("\n" + "=" * 60)
    print("测试新的正则表达式（非贪婪匹配）:")
    print("=" * 60)
    updated_text_new = original_text
    for result in calibrated_results:
        if not result.get('success'):
            continue

        info_hash = result['info_hash']
        raw_filename = result.get('filename', '')
        filename = clean_filename(raw_filename)

        new_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={filename}"

        # 新的正则（非贪婪匹配，使用负向前瞻）
        magnet_pattern = rf'magnet:\?xt=urn:btih:{re.escape(info_hash)}(?:[&?](?:(?!magnet:)[^\r\n])*)?'
        updated_text_new = re.sub(magnet_pattern, new_magnet, updated_text_new, flags=re.IGNORECASE)

    print("\n更新后的文本:")
    print(updated_text_new)

    # 统计磁力链接数量
    magnet_count_new = len(re.findall(r'magnet:\?xt=urn:btih:', updated_text_new, re.IGNORECASE))
    print(f"\n磁力链接数量: {magnet_count_new}")
    if magnet_count_new == 3:
        print("✅ 新正则测试通过（保留了3条磁力链接）")
    else:
        print(f"❌ 新正则测试失败（只剩{magnet_count_new}条磁力链接）")

    print("\n" + "=" * 60)
    print("测试总结:")
    print("=" * 60)
    print(f"旧正则: {magnet_count_old}条磁力链接")
    print(f"新正则: {magnet_count_new}条磁力链接")

    if magnet_count_new == 3 and magnet_count_old < 3:
        print("\n✅ 修复成功！新正则解决了贪婪匹配问题")
        return True
    else:
        print("\n❌ 修复失败")
        return False

if __name__ == '__main__':
    import sys
    success = test_multi_magnet_update()
    sys.exit(0 if success else 1)
