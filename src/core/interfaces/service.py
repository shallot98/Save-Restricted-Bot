"""
Service Interface
=================

Base interface for application services.
"""

from abc import ABC, abstractmethod
from typing import Optional


class Service(ABC):
    """
    Base service interface

    Services encapsulate business logic and orchestrate
    domain operations.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize service resources

        Called once during application startup.
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Cleanup service resources

        Called during application shutdown.
        """
        pass

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if service is initialized"""
        pass


class HealthCheckable(ABC):
    """
    Interface for services that support health checks
    """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform health check

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    def get_health_status(self) -> dict:
        """
        Get detailed health status

        Returns:
            Dictionary with health details
        """
        pass
