#!/bin/bash
# 校准数据刷新后丢失问题 - 自动修复脚本
# 请在 /root/Save-Restricted-Bot 目录下执行

set -e

echo "=========================================="
echo "校准缓存失效问题修复脚本"
echo "=========================================="

# 备份文件
echo "1. 备份原始文件..."
cp web/routes/api.py web/routes/api.py.backup.$(date +%Y%m%d_%H%M%S)
cp bot/services/calibration_manager.py bot/services/calibration_manager.py.backup.$(date +%Y%m%d_%H%M%S)

# 修复 web/routes/api.py
echo "2. 修复 web/routes/api.py ..."
python3 << 'EOF'
with open('web/routes/api.py', 'r') as f:
    content = f.read()

# 查找并替换缓存失效代码块
old_code = '''            # 使缓存失效，确保刷新页面后能看到更新后的数据
            try:
                from src.infrastructure.cache.managers import get_note_cache_manager
                cache_manager = get_note_cache_manager()
                # 需要获取note的user_id来失效缓存
                user_id = updated_note.get('user_id')
                if user_id:
                    invalidated = cache_manager.invalidate_note(note_id, user_id)
                    logger.info(f"✅ 已失效笔记 {note_id} 的缓存 ({invalidated} 个条目)")
            except Exception as e:
                logger.warning(f"⚠️ 缓存失效失败 (不影响功能): {e}")'''

new_code = '''            # 使缓存失效，确保刷新页面后能看到更新后的数据
            try:
                from src.infrastructure.cache.managers import get_note_cache_manager
                cache_manager = get_note_cache_manager()
                user_id = updated_note.get('user_id')

                # 失效特定用户的缓存
                if user_id:
                    invalidated = cache_manager.invalidate_note(note_id, user_id)
                    logger.info(f"✅ 已失效笔记 {note_id} 的用户缓存 ({invalidated} 个条目)")

                # 【关键修复】失效全局列表缓存（user_id=None的情况）
                # 因为notes_list()使用user_id=None，生成的是notes:list:all:*的key
                deleted = cache_manager._cache.delete_pattern(f"{cache_manager._key_prefix}:list:all:*")
                deleted += cache_manager._cache.delete_pattern(f"{cache_manager._key_prefix}:count:all:*")
                logger.info(f"✅ 已失效全局笔记列表缓存 ({deleted} 个条目)")

            except Exception as e:
                logger.error(f"❌ 缓存失效失败: {e}")
                import traceback
                traceback.print_exc()'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('web/routes/api.py', 'w') as f:
        f.write(content)
    print("✅ web/routes/api.py 修复成功")
else:
    print("⚠️  警告：未找到匹配的代码块，可能已经修复或代码已变更")
    print("   请手动检查 web/routes/api.py:164-174")
EOF

# 修复 bot/services/calibration_manager.py
echo "3. 修复 bot/services/calibration_manager.py ..."
python3 << 'EOF'
with open('bot/services/calibration_manager.py', 'r') as f:
    content = f.read()

# 查找并替换缓存失效代码块
old_code = '''                    # 使缓存失效，确保刷新页面后能看到更新后的数据
                    try:
                        from src.infrastructure.cache.managers import get_note_cache_manager
                        cache_manager = get_note_cache_manager()
                        user_id = note.get('user_id')
                        if user_id:
                            invalidated = cache_manager.invalidate_note(note_id, user_id)
                            logger.info(f"✅ 已失效笔记 {note_id} 的缓存 ({invalidated} 个条目)")
                    except Exception as e:
                        logger.warning(f"⚠️ 缓存失效失败 (不影响功能): {e}")'''

new_code = '''                    # 使缓存失效，确保刷新页面后能看到更新后的数据
                    try:
                        from src.infrastructure.cache.managers import get_note_cache_manager
                        cache_manager = get_note_cache_manager()
                        user_id = note.get('user_id')

                        # 失效特定用户的缓存
                        if user_id:
                            invalidated = cache_manager.invalidate_note(note_id, user_id)
                            logger.info(f"✅ 已失效笔记 {note_id} 的用户缓存 ({invalidated} 个条目)")

                        # 【关键修复】失效全局列表缓存（user_id=None的情况）
                        deleted = cache_manager._cache.delete_pattern(f"{cache_manager._key_prefix}:list:all:*")
                        deleted += cache_manager._cache.delete_pattern(f"{cache_manager._key_prefix}:count:all:*")
                        logger.info(f"✅ 已失效全局笔记列表缓存 ({deleted} 个条目)")

                    except Exception as e:
                        logger.error(f"❌ 缓存失效失败: {e}")
                        import traceback
                        traceback.print_exc()'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('bot/services/calibration_manager.py', 'w') as f:
        f.write(content)
    print("✅ bot/services/calibration_manager.py 修复成功")
else:
    print("⚠️  警告：未找到匹配的代码块，可能已经修复或代码已变更")
    print("   请手动检查 bot/services/calibration_manager.py:425-434")
EOF

echo ""
echo "=========================================="
echo "修复完成！"
echo "=========================================="
echo ""
echo "下一步："
echo "1. 检查修复后的文件是否正确"
echo "2. 重启Flask服务: docker-compose restart web 或 systemctl restart your-service"
echo "3. 测试校准功能并刷新页面验证"
echo ""
echo "备份文件位置："
echo "- web/routes/api.py.backup.*"
echo "- bot/services/calibration_manager.py.backup.*"
echo ""
