"""Path configuration for legacy Settings."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PathConfig:
    """Path configuration for data directories."""

    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)

    @property
    def data_dir(self) -> Path:
        """Data directory path."""
        env_dir = os.environ.get("DATA_DIR")
        if env_dir:
            return Path(env_dir)
        return self.base_dir / "data"

    @property
    def config_dir(self) -> Path:
        """Configuration directory path."""
        return self.data_dir / "config"

    @property
    def media_dir(self) -> Path:
        """Media storage directory path."""
        return self.data_dir / "media"

    @property
    def config_file(self) -> Path:
        """Main config file path."""
        return self.config_dir / "config.json"

    @property
    def watch_file(self) -> Path:
        """Watch config file path."""
        return self.config_dir / "watch_config.json"

    @property
    def webdav_file(self) -> Path:
        """WebDAV config file path."""
        return self.config_dir / "webdav_config.json"

    @property
    def viewer_file(self) -> Path:
        """Viewer config file path."""
        return self.config_dir / "viewer_config.json"

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)
