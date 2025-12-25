#!/bin/bash
# 多图片功能验证脚本

echo "=========================================="
echo "🔍 多图片显示功能验证"
echo "=========================================="
echo ""

# 1. 检查容器状态
echo "1️⃣ 检查容器状态..."
if docker compose ps | grep -q "Up.*healthy"; then
    echo "   ✅ 容器运行正常"
else
    echo "   ❌ 容器未运行或不健康"
    exit 1
fi
echo ""

# 2. 检查数据库中的多图片笔记
echo "2️⃣ 检查数据库中的多图片笔记..."
MULTI_COUNT=$(docker exec save-restricted-bot python3 -c "
from database import get_notes
notes = get_notes(limit=100)
count = sum(1 for note in notes if note.get('media_paths') and len(note.get('media_paths', [])) > 1)
print(count)
" 2>/dev/null | tail -1)

if [ "$MULTI_COUNT" -gt 0 ]; then
    echo "   ✅ 找到 $MULTI_COUNT 条多图片笔记"
else
    echo "   ❌ 未找到多图片笔记"
    exit 1
fi
echo ""

# 3. 检查模板文件
echo "3️⃣ 检查模板文件是否包含新功能..."
if docker exec save-restricted-bot grep -q "openImageGallery" /app/templates/notes.html; then
    echo "   ✅ 模板包含 openImageGallery 函数"
else
    echo "   ❌ 模板未包含 openImageGallery 函数"
    exit 1
fi

if docker exec save-restricted-bot grep -q "galleryModal" /app/templates/notes.html; then
    echo "   ✅ 模板包含画廊模态框"
else
    echo "   ❌ 模板未包含画廊模态框"
    exit 1
fi
echo ""

# 4. 检查 Web 服务
echo "4️⃣ 检查 Web 服务..."
if curl -s http://localhost:10000/health | grep -q '"status": "healthy"'; then
    echo "   ✅ Web 服务健康"
else
    echo "   ❌ Web 服务异常"
    exit 1
fi
echo ""

# 5. 显示测试笔记信息
echo "5️⃣ 显示可用于测试的多图片笔记..."
docker exec save-restricted-bot python3 -c "
from database import get_notes
notes = get_notes(limit=100)
count = 0
for note in notes:
    if note.get('media_paths') and len(note.get('media_paths', [])) > 1:
        count += 1
        if count <= 5:
            print(f'   📷 笔记 ID: {note[\"id\"]}, 图片数: {len(note[\"media_paths\"])}')
if count > 5:
    print(f'   ... 还有 {count - 5} 条多图片笔记')
" 2>/dev/null | grep -E "📷|还有"
echo ""

# 6. 访问信息
echo "=========================================="
echo "✅ 验证完成！"
echo "=========================================="
echo ""
echo "📝 测试步骤："
echo "   1. 访问: http://localhost:10000/notes"
echo "   2. 查找带有 📷 标记的笔记"
echo "   3. 点击图片打开画廊"
echo "   4. 测试左右切换和键盘快捷键"
echo ""
echo "🔑 登录信息："
echo "   用户名: admin"
echo "   密码: admin"
echo ""
echo "📚 详细测试指南："
echo "   查看文件: MULTI_IMAGE_TEST_GUIDE.md"
echo ""
