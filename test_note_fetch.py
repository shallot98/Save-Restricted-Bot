#!/usr/bin/env python3
"""测试笔记979获取的数据"""
import sys
sys.path.insert(0, '/root/Save-Restricted-Bot')

from src.core.container import get_note_service
from database import get_note_by_id

print("="*80)
print("测试1: 直接从数据库读取笔记979")
print("="*80)
note_db = get_note_by_id(979)
print(f"ID: {note_db.get('id')}")
print(f"Filename: {note_db.get('filename')}")
print(f"Magnet (前100字符): {note_db.get('magnet_link', '')[:100]}")
print()

print("="*80)
print("测试2: 通过NoteService获取笔记列表（会使用缓存）")
print("="*80)
note_service = get_note_service()
# 清除缓存，强制从数据库读取
from src.infrastructure.cache.managers import get_note_cache_manager
cache_manager = get_note_cache_manager()
deleted = cache_manager._cache.delete_pattern("notes:list:*")
print(f"已删除 {deleted} 个列表缓存")

result = note_service.get_notes(user_id=None, page=1, page_size=100)
note_979 = None
for note_dto in result.items:
    if note_dto.id == 979:
        note_979 = note_dto
        break

if note_979:
    print(f"ID: {note_979.id}")
    print(f"Filename: {note_979.filename}")
    print(f"Magnet (前100字符): {note_979.magnet_link[:100] if note_979.magnet_link else 'None'}")
else:
    print("❌ 未找到笔记979")

print()
print("="*80)
print("测试3: 检查DTO转换")
print("="*80)
from src.domain.entities.note import Note
from src.application.dto.note_dto import NoteDTO

# 直接从数据库数据创建Entity然后转DTO
note_entity = Note(
    id=note_db['id'],
    user_id=note_db['user_id'],
    source_chat_id=note_db['source_chat_id'],
    source_name=note_db.get('source_name'),
    message_text=note_db.get('message_text'),
    timestamp=note_db.get('timestamp'),
    media_type=note_db.get('media_type'),
    media_path=note_db.get('media_path'),
    media_paths=note_db.get('media_paths'),
    magnet_link=note_db.get('magnet_link'),
    filename=note_db.get('filename'),
    is_favorite=note_db.get('is_favorite', False)
)

note_dto_converted = NoteDTO.from_entity(note_entity)
print(f"Entity Filename: {note_entity.filename}")
print(f"Entity Magnet (前100字符): {note_entity.magnet_link[:100] if note_entity.magnet_link else 'None'}")
print(f"DTO Filename: {note_dto_converted.filename}")
print(f"DTO Magnet (前100字符): {note_dto_converted.magnet_link[:100] if note_dto_converted.magnet_link else 'None'}")
