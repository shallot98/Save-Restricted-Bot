"""
Save Note Use Case
==================

Use case for saving a note from a message.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List

from src.domain.entities.note import NoteCreate
from src.domain.repositories.note_repository import NoteRepository
from src.domain.value_objects.magnet import MagnetLink
from src.application.dto import NoteDTO

logger = logging.getLogger(__name__)


@dataclass
class SaveNoteInput:
    """Input data for save note use case"""

    user_id: int
    source_chat_id: str
    source_name: Optional[str]
    message_text: Optional[str]
    media_type: Optional[str] = None
    media_path: Optional[str] = None
    media_paths: Optional[List[str]] = None
    media_group_id: Optional[str] = None


@dataclass
class SaveNoteOutput:
    """Output data for save note use case"""

    note_id: int
    is_duplicate: bool
    has_magnet: bool
    note: Optional[NoteDTO] = None


class SaveNoteUseCase:
    """
    Save note use case

    Handles the complete flow of saving a note:
    1. Check for duplicates
    2. Extract magnet links
    3. Create note record
    4. Schedule calibration if needed
    """

    def __init__(self, note_repository: NoteRepository) -> None:
        """
        Initialize use case

        Args:
            note_repository: Note repository implementation
        """
        self._repository = note_repository

    def execute(self, input_data: SaveNoteInput) -> SaveNoteOutput:
        """
        Execute the use case

        Args:
            input_data: Input data

        Returns:
            Use case output
        """
        # Check for duplicates
        if self._repository.check_duplicate(
            user_id=input_data.user_id,
            source_chat_id=input_data.source_chat_id,
            message_text=input_data.message_text,
            media_group_id=input_data.media_group_id
        ):
            logger.debug(f"Duplicate note detected for user {input_data.user_id}")
            return SaveNoteOutput(
                note_id=0,
                is_duplicate=True,
                has_magnet=False
            )

        # Extract magnet link if present
        magnet = None
        if input_data.message_text:
            magnet = MagnetLink.parse(input_data.message_text)

        # Create note
        note_create = NoteCreate(
            user_id=input_data.user_id,
            source_chat_id=input_data.source_chat_id,
            source_name=input_data.source_name,
            message_text=input_data.message_text,
            media_type=input_data.media_type,
            media_path=input_data.media_path,
            media_paths=input_data.media_paths,
            media_group_id=input_data.media_group_id,
        )

        note = self._repository.create(note_create)
        logger.info(f"Note saved: id={note.id}, user={note.user_id}")

        return SaveNoteOutput(
            note_id=note.id,
            is_duplicate=False,
            has_magnet=magnet is not None,
            note=NoteDTO.from_entity(note)
        )
