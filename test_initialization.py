#!/usr/bin/env python3
"""
测试 DATA_DIR 初始化和配置文件自动创建功能
"""

import os
import json
import tempfile
import shutil

def test_data_dir_initialization():
    """测试 DATA_DIR 目录初始化"""
    print("=" * 60)
    print("测试 DATA_DIR 初始化功能")
    print("=" * 60)
    print()
    
    # 创建临时目录模拟 DATA_DIR
    temp_dir = tempfile.mkdtemp(prefix='test_data_dir_')
    print(f"创建临时测试目录: {temp_dir}")
    
    try:
        # 设置环境变量
        os.environ['DATA_DIR'] = temp_dir
        os.environ['TOKEN'] = 'test_token_123'
        os.environ['ID'] = '12345'
        os.environ['HASH'] = 'test_hash_abc'
        os.environ['STRING'] = 'test_session_string'
        
        # 模拟 main.py 的初始化代码
        DATA_DIR = os.environ.get('DATA_DIR', '/data/save_restricted_bot')
        CONFIG_DIR = os.path.join(DATA_DIR, 'config')
        
        print()
        print("1. 创建目录结构...")
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(os.path.join(DATA_DIR, 'media'), exist_ok=True)
        os.makedirs(os.path.join(DATA_DIR, 'logs'), exist_ok=True)
        print(f"   ✅ 创建 {CONFIG_DIR}")
        print(f"   ✅ 创建 {os.path.join(DATA_DIR, 'media')}")
        print(f"   ✅ 创建 {os.path.join(DATA_DIR, 'logs')}")
        
        # 验证目录存在
        assert os.path.exists(CONFIG_DIR), "CONFIG_DIR 不存在"
        assert os.path.exists(os.path.join(DATA_DIR, 'media')), "media 目录不存在"
        assert os.path.exists(os.path.join(DATA_DIR, 'logs')), "logs 目录不存在"
        
        print()
        print("2. 创建配置文件...")
        
        # 创建 config.json
        CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
        if not os.path.exists(CONFIG_FILE):
            default_config = {
                "TOKEN": os.environ.get('TOKEN', ''),
                "ID": os.environ.get('ID', ''),
                "HASH": os.environ.get('HASH', ''),
                "STRING": os.environ.get('STRING', '')
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            print(f"   ✅ 创建 {CONFIG_FILE}")
        
        # 创建 watch_config.json
        WATCH_FILE = os.path.join(CONFIG_DIR, 'watch_config.json')
        if not os.path.exists(WATCH_FILE):
            default_watch_config = {}
            with open(WATCH_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_watch_config, f, indent=4, ensure_ascii=False)
            print(f"   ✅ 创建 {WATCH_FILE}")
        
        print()
        print("3. 验证配置文件内容...")
        
        # 验证 config.json
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        assert config['TOKEN'] == 'test_token_123', "TOKEN 不匹配"
        assert config['ID'] == '12345', "ID 不匹配"
        assert config['HASH'] == 'test_hash_abc', "HASH 不匹配"
        assert config['STRING'] == 'test_session_string', "STRING 不匹配"
        print("   ✅ config.json 内容正确")
        
        # 验证 watch_config.json
        with open(WATCH_FILE, 'r', encoding='utf-8') as f:
            watch_config = json.load(f)
        
        assert watch_config == {}, "watch_config.json 应该是空字典"
        print("   ✅ watch_config.json 内容正确")
        
        print()
        print("4. 测试目录结构...")
        expected_structure = {
            'config': ['config.json', 'watch_config.json'],
            'media': [],
            'logs': []
        }
        
        for dir_name, files in expected_structure.items():
            dir_path = os.path.join(DATA_DIR, dir_name)
            assert os.path.exists(dir_path), f"{dir_name} 目录不存在"
            print(f"   ✅ {dir_name}/ 目录存在")
            
            for file_name in files:
                file_path = os.path.join(dir_path, file_name)
                assert os.path.exists(file_path), f"{file_name} 文件不存在"
                print(f"      ✅ {file_name} 存在")
        
        print()
        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print()
        print("测试目录结构:")
        for root, dirs, files in os.walk(DATA_DIR):
            level = root.replace(DATA_DIR, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f'{indent}{os.path.basename(root)}/')
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                print(f'{subindent}{file}')
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    
    finally:
        # 清理临时目录
        print()
        print(f"清理临时目录: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        success = test_data_dir_initialization()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n测试已取消")
        exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        exit(1)
