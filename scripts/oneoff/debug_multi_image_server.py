#!/usr/bin/env python3
"""
创建一个简单的调试页面来显示多图片笔记
不需要登录,直接查看数据
"""

import sys
import json
sys.path.insert(0, '/root/Save-Restricted-Bot')

import sqlite3
from flask import Flask, render_template_string

app = Flask(__name__)

# 简化的笔记卡片模板
CARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>多图片笔记调试</title>
    <script src="https://cdn.tailwindcss.com/3.4.1"></script>
    <style>
        .line-clamp-3 {
            display: -webkit-box;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 3;
            overflow: hidden;
        }
    </style>
</head>
<body class="bg-gray-50 p-8">
    <h1 class="text-3xl font-bold mb-6">多图片笔记调试页面</h1>
    <p class="mb-4 text-gray-600">数据库中共有 {{ total_notes }} 条笔记,其中 {{ multi_image_count }} 条是多图片笔记</p>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {% for note in notes %}
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            <!-- 图片区域 -->
            {% if note.media_paths and note.media_paths|length > 0 %}
            <div class="relative aspect-video bg-gray-100">
                <img src="/media/{{ note.media_paths[0] }}"
                     alt="Note image"
                     loading="lazy"
                     class="w-full h-full object-cover"
                     onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22400%22 height=%22300%22%3E%3Crect fill=%22%23ddd%22 width=%22400%22 height=%22300%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 fill=%22%23999%22%3E图片加载失败%3C/text%3E%3C/svg%3E'">

                {% if note.media_paths|length > 1 %}
                <div class="absolute top-2 right-2 bg-black bg-opacity-60 text-white text-xs px-2 py-1 rounded">
                    📷 {{ note.media_paths|length }}
                </div>
                {% endif %}
            </div>
            {% endif %}

            <!-- 内容 -->
            <div class="p-4">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-medium text-blue-600 bg-blue-100 px-2 py-1 rounded">
                        {{ note.source_name or note.source_chat_id }}
                    </span>
                    <span class="text-xs text-gray-500">#{{ note.id }}</span>
                </div>

                {% if note.message_text %}
                <p class="text-sm text-gray-700 line-clamp-3 mb-2">
                    {{ note.message_text }}
                </p>
                {% endif %}

                <div class="text-xs text-gray-500">
                    🕒 {{ note.timestamp }}
                </div>

                <!-- 调试信息 -->
                <div class="mt-2 pt-2 border-t border-gray-100 text-xs text-gray-500">
                    <div>媒体类型: {{ note.media_type }}</div>
                    <div>media_paths 数量: {{ note.media_paths|length if note.media_paths else 0 }}</div>
                    {% if note.media_paths %}
                    <details class="mt-1">
                        <summary class="cursor-pointer text-blue-600">查看所有图片路径</summary>
                        <ul class="mt-1 ml-4 list-disc">
                        {% for path in note.media_paths %}
                            <li>{{ path }}</li>
                        {% endfor %}
                        </ul>
                    </details>
                    {% endif %}
                </div>
            </div>
        </div>
    {% endfor %}
    </div>
</body>
</html>
"""

@app.route('/debug')
def debug_notes():
    conn = sqlite3.connect('/root/Save-Restricted-Bot/data/notes.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取前30条笔记
    cursor.execute('SELECT * FROM notes ORDER BY timestamp DESC LIMIT 30')
    rows = cursor.fetchall()

    notes = []
    multi_image_count = 0

    for row in rows:
        row_dict = dict(row)

        # 解析 media_paths
        media_paths = []
        if row_dict.get('media_paths'):
            try:
                media_paths = json.loads(row_dict['media_paths'])
            except:
                pass

        # 回退到单个 media_path
        if not media_paths and row_dict.get('media_path'):
            media_paths = [row_dict['media_path']]

        note_data = {
            'id': row_dict['id'],
            'source_chat_id': row_dict['source_chat_id'],
            'source_name': row_dict.get('source_name'),
            'message_text': row_dict.get('message_text'),
            'timestamp': row_dict.get('timestamp'),
            'media_type': row_dict.get('media_type'),
            'media_paths': media_paths,
        }

        if len(media_paths) > 1:
            multi_image_count += 1

        notes.append(note_data)

    conn.close()

    return render_template_string(
        CARD_TEMPLATE,
        notes=notes,
        total_notes=len(notes),
        multi_image_count=multi_image_count
    )

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("多图片笔记调试服务器")
    print("=" * 80)
    print("\n访问 http://localhost:5556/debug 查看多图片笔记")
    print("\n按 Ctrl+C 停止服务器\n")
    app.run(host='0.0.0.0', port=5556, debug=False)
