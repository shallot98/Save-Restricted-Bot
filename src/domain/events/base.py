"""
Base Domain Event
=================

Base class for all domain events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict
import uuid


@dataclass
class DomainEvent:
    """
    Base class for domain events

    Domain events represent something that happened
    in the domain that domain experts care about.

    Attributes:
        event_id: Unique event identifier
        occurred_at: When the event occurred
        metadata: Additional event metadata
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """Get event type name"""
        return self.__class__.__name__
