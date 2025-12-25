#!/usr/bin/env python3
"""
测试前端模板渲染 - 检查 media_paths 是否正确传递到模板
"""

import json

# 模拟笔记数据(从数据库来的)
note = {
    'id': 127,
    'media_type': 'photo',
    'media_path': 'webdav:693_0_20251114_224009.jpg',
    'media_paths': ['webdav:693_0_20251114_224009.jpg', 'webdav:694_1_20251114_224009.jpg'],
    'message_text': '测试多图片笔记',
    'source_name': '测试来源',
    'timestamp': '2024-11-14 22:40:09',
    'is_favorite': False,
}

print("=" * 80)
print("模板渲染测试 - 多图片笔记")
print("=" * 80)

print(f"\n笔记数据:")
print(f"  ID: {note['id']}")
print(f"  media_type: {note['media_type']}")
print(f"  media_path: {note['media_path']}")
print(f"  media_paths: {note['media_paths']}")
print(f"  图片数量: {len(note['media_paths'])}")

# 模拟 Jinja2 模板条件判断
print("\n模板条件判断:")
print(f"  note.media_paths 存在: {bool(note.get('media_paths'))}")
print(f"  note.media_paths 长度 > 0: {len(note.get('media_paths', [])) > 0}")
print(f"  note.media_paths 长度 > 1: {len(note.get('media_paths', [])) > 1}")

# 模拟模板渲染逻辑
if note.get('media_paths') and len(note['media_paths']) > 0:
    print("\n✅ 应该渲染多图片区域")
    print(f"   第一张图片: /media/{note['media_paths'][0]}")

    if len(note['media_paths']) > 1:
        print(f"   ✅ 应该显示图片数量标记: 📷 {len(note['media_paths'])}")
        print(f"   画廊图片列表: {json.dumps(note['media_paths'])}")
    else:
        print("   ⚠️  只有一张图片,不显示数量标记")

elif note.get('media_type') == 'photo':
    print(f"\n⚠️  使用旧的 media_path: {note['media_path']}")
else:
    print("\n❌ 不渲染图片")

print("\n" + "=" * 80)
print("检查 media_paths 的类型")
print("=" * 80)

media_paths = note.get('media_paths')
print(f"类型: {type(media_paths)}")
print(f"是列表: {isinstance(media_paths, list)}")
print(f"长度: {len(media_paths) if isinstance(media_paths, list) else 'N/A'}")

if isinstance(media_paths, list):
    for i, path in enumerate(media_paths):
        print(f"  [{i}] {path} (类型: {type(path)})")
