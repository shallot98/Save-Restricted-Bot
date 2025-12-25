"""
Watch Repository Interface
==========================

Abstract interface for watch configuration persistence.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Set

from src.domain.entities.watch import WatchTask, WatchConfig


class WatchRepository(ABC):
    """
    Watch configuration repository interface

    Defines the contract for watch configuration persistence.
    """

    @abstractmethod
    def get_user_config(self, user_id: str) -> Optional[WatchConfig]:
        """
        Get watch configuration for a user

        Args:
            user_id: User identifier

        Returns:
            WatchConfig if found, None otherwise
        """
        pass

    @abstractmethod
    def get_all_configs(self) -> List[WatchConfig]:
        """
        Get all watch configurations

        Returns:
            List of all user configurations
        """
        pass

    @abstractmethod
    def save_user_config(self, config: WatchConfig) -> None:
        """
        Save user's watch configuration

        Args:
            config: Configuration to save
        """
        pass

    @abstractmethod
    def delete_user_config(self, user_id: str) -> bool:
        """
        Delete user's watch configuration

        Args:
            user_id: User identifier

        Returns:
            True if deleted
        """
        pass

    @abstractmethod
    def get_task(self, user_id: str, watch_key: str) -> Optional[WatchTask]:
        """
        Get specific watch task

        Args:
            user_id: User identifier
            watch_key: Watch task key (e.g. source|dest or source|record)

        Returns:
            WatchTask if found
        """
        pass

    @abstractmethod
    def add_task(self, user_id: str, watch_key: str, task: WatchTask) -> None:
        """
        Add or update a watch task

        Args:
            user_id: User identifier
            watch_key: Watch task key (e.g. source|dest or source|record)
            task: Task configuration
        """
        pass

    @abstractmethod
    def remove_task(self, user_id: str, watch_key: str) -> bool:
        """
        Remove a watch task

        Args:
            user_id: User identifier
            watch_key: Watch task key (e.g. source|dest or source|record)

        Returns:
            True if removed
        """
        pass

    @abstractmethod
    def get_monitored_sources(self) -> Set[str]:
        """
        Get all monitored source chat IDs

        Returns:
            Set of source chat IDs
        """
        pass

    @abstractmethod
    def get_tasks_for_source(self, source_id: str) -> List[tuple]:
        """
        Get all tasks monitoring a specific source

        Args:
            source_id: Source chat ID

        Returns:
            List of (user_id, watch_key, task) tuples
        """
        pass
