#!/usr/bin/env python3
"""
迁移脚本：升级到多图片支持版本

功能：
1. 创建 note_media 表（如果不存在）
2. 将现有的单媒体笔记迁移到 note_media 表
3. 将配置文件移动到 data/config/ 目录
4. 不会删除原始数据，保证向后兼容
"""

import sqlite3
import os
import shutil
import sys

# 数据目录
DATA_DIR = os.environ.get('DATA_DIR', 'data')
DATABASE_FILE = os.path.join(DATA_DIR, 'notes.db')
CONFIG_DIR = os.path.join(DATA_DIR, 'config')

def migrate_database():
    """迁移数据库到新格式"""
    print("="*60)
    print("开始数据库迁移...")
    print("="*60)
    
    if not os.path.exists(DATABASE_FILE):
        print(f"❌ 数据库文件不存在: {DATABASE_FILE}")
        print("   如果这是新安装，可以忽略此错误")
        return True
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # 检查 note_media 表是否存在
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='note_media'
    """)
    
    if cursor.fetchone():
        print("✅ note_media 表已存在，跳过创建")
    else:
        print("📝 创建 note_media 表...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS note_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                media_path TEXT NOT NULL,
                media_order INTEGER DEFAULT 0,
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_note_media_note_id 
            ON note_media(note_id)
        ''')
        print("✅ note_media 表创建成功")
    
    # 迁移现有的单媒体数据到 note_media 表
    print("\n📦 迁移现有媒体数据...")
    cursor.execute("""
        SELECT id, media_type, media_path 
        FROM notes 
        WHERE media_path IS NOT NULL 
        AND media_path != ''
        AND id NOT IN (SELECT DISTINCT note_id FROM note_media)
    """)
    
    old_media = cursor.fetchall()
    migrated_count = 0
    
    for note_id, media_type, media_path in old_media:
        try:
            cursor.execute('''
                INSERT INTO note_media (note_id, media_type, media_path, media_order)
                VALUES (?, ?, ?, 0)
            ''', (note_id, media_type, media_path))
            migrated_count += 1
        except Exception as e:
            print(f"⚠️ 迁移笔记 {note_id} 的媒体时出错: {e}")
    
    conn.commit()
    conn.close()
    
    if migrated_count > 0:
        print(f"✅ 成功迁移 {migrated_count} 条媒体记录到新表")
    else:
        print("ℹ️  没有需要迁移的媒体记录")
    
    return True

def migrate_config_files():
    """将配置文件移动到 data/config/ 目录"""
    print("\n" + "="*60)
    print("迁移配置文件...")
    print("="*60)
    
    # 确保配置目录存在
    os.makedirs(CONFIG_DIR, exist_ok=True)
    
    config_files = ['config.json', 'watch_config.json']
    migrated = 0
    
    for config_file in config_files:
        src = config_file
        dest = os.path.join(CONFIG_DIR, config_file)
        
        # 如果源文件存在且目标文件不存在，则移动
        if os.path.exists(src) and not os.path.exists(dest):
            try:
                shutil.copy2(src, dest)
                print(f"✅ 复制 {config_file} → {dest}")
                print(f"   (保留原文件以确保兼容性)")
                migrated += 1
            except Exception as e:
                print(f"⚠️ 复制 {config_file} 时出错: {e}")
        elif os.path.exists(dest):
            print(f"ℹ️  {config_file} 已存在于目标位置，跳过")
        else:
            print(f"ℹ️  {config_file} 不存在，跳过")
    
    if migrated > 0:
        print(f"\n✅ 成功复制 {migrated} 个配置文件")
        print("   配置文件现在位于: data/config/")
        print("   下次启动将优先使用新位置的配置")
    
    return True

def verify_migration():
    """验证迁移结果"""
    print("\n" + "="*60)
    print("验证迁移结果...")
    print("="*60)
    
    # 检查数据库
    if os.path.exists(DATABASE_FILE):
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # 检查表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['notes', 'note_media', 'users']
        for table in required_tables:
            if table in tables:
                print(f"✅ 表 {table} 存在")
            else:
                print(f"❌ 表 {table} 不存在")
        
        # 统计数据
        cursor.execute("SELECT COUNT(*) FROM notes")
        note_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM note_media")
        media_count = cursor.fetchone()[0]
        
        print(f"\n📊 数据统计:")
        print(f"   笔记总数: {note_count}")
        print(f"   媒体总数: {media_count}")
        
        conn.close()
    else:
        print("ℹ️  数据库文件不存在（可能是新安装）")
    
    # 检查目录结构
    print(f"\n📁 目录结构:")
    dirs = [DATA_DIR, os.path.join(DATA_DIR, 'media'), CONFIG_DIR]
    for d in dirs:
        if os.path.exists(d):
            print(f"   ✅ {d}")
        else:
            print(f"   ❌ {d} (将在首次运行时创建)")
    
    return True

def main():
    print("\n" + "="*60)
    print("Save-Restricted-Bot 多图片支持迁移工具")
    print("="*60)
    print()
    print("此脚本将:")
    print("1. 升级数据库以支持多图片功能")
    print("2. 迁移现有单媒体数据到新表")
    print("3. 将配置文件组织到 data/config/ 目录")
    print()
    print("⚠️  迁移前建议备份以下内容:")
    print(f"   - {DATABASE_FILE}")
    print("   - config.json")
    print("   - watch_config.json")
    print()
    
    response = input("是否继续? (y/N): ")
    if response.lower() != 'y':
        print("❌ 取消迁移")
        return
    
    print()
    
    # 执行迁移
    success = True
    success = success and migrate_database()
    success = success and migrate_config_files()
    success = success and verify_migration()
    
    print("\n" + "="*60)
    if success:
        print("✅ 迁移完成!")
        print("="*60)
        print()
        print("后续步骤:")
        print("1. 重启机器人以加载新的数据库结构")
        print("2. 配置文件将自动使用 data/config/ 目录")
        print("3. 新的多图片功能将自动生效")
        print()
        print("💡 提示:")
        print("   - 旧的单图片笔记仍可正常显示")
        print("   - 新的多图片功能会自动处理媒体组")
        print("   - 所有数据保存在 data/ 目录，更新代码时不会丢失")
    else:
        print("⚠️  迁移过程中遇到一些问题")
        print("="*60)
        print()
        print("请检查上面的错误信息，如果需要帮助请查看文档")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
