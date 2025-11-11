#!/usr/bin/env python3
"""
数据迁移脚本：将旧的 data/ 目录迁移到新的系统级目录 /data/save_restricted_bot/

此脚本用于将现有的数据文件从项目根目录下的 data/ 目录迁移到新的独立数据目录。

使用方法：
    python3 migrate_to_system_data_dir.py

迁移内容：
    - data/config/config.json -> /data/save_restricted_bot/config/config.json
    - data/config/watch_config.json -> /data/save_restricted_bot/config/watch_config.json
    - data/notes.db -> /data/save_restricted_bot/notes.db
    - data/media/* -> /data/save_restricted_bot/media/*

注意：
    - 脚本会保留原文件作为备份
    - 需要有足够的权限创建 /data/save_restricted_bot/ 目录
    - 迁移完成后，请确认数据正常后再删除旧的 data/ 目录
"""

import os
import shutil
import sys

# 旧数据目录（项目根目录下的相对路径）
OLD_DATA_DIR = 'data'

# 新数据目录（系统级绝对路径）
NEW_DATA_DIR = '/data/save_restricted_bot'

def ensure_dir(directory):
    """确保目录存在"""
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        print(f"✅ 创建目录: {directory}")
    else:
        print(f"✓ 目录已存在: {directory}")

def copy_file(src, dest):
    """复制文件"""
    if os.path.exists(src):
        ensure_dir(os.path.dirname(dest))
        shutil.copy2(src, dest)
        print(f"✅ 复制文件: {src} -> {dest}")
        return True
    else:
        print(f"⚠️ 源文件不存在: {src}")
        return False

def copy_directory(src, dest):
    """复制目录"""
    if os.path.exists(src):
        ensure_dir(dest)
        for item in os.listdir(src):
            src_path = os.path.join(src, item)
            dest_path = os.path.join(dest, item)
            
            if os.path.isfile(src_path):
                shutil.copy2(src_path, dest_path)
                print(f"✅ 复制文件: {src_path} -> {dest_path}")
            elif os.path.isdir(src_path):
                copy_directory(src_path, dest_path)
        return True
    else:
        print(f"⚠️ 源目录不存在: {src}")
        return False

def migrate_data():
    """执行数据迁移"""
    print("=" * 60)
    print("数据迁移工具 - Save-Restricted-Bot")
    print("=" * 60)
    print(f"旧数据目录: {OLD_DATA_DIR}")
    print(f"新数据目录: {NEW_DATA_DIR}")
    print()
    
    # 检查旧数据目录是否存在
    if not os.path.exists(OLD_DATA_DIR):
        print(f"⚠️ 旧数据目录 {OLD_DATA_DIR} 不存在")
        print("无需迁移，退出")
        return
    
    # 检查是否有权限创建新目录
    try:
        ensure_dir(NEW_DATA_DIR)
        ensure_dir(os.path.join(NEW_DATA_DIR, 'config'))
        ensure_dir(os.path.join(NEW_DATA_DIR, 'media'))
        ensure_dir(os.path.join(NEW_DATA_DIR, 'logs'))
    except PermissionError:
        print(f"❌ 错误：没有权限创建目录 {NEW_DATA_DIR}")
        print("请使用 sudo 运行此脚本，或者更改 NEW_DATA_DIR 为您有权限的目录")
        sys.exit(1)
    
    print("\n开始迁移数据...")
    print("-" * 60)
    
    migrated_count = 0
    
    # 迁移配置文件
    config_files = [
        ('config/config.json', 'config/config.json'),
        ('config/watch_config.json', 'config/watch_config.json'),
        ('config.json', 'config/config.json'),  # 兼容旧位置
        ('watch_config.json', 'config/watch_config.json'),  # 兼容旧位置
    ]
    
    for old_rel, new_rel in config_files:
        old_path = os.path.join(OLD_DATA_DIR, old_rel) if OLD_DATA_DIR in old_rel or '/' in old_rel else old_rel
        new_path = os.path.join(NEW_DATA_DIR, new_rel)
        
        # 避免重复复制
        if os.path.exists(new_path):
            continue
            
        if copy_file(old_path, new_path):
            migrated_count += 1
    
    # 迁移数据库文件
    if copy_file(os.path.join(OLD_DATA_DIR, 'notes.db'), os.path.join(NEW_DATA_DIR, 'notes.db')):
        migrated_count += 1
    
    # 迁移媒体文件目录
    old_media_dir = os.path.join(OLD_DATA_DIR, 'media')
    new_media_dir = os.path.join(NEW_DATA_DIR, 'media')
    
    if os.path.exists(old_media_dir):
        print(f"\n迁移媒体文件目录...")
        if copy_directory(old_media_dir, new_media_dir):
            media_count = len([f for f in os.listdir(old_media_dir) if os.path.isfile(os.path.join(old_media_dir, f))])
            print(f"✅ 迁移了 {media_count} 个媒体文件")
            migrated_count += media_count
    
    print("-" * 60)
    print(f"\n✅ 迁移完成！共迁移 {migrated_count} 个文件/目录")
    print()
    print("⚠️ 重要提示：")
    print("1. 请启动程序并确认数据正常后，再删除旧的 data/ 目录")
    print("2. 确保环境变量 DATA_DIR 未设置，或设置为 /data/save_restricted_bot")
    print("3. Docker 用户请更新 docker-compose.yml 的 volumes 配置")
    print()
    print("备份旧数据目录的命令：")
    print(f"  tar -czf data_backup_$(date +%Y%m%d).tar.gz {OLD_DATA_DIR}")
    print()

if __name__ == '__main__':
    try:
        migrate_data()
    except Exception as e:
        print(f"\n❌ 迁移失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
