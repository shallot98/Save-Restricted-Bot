#!/usr/bin/env python3
"""
测试849笔记的实际情况
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

def test_849_case():
    """测试849笔记的实际情况"""
    print("=" * 60)
    print("测试849笔记的实际情况")
    print("=" * 60)

    # 849笔记的原始内容（3条磁力链接在同一行，用空格分隔）
    original_text = """熟女空必备！丝袜熟女团队【未知姓名】系列  #合集                                                                                                                     magnet:?xt=urn:btih:54ffce3a29f67e33814243e734201a67221a73eb&dn=%E7%86%9F%E5%A5%B3%E7%A9%BA%E5%BF%85%E5%A4%87%EF%BC%81%E4%B8%9D%E8%A2%9C%E7%86%9F%E5%A5%B3%E5%9B%A2%E9%98%9F%E3%80%90%E6%9C%AA%E7%9F%A5%E5%A7%93%E5%90%8D%E3%80%91%E7%B3%BB%E5%88%9701 magnet:?xt=urn:btih:abc123def456&dn=file02 magnet:?xt=urn:btih:xyz789ghi012&dn=file03"""

    print("\n原始文本:")
    print(original_text)
    print()

    # 统计原始磁力链接数量
    magnet_count_original = len(re.findall(r'magnet:\?xt=urn:btih:', original_text, re.IGNORECASE))
    print(f"原始磁力链接数量: {magnet_count_original}")

    # 模拟校准结果（假设校准成功，文件名很长）
    calibrated_results = [
        {
            'success': True,
            'info_hash': '54FFCE3A29F67E33814243E734201A67221A73EB',
            'old_magnet': 'magnet:?xt=urn:btih:54ffce3a29f67e33814243e734201a67221a73eb&dn=%E7%86%9F%E5%A5%B3%E7%A9%BA%E5%BF%85%E5%A4%87%EF%BC%81%E4%B8%9D%E8%A2%9C%E7%86%9F%E5%A5%B3%E5%9B%A2%E9%98%9F%E3%80%90%E6%9C%AA%E7%9F%A5%E5%A7%93%E5%90%8D%E3%80%91%E7%B3%BB%E5%88%9701',
            'filename': '01 magnet:?xt=urn:btih:abc123def456&dn=file02 magnet:?xt=urn:btih:xyz789ghi012&dn=file03'  # 校准脚本返回的文件名包含了后面的磁力链接
        }
    ]

    print("\n模拟校准结果:")
    print(f"  filename: {calibrated_results[0]['filename']}")
    print()

    # 清理文件名
    cleaned_filename = clean_filename(calibrated_results[0]['filename'])
    print(f"清理后的filename: {cleaned_filename}")
    print()

    # 使用旧的正则更新
    print("=" * 60)
    print("使用旧正则更新:")
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
        print(f"正则模式: {magnet_pattern}")
        updated_text_old = re.sub(magnet_pattern, new_magnet, updated_text_old, flags=re.IGNORECASE)

    print("\n更新后的文本:")
    print(updated_text_old)

    # 统计磁力链接数量
    magnet_count_old = len(re.findall(r'magnet:\?xt=urn:btih:', updated_text_old, re.IGNORECASE))
    print(f"\n磁力链接数量: {magnet_count_old}")

    # 使用新的正则更新
    print("\n" + "=" * 60)
    print("使用新正则更新:")
    print("=" * 60)
    updated_text_new = original_text
    for result in calibrated_results:
        if not result.get('success'):
            continue

        info_hash = result['info_hash']
        raw_filename = result.get('filename', '')
        filename = clean_filename(raw_filename)

        new_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={filename}"

        # 新的正则（非贪婪匹配）
        magnet_pattern = rf'magnet:\?xt=urn:btih:{re.escape(info_hash)}(?:[&?](?:(?!magnet:)[^\r\n])*)?'
        print(f"正则模式: {magnet_pattern}")
        updated_text_new = re.sub(magnet_pattern, new_magnet, updated_text_new, flags=re.IGNORECASE)

    print("\n更新后的文本:")
    print(updated_text_new)

    # 统计磁力链接数量
    magnet_count_new = len(re.findall(r'magnet:\?xt=urn:btih:', updated_text_new, re.IGNORECASE))
    print(f"\n磁力链接数量: {magnet_count_new}")

    print("\n" + "=" * 60)
    print("测试总结:")
    print("=" * 60)
    print(f"原始: {magnet_count_original}条磁力链接")
    print(f"旧正则: {magnet_count_old}条磁力链接")
    print(f"新正则: {magnet_count_new}条磁力链接")

    if magnet_count_new == magnet_count_original and magnet_count_old < magnet_count_original:
        print("\n✅ 修复成功！新正则解决了贪婪匹配问题")
        return True
    elif magnet_count_new == magnet_count_original and magnet_count_old == magnet_count_original:
        print("\n⚠️ 两个正则都保留了所有磁力链接，问题可能在其他地方")
        return False
    else:
        print("\n❌ 修复失败")
        return False

if __name__ == '__main__':
    import sys
    success = test_849_case()
    sys.exit(0 if success else 1)
