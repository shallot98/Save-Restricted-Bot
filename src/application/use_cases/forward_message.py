"""
Forward Message Use Case
========================

Use case for determining if and how to forward a message.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List

from src.domain.entities.watch import WatchTask
from src.domain.services.filter_service import FilterService

logger = logging.getLogger(__name__)


@dataclass
class ForwardMessageInput:
    """Input data for forward message use case"""

    task: WatchTask
    message_text: Optional[str]


@dataclass
class ForwardMessageOutput:
    """Output data for forward message use case"""

    should_forward: bool
    forward_mode: str
    extracted_content: Optional[str] = None
    destination: Optional[str] = None
    record_only: bool = False


class ForwardMessageUseCase:
    """
    Forward message use case

    Determines if a message should be forwarded based on
    watch task configuration and filter rules.
    """

    def __init__(self) -> None:
        """Initialize use case"""
        self._filter_service = FilterService()

    def execute(self, input_data: ForwardMessageInput) -> ForwardMessageOutput:
        """
        Execute the use case

        Args:
            input_data: Input data

        Returns:
            Use case output
        """
        task = input_data.task
        message_text = input_data.message_text

        # Check if message passes filters
        should_forward = self._filter_service.should_forward(task, message_text)

        if not should_forward:
            return ForwardMessageOutput(
                should_forward=False,
                forward_mode=task.forward_mode
            )

        # Extract content if in extract mode
        extracted_content = None
        if task.forward_mode == "extract" and message_text:
            extracted_content = self._filter_service.extract_content(
                task, message_text
            )

        return ForwardMessageOutput(
            should_forward=True,
            forward_mode=task.forward_mode,
            extracted_content=extracted_content,
            destination=task.dest,
            record_only=task.record_mode
        )
