"""
Repository Interface
====================

Base interface for repository pattern implementation.
Follows Interface Segregation Principle (ISP).
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Any

T = TypeVar('T')
ID = TypeVar('ID')


class Repository(ABC, Generic[T, ID]):
    """
    Generic repository interface

    Type Parameters:
        T: Entity type
        ID: Entity identifier type
    """

    @abstractmethod
    def get_by_id(self, entity_id: ID) -> Optional[T]:
        """
        Retrieve entity by ID

        Args:
            entity_id: Entity identifier

        Returns:
            Entity if found, None otherwise
        """
        pass

    @abstractmethod
    def get_all(self) -> List[T]:
        """
        Retrieve all entities

        Returns:
            List of all entities
        """
        pass

    @abstractmethod
    def add(self, entity: T) -> T:
        """
        Add new entity

        Args:
            entity: Entity to add

        Returns:
            Added entity with generated ID
        """
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """
        Update existing entity

        Args:
            entity: Entity with updated values

        Returns:
            Updated entity
        """
        pass

    @abstractmethod
    def delete(self, entity_id: ID) -> bool:
        """
        Delete entity by ID

        Args:
            entity_id: Entity identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def exists(self, entity_id: ID) -> bool:
        """
        Check if entity exists

        Args:
            entity_id: Entity identifier

        Returns:
            True if exists, False otherwise
        """
        pass


class QueryableRepository(Repository[T, ID], Generic[T, ID]):
    """
    Extended repository with query capabilities
    """

    @abstractmethod
    def find_by(self, **criteria: Any) -> List[T]:
        """
        Find entities matching criteria

        Args:
            **criteria: Field-value pairs to match

        Returns:
            List of matching entities
        """
        pass

    @abstractmethod
    def count(self, **criteria: Any) -> int:
        """
        Count entities matching criteria

        Args:
            **criteria: Field-value pairs to match

        Returns:
            Count of matching entities
        """
        pass
