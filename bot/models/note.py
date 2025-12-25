"""
Note data models

NOTE: This file now delegates to the new layered architecture.
      For new code, prefer using:
          from src.domain.entities import Note, NoteCreate, NoteFilter
"""

# Re-export from new architecture for backward compatibility
from src.domain.entities.note import Note, NoteCreate, NoteFilter

__all__ = ["Note", "NoteCreate", "NoteFilter"]
