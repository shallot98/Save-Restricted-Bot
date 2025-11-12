"""
配置管理模块 - 统一管理所有配置路径和环境变量
遵循 KISS 原则：简单明了的配置管理
"""
import os
import json
from pathlib import Path

class ConfigManager:
    """配置管理器 - 单一职责：管理所有配置"""

    def __init__(self):
        # 项目根目录
        self.project_root = Path(__file__).parent.parent

        # 数据目录 - 独立存储，防止更新时丢失
        self.data_dir = Path(os.environ.get('DATA_DIR', self.project_root / 'data'))
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 配置文件目录
        self.config_dir = self.data_dir / 'config'
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 媒体文件目录
        self.media_dir = self.data_dir / 'media'
        self.media_dir.mkdir(parents=True, exist_ok=True)

        # 数据库文件
        self.database_file = self.data_dir / 'notes.db'

        # Bot配置文件路径（优先从data目录读取，其次从根目录）
        self.bot_config_file = self._find_bot_config()

        # Watch配置文件
        self.watch_config_file = self.config_dir / 'watch_config.json'

        # 加载Bot配置
        self.bot_config = self._load_bot_config()

    def _find_bot_config(self) -> Path:
        """查找Bot配置文件 - 优先级：data/config > 根目录"""
        # 优先从data/config目录查找
        config_in_data = self.config_dir / 'config.json'
        if config_in_data.exists():
            print(f"✅ 使用配置文件: {config_in_data}")
            return config_in_data

        # 其次从根目录查找
        config_in_root = self.project_root / 'config.json'
        if config_in_root.exists():
            print(f"✅ 使用配置文件: {config_in_root}")
            return config_in_root

        # 都不存在，返回默认位置（data/config）
        print(f"⚠️ 配置文件不存在，将使用: {config_in_data}")
        return config_in_data

    def _load_bot_config(self) -> dict:
        """加载Bot配置"""
        if not self.bot_config_file.exists():
            print(f"⚠️ 配置文件不存在: {self.bot_config_file}")
            return {}

        try:
            with open(self.bot_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"✅ 成功加载配置文件")
                return config
        except Exception as e:
            print(f"❌ 加载配置文件失败: {e}")
            return {}

    def get_env(self, key: str, default=None):
        """获取配置值 - 优先从环境变量，其次从配置文件"""
        # 优先从环境变量获取
        env_value = os.environ.get(key)
        if env_value is not None:
            return env_value

        # 其次从配置文件获取
        config_value = self.bot_config.get(key, default)
        return config_value

    def get_bot_token(self) -> str:
        """获取Bot Token"""
        return self.get_env("TOKEN", "")

    def get_api_id(self) -> str:
        """获取API ID"""
        return self.get_env("ID", "")

    def get_api_hash(self) -> str:
        """获取API Hash"""
        return self.get_env("HASH", "")

    def get_session_string(self) -> str:
        """获取Session String"""
        return self.get_env("STRING")

    def load_watch_config(self) -> dict:
        """加载监控配置"""
        if not self.watch_config_file.exists():
            return {}

        try:
            with open(self.watch_config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 加载监控配置失败: {e}")
            return {}

    def save_watch_config(self, config: dict):
        """保存监控配置"""
        try:
            with open(self.watch_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print(f"✅ 监控配置已保存")
        except Exception as e:
            print(f"❌ 保存监控配置失败: {e}")

    def __str__(self):
        """打印配置信息"""
        return f"""
配置管理器状态：
- 项目根目录: {self.project_root}
- 数据目录: {self.data_dir}
- 配置目录: {self.config_dir}
- 媒体目录: {self.media_dir}
- 数据库文件: {self.database_file}
- Bot配置文件: {self.bot_config_file}
- Watch配置文件: {self.watch_config_file}
"""

# 全局配置实例 - 单例模式
_config_instance = None

def get_config() -> ConfigManager:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance
