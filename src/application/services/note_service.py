"""
Note Application Service
========================

Orchestrates note-related operations.
"""

import logging
from typing import Optional, List, Set

from src.domain.entities.note import Note, NoteCreate, NoteFilter
from src.domain.repositories.note_repository import NoteRepository
from src.application.dto import NoteDTO, PaginatedResult
from src.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class NoteService:
    """
    Note application service

    Orchestrates note operations between presentation
    and domain layers.
    """

    def __init__(self, note_repository: NoteRepository) -> None:
        """
        Initialize service

        Args:
            note_repository: Note repository implementation
        """
        self._repository = note_repository
        self._cache = None  # Lazy initialization to avoid circular imports
        self._storage_manager = None  # Lazy init: avoid WebDAV I/O at import/startup

    def _get_cache(self):
        """Get cache manager with lazy initialization"""
        if self._cache is None:
            from src.infrastructure.cache.managers import get_note_cache_manager
            self._cache = get_note_cache_manager()
        return self._cache

    def _get_storage_manager(self):
        """Get storage manager (local/WebDAV) with lazy initialization."""
        if self._storage_manager is None:
            from src.core.config import settings
            from bot.storage.webdav_client import StorageManager, WebDAVClient

            media_dir = str(settings.paths.media_dir)
            webdav_config = settings.webdav_config

            webdav_client = None
            if webdav_config.get("enabled", False):
                url = (webdav_config.get("url") or "").strip()
                username = (webdav_config.get("username") or "").strip()
                password = (webdav_config.get("password") or "").strip()
                base_path = webdav_config.get("base_path") or "/telegram_media"

                if url and username and password:
                    try:
                        webdav_client = WebDAVClient(url, username, password, base_path)
                    except Exception as e:
                        logger.warning(f"WebDAV storage init failed, fallback to local: {e}")

            self._storage_manager = StorageManager(media_dir, webdav_client)

        return self._storage_manager

    @staticmethod
    def _collect_media_locations(note: Note) -> Set[str]:
        media_locations: Set[str] = set()
        if note.media_path:
            media_locations.add(note.media_path)
        if note.media_paths:
            media_locations.update(p for p in note.media_paths if p)
        return media_locations

    def _delete_note_media_best_effort(self, note: Note) -> None:
        media_locations = self._collect_media_locations(note)
        if not media_locations:
            return

        try:
            storage_manager = self._get_storage_manager()
        except Exception as e:
            logger.warning(f"Storage manager unavailable, skip media cleanup: {e}")
            return

        for location in media_locations:
            try:
                if not storage_manager.delete_file(location):
                    logger.warning(f"Failed to delete media: note={note.id}, path={location}")
            except Exception as e:
                logger.warning(f"Failed to delete media: note={note.id}, path={location}, err={e}")

    def get_note(self, note_id: int) -> NoteDTO:
        """
        Get note by ID

        Args:
            note_id: Note identifier

        Returns:
            Note DTO

        Raises:
            NotFoundError: If note not found
        """
        note = self._repository.get_by_id(note_id)
        if not note:
            raise NotFoundError(
                f"Note not found: {note_id}",
                resource_type="Note",
                resource_id=note_id
            )
        return NoteDTO.from_entity(note)

    def get_notes(
        self,
        user_id: Optional[int] = None,
        source_chat_id: Optional[str] = None,
        search_query: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        favorite_only: bool = False,
        page: int = 1,
        page_size: int = 50
    ) -> PaginatedResult:
        """
        Get paginated notes

        Args:
            user_id: User identifier
            source_chat_id: Filter by source
            search_query: Search text
            date_from: Start date filter
            date_to: End date filter
            favorite_only: Only favorites
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Paginated result with notes
        """
        cache = self._get_cache()

        search_normalized = (search_query or "").strip()
        should_cache = (
            not search_normalized
            and not date_from
            and not date_to
            and 1 <= page <= 10
        )

        cache_key = None
        if should_cache:
            user_part = str(user_id) if user_id is not None else "all"
            source_part = source_chat_id or "all"
            favorite_part = "fav" if favorite_only else "all"
            cache_key = f"list:{user_part}:v2:{source_part}:{favorite_part}:{page}:{page_size}"

            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: notes list page={page}")
                return cached_result

        filter_criteria = NoteFilter(
            user_id=user_id,
            source_chat_id=source_chat_id,
            search_query=search_normalized or None,
            date_from=date_from,
            date_to=date_to,
            favorite_only=favorite_only,
            limit=page_size,
            offset=(page - 1) * page_size
        )

        notes, total = self._repository.search(filter_criteria)
        note_dtos = [NoteDTO.from_entity(note) for note in notes]

        result = PaginatedResult(
            items=note_dtos,
            total=total,
            page=page,
            page_size=page_size
        )

        # Cache the result (TTL: 5 minutes)
        if cache_key:
            cache.set(cache_key, result, ttl=300.0)
            logger.debug(f"Cache set: notes list page={page}")

        return result

    def create_note(self, note_data: NoteCreate) -> NoteDTO:
        """
        Create a new note

        Args:
            note_data: Note creation data

        Returns:
            Created note DTO

        Raises:
            ValidationError: If duplicate detected
        """
        # Check for duplicates
        if self._repository.check_duplicate(
            user_id=note_data.user_id,
            source_chat_id=note_data.source_chat_id,
            message_text=note_data.message_text,
            media_group_id=note_data.media_group_id
        ):
            raise ValidationError("Duplicate note detected")

        note = self._repository.create(note_data)
        logger.info(f"Note created: id={note.id}, user={note.user_id}")

        # Invalidate related caches
        self._invalidate_note_caches(note.user_id)

        return NoteDTO.from_entity(note)

    def delete_note(self, note_id: int) -> bool:
        """
        Delete a note

        Args:
            note_id: Note identifier

        Returns:
            True if deleted

        Raises:
            NotFoundError: If note not found
        """
        note = self._repository.get_by_id(note_id)
        if not note:
            raise NotFoundError(
                f"Note not found: {note_id}",
                resource_type="Note",
                resource_id=note_id,
            )

        if not self._repository.delete(note_id):
            raise NotFoundError(
                f"Note not found: {note_id}",
                resource_type="Note",
                resource_id=note_id,
            )

        self._invalidate_note_caches(note.user_id)
        self._delete_note_media_best_effort(note)

        logger.info(f"Note deleted: id={note_id}")
        return True

    def toggle_favorite(self, note_id: int) -> bool:
        """
        Toggle note favorite status

        Args:
            note_id: Note identifier

        Returns:
            New favorite status
        """
        note = self._repository.get_by_id(note_id)
        if not note:
            raise NotFoundError(
                f"Note not found: {note_id}",
                resource_type="Note",
                resource_id=note_id
            )

        result = self._repository.toggle_favorite(note_id)

        self._invalidate_note_caches(note.user_id)

        return result

    def update_magnet(
        self,
        note_id: int,
        magnet_link: str,
        filename: Optional[str] = None
    ) -> bool:
        """
        Update note's magnet link

        Args:
            note_id: Note identifier
            magnet_link: New magnet link
            filename: Extracted filename

        Returns:
            True if updated
        """
        if not magnet_link or not magnet_link.strip():
            raise ValidationError("Magnet link cannot be empty")

        if not self._repository.update_magnet(note_id, magnet_link, filename):
            raise NotFoundError(
                f"Note not found: {note_id}",
                resource_type="Note",
                resource_id=note_id,
            )

        self._invalidate_note_caches()
        logger.info(f"Note magnet updated: id={note_id}")
        return True

    def get_sources(self, user_id: int) -> List[dict]:
        """
        Get unique sources for a user

        Args:
            user_id: User identifier

        Returns:
            List of source info dicts
        """
        # Try cache first
        cached_sources = self._get_cache().get_sources(user_id)
        if cached_sources is not None:
            logger.debug(f"Cache hit: sources for user={user_id}")
            return cached_sources

        sources = self._repository.get_sources(user_id)
        result = [
            {
                "source_chat_id": source_id,
                "source_name": source_name,
                "count": count
            }
            for source_id, source_name, count in sources
        ]

        # Cache the result (TTL: 10 minutes)
        self._get_cache().cache_sources(user_id, result, ttl=600.0)
        logger.debug(f"Cache set: sources for user={user_id}")

        return result

    def update_text(self, note_id: int, message_text: str) -> bool:
        """
        Update note's message text

        Args:
            note_id: Note identifier
            message_text: New message text

        Returns:
            True if updated

        Raises:
            NotFoundError: If note not found
            ValidationError: If message_text is empty
        """
        if not message_text or not message_text.strip():
            raise ValidationError("Message text cannot be empty")

        if not self._repository.update_text(note_id, message_text):
            raise NotFoundError(
                f"Note not found: {note_id}",
                resource_type="Note",
                resource_id=note_id
            )

        self._invalidate_note_caches()

        logger.info(f"Note text updated: id={note_id}")
        return True

    def _invalidate_note_caches(self, user_id: Optional[int] = None) -> None:
        """
        Invalidate note-related caches after write operations

        Args:
            user_id: User ID to invalidate, or None for all
        """
        cache = self._get_cache()

        deleted = cache.invalidate_all()
        logger.debug(f"Cache invalidated for notes (user={user_id or 'all'}), deleted={deleted}")

    def get_all_sources(self) -> List[dict]:
        """
        Get all unique sources across all users

        Returns:
            List of source info dicts with source_chat_id, source_name, count
        """
        # Use user_id=0 as a special key for "all sources"
        cached_sources = self._get_cache().get_sources(0)
        if cached_sources is not None:
            logger.debug("Cache hit: all sources")
            return cached_sources

        sources = self._repository.get_all_sources()
        result = [
            {
                "source_chat_id": source_id,
                "source_name": source_name,
                "count": count
            }
            for source_id, source_name, count in sources
        ]

        # Cache the result (TTL: 10 minutes)
        self._get_cache().cache_sources(0, result, ttl=600.0)
        logger.debug("Cache set: all sources")

        return result

    def invalidate_cache(self, user_id: Optional[int] = None) -> int:
        """
        Invalidate cache for a user or all users

        Args:
            user_id: User ID to invalidate, or None for all

        Returns:
            Number of cache entries invalidated
        """
        if user_id is not None:
            return self._get_cache().invalidate_user_notes(user_id)
        else:
            return self._get_cache().invalidate_all()
