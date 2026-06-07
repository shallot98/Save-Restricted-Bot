"""Magnet link utility facade."""

from typing import Dict, List, Optional

from bot.utils import magnet_parsing
from bot.utils.magnet_note import extract_all_dns_from_note


class MagnetLinkParser:
    """Magnet link parser compatibility facade."""

    MAGNET_START_PATTERN = magnet_parsing.MAGNET_START_PATTERN
    INFO_HASH_PATTERN = magnet_parsing.INFO_HASH_PATTERN
    DN_PARAMETER_PATTERN = magnet_parsing.DN_PARAMETER_PATTERN
    _FILENAME_EXTENSION_PATTERN = magnet_parsing.FILENAME_EXTENSION_PATTERN

    @staticmethod
    def extract_all_magnets(text: str) -> List[str]:
        return magnet_parsing.extract_all_magnets(text)

    @staticmethod
    def _extract_single_magnet_from_segment(segment: str) -> Optional[str]:
        return magnet_parsing.extract_single_magnet_from_segment(segment)

    @staticmethod
    def extract_info_hash(magnet: str) -> Optional[str]:
        return magnet_parsing.extract_info_hash(magnet)

    @staticmethod
    def extract_dn_parameter(magnet: str) -> Optional[str]:
        return magnet_parsing.extract_dn_parameter(magnet)

    @staticmethod
    def build_magnet_link(
        info_hash: str,
        filename: Optional[str] = None,
        trackers: Optional[List[str]] = None,
    ) -> str:
        return magnet_parsing.build_magnet_link(info_hash, filename, trackers)

    @staticmethod
    def clean_filename(filename: str) -> str:
        return magnet_parsing.clean_filename(filename)

    @staticmethod
    def extract_magnet_from_text(message_text: str) -> Optional[str]:
        return magnet_parsing.extract_magnet_from_text(message_text)

    @staticmethod
    def extract_all_magnet_info(
        message_text: str,
        filename: Optional[str] = None,
    ) -> List[Dict]:
        return magnet_parsing.extract_all_magnet_info(message_text, filename)


def extract_all_magnets_from_text(text: str) -> List[str]:
    """Extract all magnet links from text."""
    return MagnetLinkParser.extract_all_magnets(text)


def extract_dn_from_magnet(
    magnet_link: str,
    message_text: Optional[str] = None,
    filename: Optional[str] = None,
) -> Optional[str]:
    """Extract dn parameter with backward-compatible priority."""
    if filename:
        return filename
    return MagnetLinkParser.extract_dn_parameter(magnet_link)


__all__ = [
    "MagnetLinkParser",
    "extract_all_magnets_from_text",
    "extract_dn_from_magnet",
    "extract_all_dns_from_note",
]
