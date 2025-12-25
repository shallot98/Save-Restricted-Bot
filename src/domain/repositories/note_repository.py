"""
Note Repository Interface
=========================

Abstract interface for note persistence operations.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple

from src.domain.entities.note import Note, NoteCreate, NoteFilter


class NoteRepository(ABC):
    """
    Note repository interface

    Defines the contract for note persistence operations.
    Implementations can use SQLite, PostgreSQL, or other storage.
    """

    @abstractmethod
    def get_by_id(self, note_id: int) -> Optional[Note]:
        """
        Get note by ID

        Args:
            note_id: Note identifier

        Returns:
            Note if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_user(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Note]:
        """
        Get notes for a user

        Args:
            user_id: User identifier
            limit: Maximum number of notes
            offset: Pagination offset

        Returns:
            List of notes
        """
        pass

    @abstractmethod
    def search(self, filter_criteria: NoteFilter) -> Tuple[List[Note], int]:
        """
        Search notes with filter criteria

        Args:
            filter_criteria: Filter parameters

        Returns:
            Tuple of (notes list, total count)
        """
        pass

    @abstractmethod
    def create(self, note_data: NoteCreate) -> Note:
        """
        Create a new note

        Args:
            note_data: Note creation data

        Returns:
            Created note with generated ID
        """
        pass

    @abstractmethod
    def update(self, note: Note) -> Note:
        """
        Update existing note

        Args:
            note: Note with updated values

        Returns:
            Updated note
        """
        pass

    @abstractmethod
    def delete(self, note_id: int) -> bool:
        """
        Delete note by ID

        Args:
            note_id: Note identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def update_magnet(
        self,
        note_id: int,
        magnet_link: str,
        filename: Optional[str] = None
    ) -> bool:
        """
        Update note's magnet link and filename

        Args:
            note_id: Note identifier
            magnet_link: New magnet link
            filename: Extracted filename

        Returns:
            True if updated
        """
        pass

    @abstractmethod
    def toggle_favorite(self, note_id: int) -> bool:
        """
        Toggle note's favorite status

        Args:
            note_id: Note identifier

        Returns:
            New favorite status
        """
        pass

    @abstractmethod
    def get_sources(self, user_id: int) -> List[Tuple[str, str, int]]:
        """
        Get unique sources for a user

        Args:
            user_id: User identifier

        Returns:
            List of (source_id, source_name, count) tuples
        """
        pass

    @abstractmethod
    def check_duplicate(
        self,
        user_id: int,
        source_chat_id: str,
        message_text: Optional[str],
        media_group_id: Optional[str] = None
    ) -> bool:
        """
        Check if note is a duplicate

        Args:
            user_id: User identifier
            source_chat_id: Source chat ID
            message_text: Message text
            media_group_id: Media group ID

        Returns:
            True if duplicate exists
        """
        pass

    @abstractmethod
    def update_text(self, note_id: int, message_text: str) -> bool:
        """
        Update note's message text

        Args:
            note_id: Note identifier
            message_text: New message text

        Returns:
            True if updated
        """
        pass

    @abstractmethod
    def get_all_sources(self) -> List[Tuple[str, Optional[str], int]]:
        """
        Get all unique sources across all users

        Returns:
            List of (source_id, source_name, count) tuples
        """
        pass
