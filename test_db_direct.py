#!/usr/bin/env python3
"""
直接测试笔记服务返回的数据
"""

import sys
import json
sys.path.insert(0, '/root/Save-Restricted-Bot')

# 直接从数据库加载笔记
import sqlite3

conn = sqlite3.connect('/root/Save-Restricted-Bot/data/notes.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 获取前20条笔记
cursor.execute('SELECT * FROM notes ORDER BY timestamp DESC LIMIT 20')
rows = cursor.fetchall()

print("=" * 80)
print(f"数据库中的笔记 (前20条)")
print("=" * 80)

multi_image_count = 0

for row in rows:
    row_dict = dict(row)
    note_id = row_dict['id']
    media_type = row_dict.get('media_type')
    media_path = row_dict.get('media_path')
    media_paths_str = row_dict.get('media_paths')

    # 解析 media_paths
    media_paths = []
    if media_paths_str:
        try:
            media_paths = json.loads(media_paths_str)
        except:
            pass

    # 打印笔记信息
    if media_paths or media_path:
        img_count = len(media_paths) if media_paths else 1
        print(f"\n笔记 #{note_id}:")
        print(f"  媒体类型: {media_type}")
        print(f"  media_path: {media_path}")
        print(f"  media_paths: {media_paths}")
        print(f"  图片数量: {img_count}")

        if len(media_paths) > 1:
            multi_image_count += 1
            print(f"  ✅ 多图片笔记")

conn.close()

print("\n" + "=" * 80)
print(f"前20条笔记中有 {multi_image_count} 条多图片笔记")
print("=" * 80)
