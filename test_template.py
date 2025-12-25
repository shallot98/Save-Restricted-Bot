#!/usr/bin/env python3
"""测试模板渲染"""

from flask import Flask, render_template
from database import get_notes, init_database

app = Flask(__name__)
init_database()

# 获取笔记
notes = get_notes(limit=10)

# 找到多图片笔记
multi_image_note = None
for note in notes:
    if note.get('media_paths') and len(note.get('media_paths', [])) > 1:
        multi_image_note = note
        break

if multi_image_note:
    print(f"找到多图片笔记 ID: {multi_image_note['id']}")
    print(f"media_paths 类型: {type(multi_image_note['media_paths'])}")
    print(f"media_paths 内容: {multi_image_note['media_paths']}")
    print(f"media_paths 长度: {len(multi_image_note['media_paths'])}")
    print(f"\n条件判断:")
    print(f"  note.media_paths: {bool(multi_image_note.get('media_paths'))}")
    print(f"  note.media_paths|length > 0: {len(multi_image_note.get('media_paths', [])) > 0}")
    print(f"  note.media_paths|length > 1: {len(multi_image_note.get('media_paths', [])) > 1}")
else:
    print("未找到多图片笔记")
