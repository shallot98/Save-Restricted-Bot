#!/usr/bin/env python3
"""
测试记录模式功能
"""

import os
import sys
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database, add_note, get_notes, get_note_count, DATA_DIR

def test_record_mode():
    """测试记录模式的基本功能"""
    print("🧪 测试记录模式功能...")
    
    # 确保数据目录存在
    print(f"📁 数据目录: {DATA_DIR}")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'media'), exist_ok=True)
    
    # 初始化数据库
    init_database()
    print("✅ 数据库初始化完成")
    
    # 测试添加文本笔记
    try:
        note_id = add_note(
            user_id=1,
            source_chat_id="-1001234567890",
            source_name="测试频道",
            message_text="这是一条测试笔记",
            media_type=None,
            media_path=None,
            media_group_id=None,
            is_media_group=False
        )
        print(f"✅ 文本笔记添加成功，ID: {note_id}")
    except Exception as e:
        print(f"❌ 文本笔记添加失败: {e}")
        return False
    
    # 测试添加图片笔记
    try:
        note_id = add_note(
            user_id=1,
            source_chat_id="-1001234567890",
            source_name="测试频道",
            message_text="带图片的测试笔记",
            media_type="photo",
            media_path="test_image.jpg",
            media_group_id=None,
            is_media_group=False
        )
        print(f"✅ 图片笔记添加成功，ID: {note_id}")
    except Exception as e:
        print(f"❌ 图片笔记添加失败: {e}")
        return False
    
    # 测试添加媒体组笔记
    try:
        note_id = add_note(
            user_id=1,
            source_chat_id="-1001234567890",
            source_name="测试频道",
            message_text="媒体组测试笔记",
            media_type="media_group",
            media_path=None,
            media_group_id="test_group_123",
            is_media_group=True
        )
        print(f"✅ 媒体组笔记添加成功，ID: {note_id}")
    except Exception as e:
        print(f"❌ 媒体组笔记添加失败: {e}")
        return False
    
    # 测试获取笔记
    try:
        notes = get_notes(limit=10, offset=0)
        print(f"✅ 获取笔记成功，共 {len(notes)} 条")
        for note in notes:
            print(f"   📝 笔记 {note['id']}: {note['source_name']} - {note['message_text'][:50]}...")
    except Exception as e:
        print(f"❌ 获取笔记失败: {e}")
        return False
    
    # 测试获取笔记数量
    try:
        count = get_note_count()
        print(f"✅ 获取笔记数量成功，共 {count} 条")
    except Exception as e:
        print(f"❌ 获取笔记数量失败: {e}")
        return False
    
    print("🎉 记录模式功能测试完成！")
    return True

def test_config_paths():
    """测试配置文件路径"""
    print("\n🧪 测试配置文件路径...")
    
    # 检查DATA_DIR环境变量
    data_dir = os.environ.get('DATA_DIR', 'data')
    print(f"📁 DATA_DIR: {data_dir}")
    
    # 检查配置文件路径
    config_dir = os.path.join(data_dir, 'config')
    config_file = os.path.join(config_dir, 'config.json')
    watch_config_file = os.path.join(config_dir, 'watch_config.json')
    
    print(f"📁 配置目录: {config_dir}")
    print(f"📄 配置文件: {config_file}")
    print(f"📄 监控配置文件: {watch_config_file}")
    
    # 确保目录存在
    os.makedirs(config_dir, exist_ok=True)
    print("✅ 配置目录创建成功")
    
    # 如果配置文件不存在，创建默认配置
    if not os.path.exists(config_file):
        default_config = {
            "TOKEN": "",
            "HASH": "",
            "ID": "",
            "STRING": ""
        }
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        print("✅ 默认配置文件创建成功")
    
    # 如果监控配置文件不存在，创建默认配置
    if not os.path.exists(watch_config_file):
        default_watch_config = {}
        with open(watch_config_file, 'w', encoding='utf-8') as f:
            json.dump(default_watch_config, f, indent=4, ensure_ascii=False)
        print("✅ 默认监控配置文件创建成功")
    
    return True

if __name__ == "__main__":
    print("="*60)
    print("🔧 Save-Restricted-Bot 记录模式测试")
    print("="*60)
    
    success = True
    
    # 测试配置路径
    if not test_config_paths():
        success = False
    
    # 测试记录模式功能
    if not test_record_mode():
        success = False
    
    if success:
        print("\n🎉 所有测试通过！记录模式功能正常。")
        sys.exit(0)
    else:
        print("\n❌ 测试失败！请检查配置和代码。")
        sys.exit(1)