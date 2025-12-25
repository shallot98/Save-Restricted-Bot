#!/usr/bin/env python3
"""
测试多图片数据流 - 从数据库到前端的完整路径
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.application.services.note_service import NoteService
from src.infrastructure.persistence.repositories.note_repository import SQLiteNoteRepository

def main():
    # 初始化服务
    repo = SQLiteNoteRepository()
    service = NoteService(repo)

    print("=" * 80)
    print("多图片数据流测试")
    print("=" * 80)

    # 获取笔记列表（第一页）
    result = service.get_notes(
        user_id=None,
        source_chat_id=None,
        search_query=None,
        date_from=None,
        date_to=None,
        favorite_only=False,
        page=1,
        page_size=20
    )

    print(f"\n总笔记数: {result.total}")
    print(f"当前页笔记数: {len(result.items)}")

    # 检查多图片笔记
    multi_image_notes = [note for note in result.items if len(note.media_paths) > 1]

    print(f"\n当前页多图片笔记数: {len(multi_image_notes)}")

    if multi_image_notes:
        print("\n" + "=" * 80)
        print("多图片笔记详情:")
        print("=" * 80)

        for note_dto in multi_image_notes[:3]:  # 只显示前3条
            print(f"\n笔记 ID: {note_dto.id}")
            print(f"媒体类型: {note_dto.media_type}")
            print(f"media_path: {note_dto.media_path}")
            print(f"media_paths: {note_dto.media_paths}")
            print(f"media_paths 长度: {len(note_dto.media_paths)}")
            print(f"media_paths 类型: {type(note_dto.media_paths)}")

            # 检查是否是列表
            if isinstance(note_dto.media_paths, list):
                print("✅ media_paths 是列表类型")
                for i, path in enumerate(note_dto.media_paths):
                    print(f"  [{i}] {path}")
            else:
                print("❌ media_paths 不是列表类型!")

            print("-" * 80)
    else:
        print("\n⚠️  当前页没有找到多图片笔记")
        print("尝试查找数据库中的多图片笔记...")

        # 直接从数据库查找
        import json
        import sqlite3
        from src.core.config import settings

        db_path = settings.paths.data_dir / "notes.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, media_type, media_paths
            FROM notes
            WHERE media_paths IS NOT NULL
            AND LENGTH(media_paths) > 10
            LIMIT 5
        """)

        rows = cursor.fetchall()
        conn.close()

        if rows:
            print(f"\n数据库中找到 {len(rows)} 条多图片笔记:")
            for note_id, media_type, media_paths_str in rows:
                try:
                    media_paths = json.loads(media_paths_str)
                    print(f"\n笔记 ID: {note_id}")
                    print(f"媒体类型: {media_type}")
                    print(f"图片数量: {len(media_paths)}")
                    print(f"图片列表: {media_paths}")
                except Exception as e:
                    print(f"解析失败: {e}")
        else:
            print("\n❌ 数据库中也没有找到多图片笔记")

if __name__ == "__main__":
    main()
