"""Helpers for extracting magnet metadata from note dictionaries."""

from typing import Dict, List, Optional

from src.domain.magnet.parsing import extract_all_magnets, extract_dn_parameter, extract_info_hash


def extract_all_dns_from_note(note: Dict) -> List[Dict]:
    """Extract all magnet DN values from a note payload."""
    message_text = note.get("message_text") or ""
    magnet_link = (note.get("magnet_link") or "").strip()
    filename = note.get("filename")

    magnets: List[str] = extract_all_magnets(message_text)
    if magnet_link:
        magnets.append(magnet_link)

    primary_info_hash = extract_info_hash(magnet_link) if magnet_link else None
    return _extract_unique_dns(magnets, filename, primary_info_hash)


def _extract_unique_dns(
    magnets: List[str],
    filename: Optional[str],
    primary_info_hash: Optional[str],
) -> List[Dict]:
    results: List[Dict] = []
    seen_hashes: set[str] = set()
    seen_magnets: set[str] = set()

    for magnet in magnets:
        info = _normalize_magnet(magnet, seen_hashes, seen_magnets)
        if info is None:
            continue

        normalized_magnet, info_hash = info
        dn = _resolve_dn(
            normalized_magnet,
            info_hash,
            filename,
            primary_info_hash=primary_info_hash,
            results=results,
        )
        if info_hash or dn:
            results.append({"magnet": normalized_magnet, "info_hash": info_hash, "dn": dn})

    return results


def _normalize_magnet(
    magnet: str,
    seen_hashes: set[str],
    seen_magnets: set[str],
) -> Optional[tuple[str, Optional[str]]]:
    normalized_magnet = (magnet or "").strip()
    if not normalized_magnet:
        return None

    info_hash = extract_info_hash(normalized_magnet)
    if info_hash:
        if info_hash in seen_hashes:
            return None
        seen_hashes.add(info_hash)
        return normalized_magnet, info_hash

    lowered = normalized_magnet.lower()
    if lowered in seen_magnets:
        return None
    seen_magnets.add(lowered)
    return normalized_magnet, None


def _resolve_dn(
    magnet: str,
    info_hash: Optional[str],
    filename: Optional[str],
    *,
    primary_info_hash: Optional[str],
    results: List[Dict],
) -> Optional[str]:
    if filename and info_hash and primary_info_hash and info_hash == primary_info_hash:
        return filename
    if filename and not primary_info_hash and not results:
        return filename
    return extract_dn_parameter(magnet)
