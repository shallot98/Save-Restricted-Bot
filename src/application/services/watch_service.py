"""
Watch Application Service
=========================

Orchestrates watch/monitoring operations.
"""

import logging
from typing import Optional, List, Set

from src.domain.entities.watch import WatchTask, WatchConfig
from src.domain.repositories.watch_repository import WatchRepository
from src.domain.services.filter_service import FilterService
from src.core.exceptions import NotFoundError
from src.core.interfaces import ConfigCache, ConfigCacheProvider
from src.application.services.cache_fallback import resolve_cache
from src.application.services.watch_task_requests import (
    WatchTaskCreateRequest,
    watch_task_create_request,
)

logger = logging.getLogger(__name__)


class WatchService:
    """
    Watch application service

    Orchestrates watch configuration and message filtering.
    """

    def __init__(
        self,
        watch_repository: WatchRepository,
        *,
        cache_provider: Optional[ConfigCacheProvider] = None,
    ) -> None:
        """
        Initialize service

        Args:
            watch_repository: Watch repository implementation
            cache_provider: Lazy provider for the config cache port, injected by
                the composition root (`composition/container.py`)
        """
        self._repository = watch_repository
        self._filter_service = FilterService()
        self._cache: Optional[ConfigCache] = None  # Resolved on first use
        self._cache_provider = cache_provider

    def _get_cache(self) -> ConfigCache:
        """Resolve the injected config cache port (degrades to NullCache)."""
        if self._cache is None:
            self._cache = resolve_cache(self._cache_provider, label="Config")
        return self._cache

    def get_user_config(self, user_id: str) -> Optional[WatchConfig]:
        """
        Get user's watch configuration

        Args:
            user_id: User identifier

        Returns:
            Watch configuration or None
        """
        # Try cache first
        cached_config = self._get_cache().get_watch_config(int(user_id) if user_id.isdigit() else hash(user_id))
        if cached_config is not None:
            logger.debug(f"Cache hit: watch config for user={user_id}")
            return WatchConfig.from_dict(user_id, cached_config) if isinstance(cached_config, dict) else cached_config

        config = self._repository.get_user_config(user_id)

        # Cache the result (TTL: 10 minutes)
        if config:
            self._get_cache().cache_watch_config(
                int(user_id) if user_id.isdigit() else hash(user_id),
                config.to_dict(),
                ttl=600.0
            )
            logger.debug(f"Cache set: watch config for user={user_id}")

        return config

    def get_all_configs(self) -> List[WatchConfig]:
        """
        Get all watch configurations

        Returns:
            List of all configurations
        """
        return self._repository.get_all_configs()

    def add_watch_task(
        self,
        request: WatchTaskCreateRequest | str | None = None,
        *legacy_args,
        **legacy_kwargs,
    ) -> WatchTask:
        """Add or update a watch task."""
        request = watch_task_create_request(request, legacy_args, legacy_kwargs)
        task = WatchTask(
            source=request.source_id,
            dest=request.dest_id,
            whitelist=request.whitelist or [],
            blacklist=request.blacklist or [],
            whitelist_regex=request.whitelist_regex or [],
            blacklist_regex=request.blacklist_regex or [],
            forward_mode=request.forward_mode,
            record_mode=request.record_mode,
        )

        watch_key = self._make_watch_key(request.source_id, request.dest_id, request.record_mode)
        self._repository.add_task(request.user_id, watch_key, task)
        logger.info(f"Watch task added: user={request.user_id}, key={watch_key}")

        return task

    @staticmethod
    def _make_watch_key(source_id: str, dest_id: Optional[str], record_mode: bool) -> str:
        """Create canonical watch key: source|dest or source|record (record mode)."""
        if record_mode:
            return f"{source_id}|record"
        if dest_id is not None:
            return f"{source_id}|{dest_id}"
        return source_id

    def remove_watch_task(self, user_id: str, watch_key: str) -> bool:
        """
        Remove a watch task

        Args:
            user_id: User identifier
            watch_key: Watch task key (e.g. source|dest or source|record)

        Returns:
            True if removed

        Raises:
            NotFoundError: If task not found
        """
        if not self._repository.remove_task(user_id, watch_key):
            raise NotFoundError(
                f"Watch task not found",
                resource_type="WatchTask",
                resource_id=f"{user_id}:{watch_key}"
            )

        logger.info(f"Watch task removed: user={user_id}, key={watch_key}")
        return True

    def get_monitored_sources(self) -> Set[str]:
        """
        Get all monitored source chat IDs

        Returns:
            Set of source chat IDs
        """
        # Try cache first
        cached_sources = self._get_cache().get_monitored_sources()
        if cached_sources is not None:
            logger.debug("Cache hit: monitored sources")
            return set(s['id'] if isinstance(s, dict) else s for s in cached_sources)

        sources = self._repository.get_monitored_sources()

        # Cache the result (TTL: 5 minutes)
        self._get_cache().cache_monitored_sources(
            [{'id': s} for s in sources],
            ttl=300.0
        )
        logger.debug("Cache set: monitored sources")

        return sources

    def should_forward_message(
        self,
        user_id: str,
        source_id: str,
        message_text: Optional[str]
    ) -> bool:
        """
        Check if message should be forwarded

        Args:
            user_id: User identifier
            source_id: Source chat ID
            message_text: Message text

        Returns:
            True if message should be forwarded
        """
        config = self._repository.get_user_config(user_id)
        if not config:
            return False

        source_id_str = str(source_id)
        for task in config.tasks.values():
            if str(task.source) != source_id_str:
                continue
            if task.record_mode:
                continue
            if self._filter_service.should_forward(task, message_text):
                return True

        return False

    def get_tasks_for_source(self, source_id: str) -> List[tuple]:
        """
        Get all tasks monitoring a specific source

        Args:
            source_id: Source chat ID

        Returns:
            List of (user_id, watch_key, task) tuples
        """
        return self._repository.get_tasks_for_source(source_id)

    def reload_config(self) -> None:
        """Reload configuration from storage"""
        if hasattr(self._repository, 'reload'):
            self._repository.reload()
            logger.info("Watch configuration reloaded")

    def get_all_configs_dict(self) -> dict:
        """
        Get all watch configurations as dictionary

        Returns raw dictionary format for backward compatibility.
        Keys are watch keys (e.g. "source|dest" or "source|record").

        Returns:
            Dictionary of all configurations
        """
        configs = self._repository.get_all_configs()
        result = {}
        for config in configs:
            result[config.user_id] = config.to_dict()
        return result

    def save_config_dict(self, config_dict: dict) -> None:
        """
        Save watch configurations from dictionary

        Accepts raw dictionary format for backward compatibility.
        Keys are watch keys (e.g. "source|dest" or "source|record").

        Args:
            config_dict: Dictionary of configurations
        """
        if hasattr(self._repository, "save_config_dict"):
            self._repository.save_config_dict(config_dict)
        else:
            for user_id, user_data in config_dict.items():
                config = WatchConfig.from_dict(str(user_id), user_data)
                self._repository.save_user_config(config)

        # Invalidate cache after saving
        self._get_cache().invalidate_watch_config()
        logger.info(f"Watch config saved: {len(config_dict)} users")

    def invalidate_cache(self, user_id: Optional[str] = None) -> int:
        """
        Invalidate cache for a user or all users

        Args:
            user_id: User ID to invalidate, or None for all

        Returns:
            Number of cache entries invalidated
        """
        if user_id is not None:
            return self._get_cache().invalidate_watch_config(
                int(user_id) if user_id.isdigit() else hash(user_id)
            )
        else:
            return self._get_cache().invalidate_watch_config()
