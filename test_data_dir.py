#!/usr/bin/env python3
"""
测试 DATA_DIR 配置是否正确
"""

import os
import sys

# 模拟环境变量
DATA_DIR = os.environ.get('DATA_DIR', '/data/save_restricted_bot')
CONFIG_DIR = os.path.join(DATA_DIR, 'config')

print("=" * 60)
print("DATA_DIR 配置测试")
print("=" * 60)
print()

print(f"✅ DATA_DIR: {DATA_DIR}")
print(f"✅ CONFIG_DIR: {CONFIG_DIR}")
print()

# 检查目录结构
expected_dirs = [
    DATA_DIR,
    CONFIG_DIR,
    os.path.join(DATA_DIR, 'media'),
    os.path.join(DATA_DIR, 'logs')
]

print("预期目录结构:")
for dir_path in expected_dirs:
    exists = "✅ 存在" if os.path.exists(dir_path) else "❌ 不存在"
    print(f"  {dir_path}: {exists}")

print()

# 检查配置文件
config_files = [
    os.path.join(CONFIG_DIR, 'config.json'),
    os.path.join(CONFIG_DIR, 'watch_config.json')
]

print("配置文件:")
for file_path in config_files:
    exists = "✅ 存在" if os.path.exists(file_path) else "❌ 不存在"
    print(f"  {file_path}: {exists}")

print()
print("=" * 60)
print("测试完成")
print("=" * 60)
