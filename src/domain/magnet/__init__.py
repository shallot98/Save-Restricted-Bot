"""
Magnet Domain Module
====================

Pure domain logic for parsing magnet links and extracting magnet metadata
from note payloads. Standard library only - no Telegram/Flask dependencies.

Moved from ``bot/utils/magnet_*.py`` to remove the ``src.* -> bot.*``
reverse dependency (see ARCHITECTURE_REFACTOR_REPORT_2026-07-26 P1-1).
"""

from src.domain.magnet.note import extract_all_dns_from_note
from src.domain.magnet.parser import (
    MagnetLinkParser,
    extract_all_magnets_from_text,
    extract_dn_from_magnet,
)

__all__ = [
    "MagnetLinkParser",
    "extract_all_magnets_from_text",
    "extract_dn_from_magnet",
    "extract_all_dns_from_note",
]
