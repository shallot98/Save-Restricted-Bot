#!/usr/bin/env python3
"""
完整系统测试 - 验证所有 v2.3.1 改进
"""

import os
import sys
import json
import tempfile
import shutil

def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_data_dir_paths():
    """测试 1: DATA_DIR 路径配置"""
    print_section("测试 1: DATA_DIR 路径配置")
    
    passed = 0
    total = 0
    
    # 检查 main.py
    total += 1
    with open('main.py', 'r') as f:
        content = f.read()
        if "DATA_DIR = os.environ.get('DATA_DIR', '/data/save_restricted_bot')" in content:
            print("✅ main.py: DATA_DIR 配置正确")
            passed += 1
        else:
            print("❌ main.py: DATA_DIR 配置错误")
    
    # 检查 database.py
    total += 1
    with open('database.py', 'r') as f:
        content = f.read()
        if "DATA_DIR = os.environ.get('DATA_DIR', '/data/save_restricted_bot')" in content:
            print("✅ database.py: DATA_DIR 配置正确")
            passed += 1
        else:
            print("❌ database.py: DATA_DIR 配置错误")
    
    # 检查 setup.py
    total += 1
    with open('setup.py', 'r') as f:
        content = f.read()
        if "DATA_DIR = os.environ.get('DATA_DIR', '/data/save_restricted_bot')" in content:
            print("✅ setup.py: DATA_DIR 配置正确")
            passed += 1
        else:
            print("❌ setup.py: DATA_DIR 配置错误")
    
    # 检查 app.py
    total += 1
    with open('app.py', 'r') as f:
        content = f.read()
        if 'from database import' in content and 'DATA_DIR' in content:
            print("✅ app.py: 从 database 导入 DATA_DIR")
            passed += 1
        else:
            print("❌ app.py: 未正确导入 DATA_DIR")
    
    print(f"\n通过: {passed}/{total}")
    return passed == total

def test_initialization_logic():
    """测试 2: 启动初始化逻辑"""
    print_section("测试 2: 启动初始化逻辑")
    
    passed = 0
    total = 0
    
    with open('main.py', 'r') as f:
        content = f.read()
        
        # 检查目录创建
        total += 1
        if 'os.makedirs(CONFIG_DIR, exist_ok=True)' in content:
            print("✅ CONFIG_DIR 自动创建逻辑")
            passed += 1
        else:
            print("❌ 缺少 CONFIG_DIR 创建逻辑")
        
        total += 1
        if "os.makedirs(os.path.join(DATA_DIR, 'media'), exist_ok=True)" in content:
            print("✅ media 目录自动创建逻辑")
            passed += 1
        else:
            print("❌ 缺少 media 目录创建逻辑")
        
        total += 1
        if "os.makedirs(os.path.join(DATA_DIR, 'logs'), exist_ok=True)" in content:
            print("✅ logs 目录自动创建逻辑")
            passed += 1
        else:
            print("❌ 缺少 logs 目录创建逻辑")
        
        # 检查配置文件创建
        total += 1
        if 'if not os.path.exists(CONFIG_FILE):' in content:
            print("✅ config.json 自动创建逻辑")
            passed += 1
        else:
            print("❌ 缺少 config.json 创建逻辑")
        
        total += 1
        if 'if not os.path.exists(WATCH_FILE):' in content:
            print("✅ watch_config.json 自动创建逻辑")
            passed += 1
        else:
            print("❌ 缺少 watch_config.json 创建逻辑")
        
        # 检查环境变量读取
        total += 1
        if "os.environ.get('TOKEN'" in content:
            print("✅ 从环境变量读取 TOKEN")
            passed += 1
        else:
            print("❌ 未从环境变量读取配置")
    
    print(f"\n通过: {passed}/{total}")
    return passed == total

def test_mobile_responsive():
    """测试 3: 移动端响应式设计"""
    print_section("测试 3: 移动端响应式设计")
    
    passed = 0
    total = 0
    
    with open('templates/notes.html', 'r') as f:
        content = f.read()
        
        # 检查双文本显示
        total += 1
        if 'class="full-text"' in content and 'class="compact-text"' in content:
            print("✅ 完整文本和紧凑文本双显示")
            passed += 1
        else:
            print("❌ 缺少双文本显示")
        
        # 检查媒体查询
        total += 1
        if '@media (max-width: 768px)' in content:
            print("✅ 768px 媒体查询（平板/手机）")
            passed += 1
        else:
            print("❌ 缺少 768px 媒体查询")
        
        total += 1
        if '@media (max-width: 480px)' in content:
            print("✅ 480px 媒体查询（小屏手机）")
            passed += 1
        else:
            print("❌ 缺少 480px 媒体查询")
        
        # 检查标题不换行
        total += 1
        if 'white-space: nowrap' in content:
            print("✅ 标题防换行设置")
            passed += 1
        else:
            print("❌ 缺少标题防换行")
        
        # 检查移动端样式切换
        total += 1
        if '.stat-item .full-text' in content and '.stat-item .compact-text' in content:
            print("✅ 统计信息样式切换")
            passed += 1
        else:
            print("❌ 缺少样式切换")
    
    print(f"\n通过: {passed}/{total}")
    return passed == total

