"""Note filtering helpers for automatic calibration."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from bot.utils.magnet_utils import MagnetLinkParser, extract_all_dns_from_note

logger = logging.getLogger(__name__)


class CalibrationNoteFilterMixin:
    def should_calibrate_note(self, note: Dict) -> bool:
        if not self.is_enabled():
            return False
        if not self._note_has_magnet(note):
            return False

        filter_mode = self.config.get("filter_mode", "empty_only")
        if filter_mode == "empty_only":
            return self._should_calibrate_empty_note(note)
        if filter_mode == "all":
            return True
        return False

    def _note_has_magnet(self, note: Dict) -> bool:
        magnet_link = note.get("magnet_link")
        message_text = note.get("message_text", "")
        all_magnets = self.extract_all_magnets_from_text(message_text)
        return bool(magnet_link or all_magnets)

    def _should_calibrate_empty_note(self, note: Dict) -> bool:
        magnet_link = note.get("magnet_link")
        if magnet_link and self._magnet_has_dn_parameter(magnet_link, note.get("id")):
            return False

        filename = note.get("filename")
        if not filename or filename.strip() == "":
            return True
        return False

    @staticmethod
    def _magnet_has_dn_parameter(magnet_link: str, note_id: int | None) -> bool:
        try:
            parsed = urlparse(magnet_link)
            params = parse_qs(parsed.query)
        except Exception as exc:
            logger.debug(f"解析dn参数失败: {exc}")
            return False
        if not params.get("dn", []):
            return False
        logger.debug(f"笔记 {note_id} 的磁力链接已有dn参数，跳过校准")
        return True

    def extract_magnet_hash(self, magnet_link: str) -> Optional[str]:
        return MagnetLinkParser.extract_info_hash(magnet_link)

    def extract_all_magnets_from_text(self, message_text: str) -> List[str]:
        return MagnetLinkParser.extract_all_magnets(message_text)

    def extract_all_dns_from_note(self, note: Dict) -> List[Dict]:
        all_info = extract_all_dns_from_note(note)
        return [
            {"magnet": info.get("magnet"), "info_hash": info.get("info_hash")}
            for info in all_info
        ]
