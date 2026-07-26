"""Magnet link parsing helpers."""

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import parse_qs, quote, unquote_plus, urlparse

logger = logging.getLogger(__name__)

MAGNET_START_PATTERN = re.compile(r"magnet:\?xt=urn:btih:\s*[a-zA-Z0-9]+", re.IGNORECASE)
INFO_HASH_PATTERN = r"xt=urn:btih:\s*([a-zA-Z0-9]+)"
DN_PARAMETER_PATTERN = r"[&?]dn=([^\n\r&]+)"
FILENAME_EXTENSION_PATTERN = re.compile(r"\.[A-Za-z0-9]{1,8}(?=(&|\s|$))")


def extract_all_magnets(text: str) -> List[str]:
    if not text:
        return []

    starts = list(MAGNET_START_PATTERN.finditer(text))
    if not starts:
        return []

    magnets: List[str] = []
    for idx, start_match in enumerate(starts):
        end_limit = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
        segment = _line_segment(text[start_match.start():end_limit])
        magnet = extract_single_magnet_from_segment(segment)
        if magnet:
            magnets.append(magnet.rstrip())

    return magnets


def _line_segment(segment: str) -> str:
    newline_pos = len(segment)
    for ch in ("\n", "\r"):
        pos = segment.find(ch)
        if pos != -1:
            newline_pos = min(newline_pos, pos)
    return segment[:newline_pos]


def extract_single_magnet_from_segment(segment: str) -> Optional[str]:
    if not segment or not segment.lower().startswith("magnet:"):
        return None

    default_end = _first_whitespace_pos(segment)
    dn_match = re.search(r"[&?]dn=", segment, re.IGNORECASE)
    if not dn_match:
        return _extract_magnet_without_dn(segment, default_end)

    dn_value_start = dn_match.end()
    dn_value_end = _find_dn_value_end(segment, dn_value_start)
    return segment[:_find_magnet_end(segment, dn_value_end)]


def _first_whitespace_pos(segment: str) -> int:
    whitespace_match = re.search(r"\s", segment)
    return whitespace_match.start() if whitespace_match else len(segment)


def _extract_magnet_without_dn(segment: str, default_end: int) -> str:
    base_match = re.match(
        r"magnet:\?xt=urn:btih:\s*([a-zA-Z0-9]{40})",
        segment,
        re.IGNORECASE,
    )
    if base_match:
        return f"magnet:?xt=urn:btih:{base_match.group(1)}"
    return segment[:default_end]


def _find_dn_value_end(segment: str, dn_value_start: int) -> int:
    next_amp_pos = segment.find("&", dn_value_start)
    if next_amp_pos != -1:
        return next_amp_pos

    ext_match = FILENAME_EXTENSION_PATTERN.search(segment, dn_value_start)
    if ext_match:
        return ext_match.end()

    return _find_line_end(segment, dn_value_start)


def _find_line_end(segment: str, start: int) -> int:
    for i in range(start, len(segment)):
        if segment[i] in "\n\r":
            return i
    return len(segment)


def _find_magnet_end(segment: str, dn_value_end: int) -> int:
    end_pos = dn_value_end
    if dn_value_end < len(segment) and segment[dn_value_end] == "&":
        while end_pos < len(segment) and not segment[end_pos].isspace():
            end_pos += 1
    return end_pos


def extract_info_hash(magnet: str) -> Optional[str]:
    if not magnet:
        return None

    match = re.search(INFO_HASH_PATTERN, magnet, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def extract_dn_parameter(magnet: str) -> Optional[str]:
    if not magnet:
        return None

    match = re.search(DN_PARAMETER_PATTERN, magnet)
    if match:
        return _clean_dn(unquote_plus(match.group(1)))

    return _extract_dn_with_urlparse(magnet)


def _extract_dn_with_urlparse(magnet: str) -> Optional[str]:
    try:
        parsed = urlparse(magnet)
        params = parse_qs(parsed.query)
        dn_values = params.get("dn", [])
        if dn_values:
            return _clean_dn(unquote_plus(dn_values[0]))
    except Exception as e:
        logger.debug(f"解析dn参数失败: {e}")
    return None


def _clean_dn(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).strip()


def build_magnet_link(
    info_hash: str,
    filename: Optional[str] = None,
    trackers: Optional[List[str]] = None,
) -> str:
    magnet = f"magnet:?xt=urn:btih:{info_hash.upper()}"

    if filename:
        magnet += f"&dn={quote(filename)}"

    if trackers:
        for tracker in trackers:
            magnet += f"&tr={quote(tracker)}"

    return magnet


def clean_filename(filename: str) -> str:
    if not filename:
        return ""

    cleaned = re.sub(r"<[^>]+>", "", filename)
    cleaned = re.split(r"[\s\r\n]*magnet:", cleaned, flags=re.IGNORECASE)[0]
    cleaned = re.sub(r"[\r\n]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def extract_magnet_from_text(message_text: str) -> Optional[str]:
    if not message_text:
        return None

    magnets = extract_all_magnets(message_text)
    if not magnets:
        return None

    magnet_link = magnets[0].rstrip()
    info_hash = extract_info_hash(magnet_link)
    if not info_hash:
        return None

    dn_decoded = extract_dn_parameter(magnet_link)
    if dn_decoded:
        return build_magnet_link(info_hash, dn_decoded)
    return build_magnet_link(info_hash)


def extract_all_magnet_info(
    message_text: str,
    filename: Optional[str] = None,
) -> List[Dict]:
    result = []
    all_magnets = extract_all_magnets(message_text)

    for idx, magnet in enumerate(all_magnets):
        info_hash = extract_info_hash(magnet)
        dn = filename if idx == 0 and filename else extract_dn_parameter(magnet)
        if info_hash or dn:
            result.append({"magnet": magnet, "info_hash": info_hash, "dn": dn})

    return result
