"""
Magnet Link Value Object
========================

Immutable value object representing a magnet link.
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse, quote


@dataclass(frozen=True)
class MagnetLink:
    """
    Immutable magnet link value object

    Parses and validates magnet links, providing
    access to individual components.

    Attributes:
        raw: Original magnet link string
        info_hash: BitTorrent info hash
        display_name: Display name (dn parameter)
        trackers: List of tracker URLs
    """

    raw: str
    info_hash: str
    display_name: Optional[str] = None
    trackers: tuple = ()

    @classmethod
    def parse(cls, magnet_uri: str) -> Optional["MagnetLink"]:
        """
        Parse magnet URI string

        Args:
            magnet_uri: Magnet URI to parse

        Returns:
            MagnetLink if valid, None otherwise
        """
        if not magnet_uri or not magnet_uri.startswith("magnet:"):
            return None

        try:
            # Extract query string
            query_start = magnet_uri.find("?")
            if query_start == -1:
                return None

            query_string = magnet_uri[query_start + 1:]
            params = parse_qs(query_string)

            # Extract info hash from xt parameter
            xt_values = params.get("xt", [])
            info_hash = None
            for xt in xt_values:
                if xt.startswith("urn:btih:"):
                    info_hash = xt[9:].lower()
                    break

            if not info_hash:
                return None

            # Extract display name
            dn_values = params.get("dn", [])
            display_name = dn_values[0] if dn_values else None

            # Extract trackers
            trackers = tuple(params.get("tr", []))

            return cls(
                raw=magnet_uri,
                info_hash=info_hash,
                display_name=display_name,
                trackers=trackers,
            )
        except Exception:
            return None

    @classmethod
    def from_hash(
        cls,
        info_hash: str,
        display_name: Optional[str] = None,
        trackers: Optional[list] = None
    ) -> "MagnetLink":
        """
        Create magnet link from info hash

        Args:
            info_hash: BitTorrent info hash
            display_name: Optional display name
            trackers: Optional tracker list

        Returns:
            MagnetLink instance
        """
        parts = [f"magnet:?xt=urn:btih:{info_hash}"]

        if display_name:
            parts.append(f"&dn={quote(display_name)}")

        if trackers:
            for tracker in trackers:
                parts.append(f"&tr={quote(tracker)}")

        raw = "".join(parts)
        return cls(
            raw=raw,
            info_hash=info_hash.lower(),
            display_name=display_name,
            trackers=tuple(trackers or []),
        )

    def with_display_name(self, display_name: str) -> "MagnetLink":
        """
        Create new magnet link with updated display name

        Args:
            display_name: New display name

        Returns:
            New MagnetLink with updated name
        """
        return MagnetLink.from_hash(
            info_hash=self.info_hash,
            display_name=display_name,
            trackers=list(self.trackers),
        )

    @property
    def has_display_name(self) -> bool:
        """Check if magnet has display name"""
        return bool(self.display_name)

    def __str__(self) -> str:
        return self.raw

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MagnetLink):
            return False
        return self.info_hash == other.info_hash
