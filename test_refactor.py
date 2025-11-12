"""
重构功能测试脚本
测试配置管理、记录服务等模块是否正常工作
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config_manager():
    """测试配置管理器"""
    print("\n" + "="*60)
    print("测试1：配置管理器")
    print("="*60)

    try:
        from config.config_manager import get_config

        config = get_config()
        print("✅ 配置管理器导入成功")
        print(config)

        # 测试获取配置
        bot_token = config.get_bot_token()
        api_id = config.get_api_id()
        api_hash = config.get_api_hash()

        if bot_token:
            print(f"✅ Bot Token: {bot_token[:10]}...")
        else:
            print("⚠️ Bot Token 未配置")

        if api_id:
            print(f"✅ API ID: {api_id}")
        else:
            print("⚠️ API ID 未配置")

        if api_hash:
            print(f"✅ API Hash: {api_hash[:10]}...")
        else:
            print("⚠️ API Hash 未配置")

        # 测试路径
        print(f"\n📁 数据目录: {config.data_dir}")
        print(f"📁 配置目录: {config.config_dir}")
        print(f"📁 媒体目录: {config.media_dir}")
        print(f"📄 数据库文件: {config.database_file}")

        return True

    except Exception as e:
        print(f"❌ 配置管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_services():
    """测试服务模块"""
    print("\n" + "="*60)
    print("测试2：服务模块")
    print("="*60)

    try:
        from services.filter_service import FilterService
        print("✅ FilterService 导入成功")

        # 测试过滤服务
        filter_service = FilterService()

        # 测试关键词白名单
        test_text = "这是一条重要的测试消息"
        watch_config = {"whitelist": ["重要", "紧急"]}

        result = filter_service.should_process_message(test_text, watch_config)
        if result:
            print("✅ 关键词白名单测试通过")
        else:
            print("❌ 关键词白名单测试失败")

        # 测试关键词黑名单
        watch_config = {"blacklist": ["广告", "推广"]}
        result = filter_service.should_process_message(test_text, watch_config)
        if result:
            print("✅ 关键词黑名单测试通过")
        else:
            print("❌ 关键词黑名单测试失败")

        return True

    except Exception as e:
        print(f"❌ 服务模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database():
    """测试数据库"""
    print("\n" + "="*60)
    print("测试3：数据库")
    print("="*60)

    try:
        import database

        # 测试数据库初始化
        database.init_database()
        print("✅ 数据库初始化成功")

        # 测试添加笔记
        note_id = database.add_note(
            user_id=123456789,
            source_chat_id="-1001234567890",
            source_name="测试频道",
            message_text="这是一条测试笔记",
            media_type=None,
            media_path=None
        )
        print(f"✅ 添加笔记成功，ID: {note_id}")

        # 测试获取笔记
        notes = database.get_notes(limit=1)
        if notes:
            print(f"✅ 获取笔记成功，共 {len(notes)} 条")
            print(f"   最新笔记: {notes[0]['message_text'][:50]}...")
        else:
            print("⚠️ 数据库中暂无笔记")

        # 测试获取笔记数量
        count = database.get_note_count()
        print(f"✅ 数据库中共有 {count} 条笔记")

        return True

    except Exception as e:
        print(f"❌ 数据库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_watch_config():
    """测试监控配置"""
    print("\n" + "="*60)
    print("测试4：监控配置")
    print("="*60)

    try:
        from config.config_manager import get_config

        config = get_config()

        # 测试加载监控配置
        watch_config = config.load_watch_config()
        print(f"✅ 加载监控配置成功")

        if watch_config:
            total_tasks = sum(len(watches) for watches in watch_config.values())
            print(f"   共有 {len(watch_config)} 个用户")
            print(f"   共有 {total_tasks} 个监控任务")

            # 显示监控任务详情
            for user_id, watches in watch_config.items():
                print(f"\n   用户 {user_id}:")
                for watch_key, watch_data in watches.items():
                    if isinstance(watch_data, dict):
                        source = watch_data.get("source", "未知")
                        dest = watch_data.get("dest", "未知")
                        record_mode = watch_data.get("record_mode", False)

                        if record_mode:
                            print(f"      📝 {source} → 记录模式")
                        else:
                            print(f"      📤 {source} → {dest}")
                    else:
                        print(f"      📤 {watch_key} → {watch_data}")
        else:
            print("   ⚠️ 暂无监控任务")

        return True

    except Exception as e:
        print(f"❌ 监控配置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    # 设置UTF-8编码输出
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

    print("\n" + "="*60)
    print("开始测试重构后的模块")
    print("="*60)

    results = []

    # 运行所有测试
    results.append(("配置管理器", test_config_manager()))
    results.append(("服务模块", test_services()))
    results.append(("数据库", test_database()))
    results.append(("监控配置", test_watch_config()))

    # 输出测试结果
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)

    passed = 0
    failed = 0

    for name, result in results:
        if result:
            print(f"✅ {name}: 通过")
            passed += 1
        else:
            print(f"❌ {name}: 失败")
            failed += 1

    print(f"\n总计: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("\n所有测试通过！重构成功！")
        return 0
    else:
        print(f"\n有 {failed} 个测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())
