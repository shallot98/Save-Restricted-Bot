#!/usr/bin/env python3
"""
集成测试 - 检查 Flask 路由返回的实际数据
"""

import os
os.environ['PORT'] = '5555'  # 使用测试端口

from web import create_app
from flask import url_for

app = create_app()

with app.test_client() as client:
    print("=" * 80)
    print("Flask路由测试 - 获取笔记列表")
    print("=" * 80)

    # 先登录
    from config import load_config
    cfg = load_config()
    login_response = client.post('/login', data={
        'password': cfg.get('admin_password', 'admin')
    }, follow_redirects=False)

    print(f"\n登录状态码: {login_response.status_code}")

    # 请求笔记列表
    response = client.get('/notes', follow_redirects=True)

    print(f"\n响应状态码: {response.status_code}")

    if response.status_code == 200:
        html = response.data.decode('utf-8')

        # 保存HTML到文件以便检查
        with open('/tmp/notes_page.html', 'w') as f:
            f.write(html)
        print("\n✅ HTML已保存到 /tmp/notes_page.html")

        # 检查是否有笔记
        import re
        note_cards = re.findall(r'<div class="note-card', html)
        print(f"\n找到 {len(note_cards)} 个笔记卡片")

        # 检查是否包含图片数量标记
        if '📷' in html:
            print("✅ 页面包含图片数量标记 📷")

            # 统计图片标记数量
            count = html.count('📷')
            print(f"   找到 {count} 个图片数量标记")
        else:
            print("❌ 页面不包含图片数量标记 📷")

        # 检查是否包含画廊函数调用
        if 'openImageGallery' in html:
            print("✅ 页面包含画廊函数调用")

            # 统计调用次数
            count = html.count('openImageGallery')
            print(f"   找到 {count} 次画廊函数调用")
        else:
            print("❌ 页面不包含画廊函数调用")

        # 检查是否包含 media_paths 数据
        if '"webdav:' in html:
            print("✅ 页面包含 webdav 图片路径")

        # 查找笔记卡片
        if 'note-card' in html:
            print("✅ 页面包含笔记卡片")

            # 提取第一个笔记卡片的片段
            start_idx = html.find('<div class="note-card')
            if start_idx != -1:
                end_idx = html.find('</div>', start_idx + 500)
                if end_idx != -1:
                    card_html = html[start_idx:end_idx + 6]

                    print("\n第一个笔记卡片片段:")
                    print("-" * 80)

                    # 检查图片区域
                    if 'aspect-video' in card_html:
                        print("✅ 包含图片区域 (aspect-video)")

                        # 检查图片数量标记
                        if '📷' in card_html:
                            import re
                            match = re.search(r'📷\s*(\d+)', card_html)
                            if match:
                                num_images = match.group(1)
                                print(f"✅ 显示图片数量: {num_images}")
                        else:
                            print("⚠️  没有图片数量标记 (可能是单图)")

                        # 检查openImageGallery调用
                        if 'openImageGallery' in card_html:
                            print("✅ 包含画廊调用")
                            # 尝试提取参数
                            match = re.search(r'openImageGallery\((\d+),\s*(\[.*?\])\)', card_html)
                            if match:
                                note_id = match.group(1)
                                paths = match.group(2)
                                print(f"   笔记ID: {note_id}")
                                print(f"   图片路径: {paths[:100]}...")
                        else:
                            print("⚠️  没有画廊调用 (使用 openImageModal)")

    else:
        print(f"❌ 请求失败: {response.status_code}")

print("\n" + "=" * 80)
