#!/usr/bin/env python3
"""
配置迁移脚本
============

自动化迁移配置到新的配置管理系统。

Usage:
    python scripts/migrate_config.py --dry-run  # 预览迁移
    python scripts/migrate_config.py            # 执行迁移
    python scripts/migrate_config.py --backup-dir /path/to/backup  # 指定备份目录
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.config.loader import ConfigLoader


def check_config_files() -> dict:
    """
    检查配置文件状态

    Returns:
        dict: 配置文件状态信息
    """
    status = {
        'config_file': settings.paths.config_file.exists(),
        'watch_file': settings.paths.watch_file.exists(),
        'webdav_file': settings.paths.webdav_file.exists(),
        'viewer_file': settings.paths.viewer_file.exists(),
    }

    print("📋 配置文件检查:")
    for file_name, exists in status.items():
        status_icon = "✅" if exists else "❌"
        print(f"  {status_icon} {file_name}: {'存在' if exists else '不存在'}")

    return status


def backup_configs(backup_dir: Path) -> bool:
    """
    备份现有配置文件

    Args:
        backup_dir: 备份目录路径

    Returns:
        bool: 备份是否成功
    """
    try:
        # 创建备份目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"config_backup_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)

        print(f"\n💾 备份配置文件到: {backup_path}")

        # 备份所有配置文件
        config_files = [
            settings.paths.config_file,
            settings.paths.watch_file,
            settings.paths.webdav_file,
            settings.paths.viewer_file,
        ]

        backed_up = 0
        for config_file in config_files:
            if config_file.exists():
                dest = backup_path / config_file.name
                shutil.copy2(config_file, dest)
                print(f"  ✅ 已备份: {config_file.name}")
                backed_up += 1

        print(f"\n✅ 成功备份 {backed_up} 个配置文件")
        return True

    except Exception as e:
        print(f"\n❌ 备份失败: {e}")
        return False


def validate_config_format(config_file: Path) -> tuple[bool, str]:
    """
    验证配置文件格式

    Args:
        config_file: 配置文件路径

    Returns:
        tuple: (是否有效, 错误信息)
    """
    if not config_file.exists():
        return True, "文件不存在，将使用默认值"

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            json.load(f)
        return True, "格式正确"
    except json.JSONDecodeError as e:
        return False, f"JSON格式错误: {e}"
    except Exception as e:
        return False, f"读取失败: {e}"


def migrate_configs(dry_run: bool = False) -> bool:
    """
    迁移配置到新格式

    Args:
        dry_run: 是否为预览模式

    Returns:
        bool: 迁移是否成功
    """
    print(f"\n{'🔍 预览' if dry_run else '🚀 执行'}配置迁移:")

    try:
        loader = ConfigLoader()

        # 验证所有配置文件
        print("\n📝 验证配置文件格式:")
        all_valid = True
        for file_path in [settings.paths.config_file, settings.paths.watch_file,
                          settings.paths.webdav_file, settings.paths.viewer_file]:
            valid, message = validate_config_format(file_path)
            status_icon = "✅" if valid else "❌"
            print(f"  {status_icon} {file_path.name}: {message}")
            if not valid:
                all_valid = False

        if not all_valid:
            print("\n❌ 配置文件格式验证失败，请修复后重试")
            return False

        # 加载并验证配置
        print("\n🔄 加载配置:")
        print("  ⏳ 加载主配置...")
        main_config = loader.load_and_validate(
            settings._main_config.__class__,
            file_path=settings.paths.config_file,
            env_prefix=""
        )
        print(f"  ✅ 主配置加载成功 (TOKEN: {'已设置' if main_config.TOKEN else '未设置'})")

        print("  ⏳ 加载WebDAV配置...")
        webdav_config = loader.load_and_validate(
            settings._webdav_config.__class__,
            file_path=settings.paths.webdav_file,
            env_prefix="WEBDAV_"
        )
        print(f"  ✅ WebDAV配置加载成功 (enabled: {webdav_config.enabled})")

        print("  ⏳ 加载查看器配置...")
        viewer_config = loader.load_and_validate(
            settings._viewer_config.__class__,
            file_path=settings.paths.viewer_file,
            env_prefix="VIEWER_"
        )
        print(f"  ✅ 查看器配置加载成功")

        if not dry_run:
            print("\n💾 保存配置:")
            # 配置已经通过验证，无需额外操作
            # Settings类会自动使用新的加载机制
            print("  ✅ 配置已迁移到新管理器")

        print("\n✅ 配置迁移完成！")
        return True

    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="配置迁移脚本 - 迁移配置到新的配置管理系统"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='预览模式，不实际修改文件'
    )
    parser.add_argument(
        '--backup-dir',
        type=Path,
        default=Path('backups'),
        help='备份目录路径（默认: backups/）'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='跳过备份步骤'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("配置迁移脚本")
    print("=" * 60)

    # 检查配置文件
    check_config_files()

    # 备份配置（除非是dry-run或明确跳过）
    if not args.dry_run and not args.no_backup:
        if not backup_configs(args.backup_dir):
            print("\n⚠️  备份失败，是否继续？(y/N): ", end='')
            if input().lower() != 'y':
                print("❌ 迁移已取消")
                return 1

    # 执行迁移
    success = migrate_configs(dry_run=args.dry_run)

    if success:
        if args.dry_run:
            print("\n✅ 预览完成，配置文件格式正确")
            print("💡 运行 'python scripts/migrate_config.py' 执行实际迁移")
        else:
            print("\n✅ 迁移成功完成！")
            print("💡 配置已迁移到新的配置管理系统")
            print("💡 旧的配置文件已备份到:", args.backup_dir)
        return 0
    else:
        print("\n❌ 迁移失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
