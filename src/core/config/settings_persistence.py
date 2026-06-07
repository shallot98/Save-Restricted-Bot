"""Persistence helpers for legacy Settings."""

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict

from .exceptions import ConfigSaveError

logger = logging.getLogger(__name__)


class SettingsPersistenceMixin:
    """JSON persistence helpers shared by Settings."""

    def _load_json_config(self, path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
        """Load JSON configuration from file."""
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load config from {path}: {e}")

        self._save_json_config(path, default)
        return default

    def _save_json_config(self, path: Path, config: Dict[str, Any]) -> None:
        """Save configuration to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

    def _persist_config(self, path: Path, config: Dict[str, Any]) -> None:
        """Atomically persist a JSON configuration file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
            )
            self._write_temp_config(temp_fd, temp_path, path, config=config)
        except Exception as e:
            logger.error(f"配置持久化失败: {path}, 错误: {e}")
            raise ConfigSaveError(str(path), str(e))

    def _write_temp_config(
        self,
        temp_fd: int,
        temp_path: str,
        path: Path,
        *,
        config: Dict[str, Any],
    ) -> None:
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            if path.exists():
                backup_path = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, backup_path)
                logger.debug(f"配置文件已备份: {backup_path}")

            os.replace(temp_path, path)
            logger.debug(f"配置已保存: {path}")
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    @staticmethod
    def _get_env_config() -> Dict[str, Any]:
        """Get configuration from environment variables."""
        config = {}
        for key in ["TOKEN", "HASH", "ID", "STRING", "OWNER_ID"]:
            value = os.environ.get(key)
            if value:
                config[key] = value
        return config

    @staticmethod
    def _default_webdav_config() -> Dict[str, Any]:
        """Default WebDAV configuration."""
        return {
            "enabled": False,
            "url": "",
            "username": "",
            "password": "",
            "base_path": "/telegram_media",
            "keep_local_copy": False,
        }

    @staticmethod
    def _default_viewer_config() -> Dict[str, Any]:
        """Default viewer configuration."""
        return {
            "viewer_url": "https://example.com/watch?dn=",
        }
