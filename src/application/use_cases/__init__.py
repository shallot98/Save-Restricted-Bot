"""
Use Cases
=========

Application use case implementations.
Each use case represents a single user action.
"""

from src.application.use_cases.save_note import SaveNoteUseCase
from src.application.use_cases.forward_message import ForwardMessageUseCase

__all__ = ["SaveNoteUseCase", "ForwardMessageUseCase"]
