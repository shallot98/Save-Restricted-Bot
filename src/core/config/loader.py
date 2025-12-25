"""
配置加载器
==========

提供配置加载、合并和验证功能。
"""

import os
import json
import logging
from pathlib import Path
from typing import Type, Dict, Any, Optional, TypeVar
from pydantic import BaseModel, ValidationError

from .models import MainConfig, WatchConfig, WebDAVConfig, ViewerConfig, PathConfig
from .exceptions import ConfigLoadError, ConfigValidationError

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class ConfigLoader:
    """
    配置加载器

    负责从多个配置源加载配置，并按优先级合并。

    配置优先级（从高到低）：
    1. 环境变量
    2. 配置文件
    3. 默认值
    """

    def __init__(self):
        """初始化配置加载器"""
        self._env_cache: Dict[str, str] = {}

    def load_from_env(self, prefix: str = "", keys: Optional[list] = None) -> Dict[str, Any]:
        """
        从环境变量加载配置

        Args:
            prefix: 环境变量前缀（如 "WEBDAV_"）
            keys: 要加载的键列表，如果为None则加载所有

        Returns:
            配置字典

        Example:
            >>> loader = ConfigLoader()
            >>> config = loader.load_from_env(prefix="WEBDAV_", keys=["ENABLED", "URL"])
            >>> # 从环境变量 WEBDAV_ENABLED 和 WEBDAV_URL 加载
        """
        config = {}

        if keys is None:
            # 加载所有带前缀的环境变量
            for key, value in os.environ.items():
                if key.startswith(prefix):
                    # 移除前缀
                    config_key = key[len(prefix):] if prefix else key
                    config[config_key] = value
        else:
            # 只加载指定的键
            for key in keys:
                env_key = f"{prefix}{key}"
                value = os.environ.get(env_key)
                if value is not None:
                    config[key] = value

        logger.debug(f"从环境变量加载配置（前缀: {prefix}）: {len(config)} 项")
        return config

    def load_from_file(self, file_path: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        从JSON文件加载配置

        Args:
            file_path: 配置文件路径
            default: 默认配置（文件不存在时使用）

        Returns:
            配置字典

        Raises:
            ConfigLoadError: 文件读取或解析失败

        Example:
            >>> loader = ConfigLoader()
            >>> config = loader.load_from_file(Path("config.json"), default={})
        """
        if default is None:
            default = {}

        if not file_path.exists():
            logger.debug(f"配置文件不存在: {file_path}，使用默认值")
            return default

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.debug(f"从文件加载配置: {file_path}")
                return config
        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON解析失败: {file_path}, 错误: {e}")
            raise ConfigLoadError(str(file_path), f"JSON解析失败: {e}")
        except OSError as e:
            logger.error(f"配置文件读取失败: {file_path}, 错误: {e}")
            raise ConfigLoadError(str(file_path), f"文件读取失败: {e}")

    def merge_configs(
        self,
        env_config: Dict[str, Any],
        file_config: Dict[str, Any],
        default_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        合并多个配置源

        按优先级合并配置：环境变量 > 配置文件 > 默认值

        Args:
            env_config: 环境变量配置
            file_config: 文件配置
            default_config: 默认配置

        Returns:
            合并后的配置字典

        Example:
            >>> loader = ConfigLoader()
            >>> merged = loader.merge_configs(
            ...     env_config={"TOKEN": "env_token"},
            ...     file_config={"TOKEN": "file_token", "HASH": "file_hash"},
            ...     default_config={"TOKEN": "", "HASH": "", "ID": ""}
            ... )
            >>> # 结果: {"TOKEN": "env_token", "HASH": "file_hash", "ID": ""}
        """
        if default_config is None:
            default_config = {}

        # 从默认值开始
        merged = default_config.copy()

        # 应用文件配置（覆盖默认值）
        merged.update(file_config)

        # 应用环境变量配置（最高优先级）
        merged.update(env_config)

        logger.debug(
            f"合并配置: 默认值 {len(default_config)} 项, "
            f"文件 {len(file_config)} 项, "
            f"环境变量 {len(env_config)} 项, "
            f"最终 {len(merged)} 项"
        )

        return merged

    def validate_config(self, config_class: Type[T], config_data: Dict[str, Any]) -> T:
        """
        验证配置并创建Pydantic模型实例

        Args:
            config_class: Pydantic配置模型类
            config_data: 配置数据字典

        Returns:
            配置模型实例

        Raises:
            ConfigValidationError: 配置验证失败

        Example:
            >>> loader = ConfigLoader()
            >>> config = loader.validate_config(
            ...     MainConfig,
            ...     {"TOKEN": "abc123", "HASH": "xyz789"}
            ... )
        """
        try:
            # 使用Pydantic的model_validate方法验证并创建实例
            instance = config_class.model_validate(config_data)
            logger.debug(f"配置验证成功: {config_class.__name__}")
            return instance
        except ValidationError as e:
            logger.error(f"配置验证失败: {config_class.__name__}, 错误: {e}")
            # 提取第一个错误信息
            first_error = e.errors()[0]
            field_name = '.'.join(str(loc) for loc in first_error['loc'])
            raise ConfigValidationError(
                field_name=field_name,
                current_value=config_data.get(field_name),
                expected_format=first_error['type'],
                message=first_error['msg']
            )

    def load_and_validate(
        self,
        config_class: Type[T],
        file_path: Optional[Path] = None,
        env_prefix: str = "",
        default_config: Optional[Dict[str, Any]] = None
    ) -> T:
        """
        加载、合并并验证配置（一站式方法）

        Args:
            config_class: Pydantic配置模型类
            file_path: 配置文件路径（可选）
            env_prefix: 环境变量前缀（可选）
            default_config: 默认配置（可选）

        Returns:
            配置模型实例

        Example:
            >>> loader = ConfigLoader()
            >>> config = loader.load_and_validate(
            ...     MainConfig,
            ...     file_path=Path("config.json"),
            ...     env_prefix="",
            ...     default_config={}
            ... )
        """
        # 加载环境变量配置
        env_config = self.load_from_env(prefix=env_prefix)

        # 加载文件配置
        file_config = {}
        if file_path:
            try:
                file_config = self.load_from_file(file_path, default={})
            except ConfigLoadError as e:
                logger.warning(f"配置文件加载失败，使用默认值: {e}")

        # 合并配置
        merged_config = self.merge_configs(env_config, file_config, default_config)

        # 验证并创建模型实例
        return self.validate_config(config_class, merged_config)

    def save_to_file(self, config: BaseModel, file_path: Path) -> None:
        """
        保存配置到文件

        Args:
            config: Pydantic配置模型实例
            file_path: 配置文件路径

        Raises:
            ConfigSaveError: 文件保存失败

        Example:
            >>> loader = ConfigLoader()
            >>> config = MainConfig(TOKEN="abc123")
            >>> loader.save_to_file(config, Path("config.json"))
        """
        try:
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 序列化为字典
            config_dict = config.model_dump()

            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            logger.debug(f"配置已保存到文件: {file_path}")
        except OSError as e:
            logger.error(f"配置文件保存失败: {file_path}, 错误: {e}")
            from .exceptions import ConfigSaveError
            raise ConfigSaveError(str(file_path), str(e))


__all__ = ['ConfigLoader']
