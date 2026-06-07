"""Parameter objects for message worker processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ForwardModeContext:
    message: Any
    dest_chat_id: Any
    message_text: str
    forward_mode: str
    extract_patterns: list[str]
    preserve_forward_source: bool
    record_mode: bool
    chain_context: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ForwardSendContext:
    message: Any
    dest_chat_id: Any
    message_text: str
    forward_mode: str
    extract_patterns: list[str]
    preserve_forward_source: bool


@dataclass(frozen=True)
class ForwardChainContext:
    record_mode: bool
    dest_chat_id: Any
    forwarded_message_id: Any
    message_text: str
    current_chain: Dict[str, Any]


@dataclass(frozen=True)
class RecordModeContext:
    message: Any
    user_id: str
    source_chat_id: str
    message_text: str
    forward_mode: str
    extract_patterns: list[str]


@dataclass(frozen=True)
class RecordSaveContext:
    user_id: str
    source_chat_id: str
    source_name: str
    content_to_save: str
    media_type: Any
    media_path: Any
    media_paths: list[str]
    media_group_id: Any
