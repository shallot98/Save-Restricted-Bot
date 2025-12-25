"""
Watch Entity
============

Domain entities for watch/monitoring configuration.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class WatchTask:
    """
    Single watch task configuration

    Represents a monitoring task that watches a source
    chat and optionally forwards messages to a destination.

    Attributes:
        source: Source chat ID to monitor
        dest: Destination chat ID for forwarding
        whitelist: Keywords that must be present
        blacklist: Keywords that must not be present
        whitelist_regex: Regex patterns that must match
        blacklist_regex: Regex patterns that must not match
        preserve_forward_source: Keep original forward source
        forward_mode: "full" or "extract"
        extract_patterns: Patterns for content extraction
        record_mode: Only record, don't forward
    """

    source: str
    dest: Optional[str]
    whitelist: List[str] = field(default_factory=list)
    blacklist: List[str] = field(default_factory=list)
    whitelist_regex: List[str] = field(default_factory=list)
    blacklist_regex: List[str] = field(default_factory=list)
    preserve_forward_source: bool = False
    forward_mode: str = "full"
    extract_patterns: List[str] = field(default_factory=list)
    record_mode: bool = False
    watch_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "WatchTask":
        """Create WatchTask from dictionary"""
        return cls(
            source=data["source"],
            dest=data.get("dest"),
            whitelist=data.get("whitelist", []),
            blacklist=data.get("blacklist", []),
            whitelist_regex=data.get("whitelist_regex", []),
            blacklist_regex=data.get("blacklist_regex", []),
            preserve_forward_source=data.get("preserve_forward_source", False),
            forward_mode=data.get("forward_mode", "full"),
            extract_patterns=data.get("extract_patterns", []),
            record_mode=data.get("record_mode", False),
            watch_id=(str(data.get("watch_id")).strip() if data.get("watch_id") is not None else None) or None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        payload = {
            "source": self.source,
            "dest": self.dest,
            "whitelist": self.whitelist,
            "blacklist": self.blacklist,
            "whitelist_regex": self.whitelist_regex,
            "blacklist_regex": self.blacklist_regex,
            "preserve_forward_source": self.preserve_forward_source,
            "forward_mode": self.forward_mode,
            "extract_patterns": self.extract_patterns,
            "record_mode": self.record_mode,
        }
        if isinstance(self.watch_id, str) and self.watch_id.strip():
            payload["watch_id"] = self.watch_id.strip()
        return payload

    @property
    def has_filters(self) -> bool:
        """Check if task has any filters configured"""
        return bool(
            self.whitelist
            or self.blacklist
            or self.whitelist_regex
            or self.blacklist_regex
        )


@dataclass
class WatchConfig:
    """
    User's watch configuration containing multiple tasks

    Aggregates all watch tasks for a single user.
    """

    user_id: str
    tasks: Dict[str, WatchTask] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, user_id: str, data: dict) -> "WatchConfig":
        """Create WatchConfig from dictionary"""
        tasks = {
            key: WatchTask.from_dict(value)
            for key, value in data.items()
        }
        return cls(user_id=user_id, tasks=tasks)

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert to dictionary for storage"""
        return {
            key: task.to_dict()
            for key, task in self.tasks.items()
        }

    def add_task(self, key: str, task: WatchTask) -> None:
        """Add a watch task"""
        self.tasks[key] = task

    def remove_task(self, key: str) -> bool:
        """Remove a watch task"""
        if key in self.tasks:
            del self.tasks[key]
            return True
        return False

    def get_task(self, key: str) -> Optional[WatchTask]:
        """Get a watch task by key"""
        return self.tasks.get(key)

    @property
    def task_count(self) -> int:
        """Get number of tasks"""
        return len(self.tasks)