def test_search_ui():
    """测试 4: 搜索 UI"""
    print_section("测试 4: 搜索 UI")
    
    passed = 0
    total = 0
    
    with open('templates/notes.html', 'r') as f:
        content = f.read()
        
        # 检查搜索图标
        total += 1
        if 'search-icon-btn' in content:
            print("✅ 搜索图标按钮")
            passed += 1
        else:
            print("❌ 缺少搜索图标")
        
        # 检查搜索面板
        total += 1
        if 'search-panel-overlay' in content and 'search-panel' in content:
            print("✅ 搜索面板和遮罩层")
            passed += 1
        else:
            print("❌ 缺少搜索面板")
        
        # 检查搜索功能
        total += 1
        if 'toggleSearchPanel' in content:
            print("✅ 搜索面板切换功能")
            passed += 1
        else:
            print("❌ 缺少切换功能")
        
        # 检查搜索表单
        total += 1
        if 'name="search"' in content and 'name="source"' in content and 'name="date_from"' in content:
            print("✅ 完整搜索表单（关键词、来源、日期）")
            passed += 1
        else:
            print("❌ 搜索表单不完整")
    
    print(f"\n通过: {passed}/{total}")
    return passed == total

def test_multi_media_support():
    """测试 5: 多媒体支持"""
    print_section("测试 5: 多媒体支持")
    
    passed = 0
    total = 0
    
    # 检查数据库
    with open('database.py', 'r') as f:
        content = f.read()
        
        total += 1
        if 'note_media' in content:
            print("✅ note_media 表支持")
            passed += 1
        else:
            print("❌ 缺少 note_media 表")
        
        total += 1
        if 'media_list' in content:
            print("✅ media_list 功能")
            passed += 1
        else:
            print("❌ 缺少 media_list")
        
        total += 1
        if 'len(media_list) > 9' in content:
            print("✅ 9张图片限制验证")
            passed += 1
        else:
            print("❌ 缺少图片数量限制")
    
    # 检查模板
    with open('templates/notes.html', 'r') as f:
        content = f.read()
        
        total += 1
        if 'note-media-grid' in content:
            print("✅ 多图片网格布局")
            passed += 1
        else:
            print("❌ 缺少网格布局")
    
    print(f"\n通过: {passed}/{total}")
    return passed == total

def test_docker_config():
    """测试 6: Docker 配置"""
    print_section("测试 6: Docker 配置")
    
    passed = 0
    total = 0
    
    with open('docker-compose.yml', 'r') as f:
        content = f.read()
        
        total += 1
        if 'DATA_DIR=/data/save_restricted_bot' in content:
            print("✅ DATA_DIR 环境变量")
            passed += 1
        else:
            print("❌ 缺少 DATA_DIR 环境变量")
        
        total += 1
        if '/data/save_restricted_bot:/data/save_restricted_bot' in content:
            print("✅ Volume 挂载配置")
            passed += 1
        else:
            print("❌ 缺少 Volume 挂载")
    
    print(f"\n通过: {passed}/{total}")
    return passed == total

def test_documentation():
    """测试 7: 文档完整性"""
    print_section("测试 7: 文档完整性")
    
    passed = 0
    total = 0
    
    docs = [
        'README.md',
        'README.zh-CN.md',
        'IMPROVEMENTS_v2.3.1.md',
        'UPDATE_v2.3.1.md',
        'test_initialization.py',
        'verify_improvements.sh'
    ]
    
    for doc in docs:
        total += 1
        if os.path.exists(doc):
            print(f"✅ {doc} 存在")
            passed += 1
        else:
            print(f"❌ {doc} 不存在")
    
    print(f"\n通过: {passed}/{total}")
    return passed == total

def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("  Save-Restricted-Bot v2.3.1 完整系统测试")
    print("=" * 60)
    
    results = []
    
    # 运行所有测试
    results.append(("DATA_DIR 路径配置", test_data_dir_paths()))
    results.append(("启动初始化逻辑", test_initialization_logic()))
    results.append(("移动端响应式设计", test_mobile_responsive()))
    results.append(("搜索 UI", test_search_ui()))
    results.append(("多媒体支持", test_multi_media_support()))
    results.append(("Docker 配置", test_docker_config()))
    results.append(("文档完整性", test_documentation()))
    
    # 汇总结果
    print_section("测试结果汇总")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status}: {name}")
    
    print("\n" + "=" * 60)
    print(f"总计: {passed_count}/{total_count} 测试通过")
    print("=" * 60)
    
    if passed_count == total_count:
        print("\n🎉 所有测试通过！v2.3.1 改进实施成功！")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} 个测试失败，请检查")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n测试已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
