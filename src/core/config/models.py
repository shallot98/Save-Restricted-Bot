"""
配置模型定义
============

使用Pydantic定义强类型配置模型，支持：
- 类型验证
- 环境变量加载
- 默认值设置
- 配置文件持久化
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PathConfig(BaseModel):
    """路径配置模型"""

    base_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent.parent,
        description="项目根目录"
    )

    data_dir: Optional[Path] = Field(
        default=None,
        description="数据目录，可通过DATA_DIR环境变量覆盖"
    )

    @field_validator('data_dir', mode='before')
    @classmethod
    def resolve_data_dir(cls, v, info):
        """解析数据目录路径"""
        if v is not None:
            return Path(v)

        # 从环境变量读取
        env_dir = os.environ.get('DATA_DIR')
        if env_dir:
            return Path(env_dir)

        # 使用默认值
        base_dir = info.data.get('base_dir', Path(__file__).parent.parent.parent.parent)
        return base_dir / 'data'

    @property
    def config_dir(self) -> Path:
        """配置文件目录"""
        return self.data_dir / 'config'

    @property
    def media_dir(self) -> Path:
        """媒体文件目录"""
        return self.data_dir / 'media'

    @property
    def config_file(self) -> Path:
        """主配置文件路径"""
        return self.config_dir / 'config.json'

    @property
    def watch_file(self) -> Path:
        """监控配置文件路径"""
        return self.config_dir / 'watch_config.json'

    @property
    def webdav_file(self) -> Path:
        """WebDAV配置文件路径"""
        return self.config_dir / 'webdav_config.json'

    @property
    def viewer_file(self) -> Path:
        """查看器配置文件路径"""
        return self.config_dir / 'viewer_config.json'

    def ensure_directories(self) -> None:
        """确保所有必需的目录存在"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

    model_config = SettingsConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True
    )


class MainConfig(BaseSettings):
    """主配置模型 - Telegram Bot核心配置"""

    TOKEN: str = Field(
        default="",
        description="Telegram Bot Token"
    )

    HASH: str = Field(
        default="",
        description="Telegram API Hash"
    )

    ID: str = Field(
        default="",
        description="Telegram API ID"
    )

    STRING: str = Field(
        default="",
        description="Telegram Session String"
    )

    OWNER_ID: str = Field(
        default="",
        description="Bot所有者的Telegram用户ID"
    )

    @field_validator('TOKEN', 'HASH', 'ID', 'STRING', 'OWNER_ID')
    @classmethod
    def validate_not_empty(cls, v: str, info) -> str:
        """验证必填字段不为空（在生产环境）"""
        # 开发环境允许为空
        if not v and os.environ.get('ENV') == 'production':
            raise ValueError(f"{info.field_name} 在生产环境中不能为空")
        return v

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='allow'  # 允许额外字段，保持向后兼容
    )


class WatchConfig(BaseModel):
    """监控配置模型 - 用户监控源映射"""

    sources: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="用户ID到监控源的映射 {user_id: {source_id: source_config}}"
    )

    def get_user_sources(self, user_id: str) -> Dict[str, Any]:
        """获取指定用户的监控源"""
        return self.sources.get(user_id, {})

    def set_user_sources(self, user_id: str, sources_config: Dict[str, Any]) -> None:
        """设置指定用户的监控源"""
        self.sources[user_id] = sources_config

    def get_all_source_ids(self) -> set:
        """获取所有监控源ID"""
        source_ids = set()
        for user_sources in self.sources.values():
            if isinstance(user_sources, dict):
                for source_key in user_sources.keys():
                    # 提取source_id（格式：source_id|dest_id 或 source_id|record）
                    if '|' in source_key:
                        source_id = source_key.split('|')[0]
                    else:
                        source_id = source_key
                    source_ids.add(source_id)
        return source_ids

    model_config = SettingsConfigDict(
        validate_assignment=True,
        extra='allow'
    )


class WebDAVConfig(BaseSettings):
    """WebDAV配置模型 - 远程存储配置"""

    enabled: bool = Field(
        default=False,
        description="是否启用WebDAV存储"
    )

    url: str = Field(
        default="",
        description="WebDAV服务器URL"
    )

    username: str = Field(
        default="",
        description="WebDAV用户名"
    )

    password: str = Field(
        default="",
        description="WebDAV密码"
    )

    base_path: str = Field(
        default="/telegram_media",
        description="WebDAV基础路径"
    )

    keep_local_copy: bool = Field(
        default=False,
        description="是否保留本地副本"
    )

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str, info) -> str:
        """验证URL格式"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError("WebDAV URL必须以http://或https://开头")
        return v

    model_config = SettingsConfigDict(
        env_prefix='WEBDAV_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='allow'
    )


class ViewerConfig(BaseSettings):
    """查看器配置模型 - 外部查看器配置"""

    viewer_url: str = Field(
        default="https://example.com/watch?dn=",
        description="外部查看器URL模板"
    )

    @field_validator('viewer_url')
    @classmethod
    def validate_viewer_url(cls, v: str) -> str:
        """验证查看器URL格式"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("查看器URL必须以http://或https://开头")
        return v

    model_config = SettingsConfigDict(
        env_prefix='VIEWER_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='allow'
    )


# 导出所有配置模型
__all__ = [
    'PathConfig',
    'MainConfig',
    'WatchConfig',
    'WebDAVConfig',
    'ViewerConfig',
]
