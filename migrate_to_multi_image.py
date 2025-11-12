#!/usr/bin/env python3
"""
Migration script to add multi-image support to existing database
"""

import sqlite3
import os

# 数据目录
DATA_DIR = 'data'
DATABASE_FILE = os.path.join(DATA_DIR, 'notes.db')

def migrate_database():
    """Migrate existing database to support multiple images"""
    print("🔄 开始数据库迁移...")
    
    if not os.path.exists(DATABASE_FILE):
        print("❌ 数据库文件不存在，无需迁移")
        return
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        # 检查是否已经包含新字段
        cursor.execute("PRAGMA table_info(notes)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # 添加新字段（如果不存在）
        if 'media_group_id' not in columns:
            cursor.execute("ALTER TABLE notes ADD COLUMN media_group_id TEXT")
            print("✅ 已添加 media_group_id 字段")
        
        if 'is_media_group' not in columns:
            cursor.execute("ALTER TABLE notes ADD COLUMN is_media_group BOOLEAN DEFAULT 0")
            print("✅ 已添加 is_media_group 字段")
        
        # 创建媒体文件表（如果不存在）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS note_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                media_path TEXT NOT NULL,
                file_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (note_id) REFERENCES notes (id) ON DELETE CASCADE
            )
        ''')
        print("✅ 已创建 note_media 表")
        
        # 提交更改
        conn.commit()
        print("✅ 数据库迁移完成！")
        
        # 显示统计信息
        cursor.execute("SELECT COUNT(*) FROM notes")
        total_notes = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM note_media")
        total_media = cursor.fetchone()[0]
        
        print(f"📊 当前数据库状态：")
        print(f"   - 总笔记数：{total_notes}")
        print(f"   - 媒体文件数：{total_media}")
        print(f"   - 数据库文件：{DATABASE_FILE}")
        
    except Exception as e:
        print(f"❌ 迁移失败：{e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()