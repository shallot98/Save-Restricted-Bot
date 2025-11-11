#!/bin/bash

echo "=========================================="
echo "验证 v2.3.1 改进实施情况"
echo "=========================================="
echo

echo "1. 检查 DATA_DIR 配置..."
echo "   main.py:"
grep -q "DATA_DIR = os.environ.get('DATA_DIR', '/data/save_restricted_bot')" main.py && echo "   ✅ DATA_DIR 配置正确" || echo "   ❌ DATA_DIR 配置有问题"
grep -q "CONFIG_DIR = os.path.join(DATA_DIR, 'config')" main.py && echo "   ✅ CONFIG_DIR 使用 DATA_DIR" || echo "   ❌ CONFIG_DIR 配置有问题"

echo "   database.py:"
grep -q "DATA_DIR = os.environ.get('DATA_DIR', '/data/save_restricted_bot')" database.py && echo "   ✅ DATA_DIR 配置正确" || echo "   ❌ DATA_DIR 配置有问题"

echo "   setup.py:"
grep -q "DATA_DIR = os.environ.get('DATA_DIR', '/data/save_restricted_bot')" setup.py && echo "   ✅ DATA_DIR 配置正确" || echo "   ❌ DATA_DIR 配置有问题"

echo
echo "2. 检查启动初始化代码..."
grep -q "os.makedirs(CONFIG_DIR, exist_ok=True)" main.py && echo "   ✅ CONFIG_DIR 自动创建" || echo "   ❌ 缺少目录创建"
grep -q "os.makedirs(os.path.join(DATA_DIR, 'media'), exist_ok=True)" main.py && echo "   ✅ media 目录自动创建" || echo "   ❌ 缺少 media 目录创建"
grep -q "if not os.path.exists(CONFIG_FILE):" main.py && echo "   ✅ config.json 自动创建逻辑" || echo "   ❌ 缺少配置文件创建"
grep -q "if not os.path.exists(WATCH_FILE):" main.py && echo "   ✅ watch_config.json 自动创建逻辑" || echo "   ❌ 缺少监控配置创建"

echo
echo "3. 检查移动端优化..."
grep -q "class=\"full-text\"" templates/notes.html && echo "   ✅ 完整文本样式" || echo "   ❌ 缺少完整文本"
grep -q "class=\"compact-text\"" templates/notes.html && echo "   ✅ 紧凑文本样式" || echo "   ❌ 缺少紧凑文本"
grep -q "@media (max-width: 768px)" templates/notes.html && echo "   ✅ 移动端媒体查询" || echo "   ❌ 缺少移动端适配"
grep -q "@media (max-width: 480px)" templates/notes.html && echo "   ✅ 小屏幕媒体查询" || echo "   ❌ 缺少小屏幕适配"
grep -q "white-space: nowrap" templates/notes.html && echo "   ✅ 标题不换行" || echo "   ❌ 缺少防换行"

echo
echo "4. 检查搜索 UI..."
grep -q "search-icon-btn" templates/notes.html && echo "   ✅ 搜索图标按钮" || echo "   ❌ 缺少搜索图标"
grep -q "search-panel-overlay" templates/notes.html && echo "   ✅ 搜索面板遮罩" || echo "   ❌ 缺少遮罩层"
grep -q "search-panel" templates/notes.html && echo "   ✅ 搜索面板" || echo "   ❌ 缺少搜索面板"
grep -q "toggleSearchPanel" templates/notes.html && echo "   ✅ 搜索面板切换功能" || echo "   ❌ 缺少切换功能"

echo
echo "5. 检查多媒体支持..."
grep -q "note_media" database.py && echo "   ✅ note_media 表支持" || echo "   ❌ 缺少多媒体表"
grep -q "media_list" database.py && echo "   ✅ media_list 支持" || echo "   ❌ 缺少媒体列表"
grep -q "note-media-grid" templates/notes.html && echo "   ✅ 多图片网格布局" || echo "   ❌ 缺少网格布局"

echo
echo "6. 检查 Docker 配置..."
grep -q "DATA_DIR=/data/save_restricted_bot" docker-compose.yml && echo "   ✅ Docker 环境变量" || echo "   ❌ 缺少环境变量"
grep -q "/data/save_restricted_bot:/data/save_restricted_bot" docker-compose.yml && echo "   ✅ Docker volume 挂载" || echo "   ❌ 缺少 volume"

echo
echo "7. 检查测试脚本..."
[ -f "test_initialization.py" ] && echo "   ✅ test_initialization.py 存在" || echo "   ❌ 缺少测试脚本"

echo
echo "8. 检查文档..."
[ -f "IMPROVEMENTS_v2.3.1.md" ] && echo "   ✅ IMPROVEMENTS_v2.3.1.md 存在" || echo "   ❌ 缺少改进文档"
[ -f "UPDATE_v2.3.1.md" ] && echo "   ✅ UPDATE_v2.3.1.md 存在" || echo "   ❌ 缺少更新文档"

echo
echo "=========================================="
echo "验证完成！"
echo "=========================================="
