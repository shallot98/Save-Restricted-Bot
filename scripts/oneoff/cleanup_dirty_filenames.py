#!/usr/bin/env python3
"""
清理数据库中的脏数据
修复filename和message_text字段中包含<br>magnet:的问题
"""
import sys
import os
import re
from urllib.parse import quote

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db_connection

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

def cleanup_database(dry_run=True):
    """清理数据库中的脏数据

    Args:
        dry_run: 如果为True，只显示需要清理的数据，不实际修改
    """
    print("=" * 60)
    print("数据库清理脚本")
    print("=" * 60)

    if dry_run:
        print("\n⚠️  DRY RUN 模式 - 不会实际修改数据库")
    else:
        print("\n⚠️  实际修改模式 - 将修改数据库")

    print("\n正在扫描数据库...")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 查找所有包含<br>或magnet:的filename
        cursor.execute('''
            SELECT id, filename, message_text, magnet_link
            FROM notes
            WHERE filename IS NOT NULL
            AND (filename LIKE '%<br>%' OR filename LIKE '%magnet:%')
        ''')

        dirty_notes = cursor.fetchall()

        if not dirty_notes:
            print("\n✅ 没有发现需要清理的数据")
            return

        print(f"\n发现 {len(dirty_notes)} 条需要清理的笔记")
        print("\n" + "=" * 60)

        cleaned_count = 0

        for note_id, filename, message_text, magnet_link in dirty_notes:
            print(f"\n笔记ID: {note_id}")
            print(f"原始filename: {filename[:100]}...")

            # 清理filename
            cleaned_filename = clean_filename(filename)
            print(f"清理后filename: {cleaned_filename[:100]}...")

            # 清理message_text中的磁力链接
            cleaned_message_text = message_text
            if message_text:
                # 提取info_hash
                hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', magnet_link, re.IGNORECASE)
                if hash_match:
                    info_hash = hash_match.group(1)

                    # 构建新的磁力链接（使用清理后的文件名）
                    new_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={cleaned_filename}"

                    # 替换message_text中的磁力链接
                    magnet_pattern = rf'magnet:\?xt=urn:btih:{re.escape(info_hash)}(?:[&?][^\r\n]*)?'
                    cleaned_message_text = re.sub(magnet_pattern, new_magnet, message_text, flags=re.IGNORECASE)

                    if cleaned_message_text != message_text:
                        print(f"message_text已更新")

            # 更新magnet_link字段
            cleaned_magnet_link = magnet_link
            if magnet_link:
                hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', magnet_link, re.IGNORECASE)
                if hash_match:
                    info_hash = hash_match.group(1)
                    # 重新构建磁力链接（URL编码）
                    cleaned_magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={quote(cleaned_filename)}"

                    if cleaned_magnet_link != magnet_link:
                        print(f"magnet_link已更新")

            if not dry_run:
                # 实际更新数据库
                cursor.execute('''
                    UPDATE notes
                    SET filename = ?, message_text = ?, magnet_link = ?
                    WHERE id = ?
                ''', (cleaned_filename, cleaned_message_text, cleaned_magnet_link, note_id))
                cleaned_count += 1
                print(f"✅ 已更新")
            else:
                print(f"⏭️  跳过（DRY RUN模式）")

        if not dry_run:
            conn.commit()
            print("\n" + "=" * 60)
            print(f"✅ 成功清理 {cleaned_count} 条笔记")
        else:
            print("\n" + "=" * 60)
            print(f"⏭️  DRY RUN完成，发现 {len(dirty_notes)} 条需要清理的笔记")
            print(f"   运行 python3 cleanup_dirty_filenames.py --apply 来实际修改数据库")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='清理数据库中的脏数据')
    parser.add_argument('--apply', action='store_true', help='实际修改数据库（默认为dry-run模式）')
    args = parser.parse_args()

    try:
        cleanup_database(dry_run=not args.apply)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
