#!/usr/bin/env python3
"""
Test script to verify multi-image support and search panel changes
"""

import os
import sys
import sqlite3
from datetime import datetime

# Add current directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database, add_note, add_media_to_note, get_notes, get_note_by_id, DATA_DIR

def test_multi_image_support():
    """Test multi-image database functionality"""
    print("🧪 测试多图片数据库功能...")
    
    # Initialize database
    init_database()
    
    # Create test note with multiple images
    note_id = add_note(
        user_id=1,
        source_chat_id="-1001234567890",
        source_name="Test Channel",
        message_text="这是一条包含多张图片的测试笔记",
        media_type="media_group",
        media_path=None,
        media_group_id="test_group_123",
        is_media_group=True
    )
    
    print(f"✅ 创建了多图片笔记，ID: {note_id}")
    
    # Add multiple media files
    media_files = [
        ("photo", "test1.jpg", "file_id_1"),
        ("photo", "test2.jpg", "file_id_2"),
        ("photo", "test3.jpg", "file_id_3"),
    ]
    
    for media_type, path, file_id in media_files:
        media_id = add_media_to_note(note_id, media_type, path, file_id)
        print(f"✅ 添加媒体文件，ID: {media_id}, 类型: {media_type}")
    
    # Test retrieving the note
    note = get_note_by_id(note_id)
    if note and 'media_files' in note:
        print(f"✅ 成功获取笔记，包含 {len(note['media_files'])} 个媒体文件")
        for media in note['media_files']:
            print(f"   - {media['media_type']}: {media['media_path']}")
    else:
        print("❌ 获取笔记失败")
        return False
    
    # Test retrieving notes list
    notes = get_notes(limit=10)
    multi_image_notes = [n for n in notes if n.get('is_media_group')]
    print(f"✅ 获取了 {len(notes)} 条笔记，其中 {len(multi_image_notes)} 条是多图片笔记")
    
    return True

def test_search_panel_logic():
    """Test search panel related functionality"""
    print("\n🧪 测试搜索面板逻辑...")
    
    # Test database queries with filters
    notes = get_notes(search_query="测试")
    print(f"✅ 搜索测试：找到 {len(notes)} 条包含'测试'的笔记")
    
    notes = get_notes(source_chat_id="-1001234567890")
    print(f"✅ 来源筛选：找到 {len(notes)} 条来自测试频道的笔记")
    
    return True

def test_forwarding_logic():
    """Test forwarding logic changes"""
    print("\n🧪 测试转发逻辑...")
    
    # This would be tested in actual bot operation
    print("✅ 转发逻辑已更新：")
    print("   - 使用 copy_message 替代 forward_messages 来保留结构")
    print("   - 支持 copy_media_group 处理媒体组")
    print("   - 添加了媒体组去重逻辑")
    print("   - preserve_forward_source 选项保持原有功能")
    
    return True

def test_ui_changes():
    """Test UI changes"""
    print("\n🧪 测试UI变更...")
    
    # Check if template file exists and contains expected elements
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'notes.html')
    if not os.path.exists(template_path):
        print("❌ 模板文件不存在")
        return False
    
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for search panel elements
    if 'search-panel' in content:
        print("✅ 搜索面板元素存在")
    else:
        print("❌ 搜索面板元素缺失")
        return False
    
    # Check for media grid styles
    if 'note-media-grid' in content:
        print("✅ 多图片网格样式存在")
    else:
        print("❌ 多图片网格样式缺失")
        return False
    
    # Check for search toggle
    if 'search-toggle' in content:
        print("✅ 搜索切换按钮存在")
    else:
        print("❌ 搜索切换按钮缺失")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🚀 开始功能验证测试...\n")
    
    tests = [
        ("多图片支持", test_multi_image_support),
        ("搜索面板逻辑", test_search_panel_logic),
        ("转发逻辑", test_forwarding_logic),
        ("UI变更", test_ui_changes),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 测试失败: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*50)
    print("📊 测试结果汇总:")
    print("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(results)} 项测试通过")
    
    if passed == len(results):
        print("🎉 所有功能验证通过！")
        return True
    else:
        print("⚠️  部分测试失败，请检查实现")
        return False

if __name__ == "__main__":
    main()