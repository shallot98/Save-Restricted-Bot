"""Shared worker exceptions."""


class UnrecoverableError(Exception):
    """Exception for unrecoverable errors that should not be retried."""


class RetryLater(Exception):
    """Exception indicating the message should be retried after a delay."""

    def __init__(self, delay_seconds: float, reason: str = "") -> None:
        super().__init__(reason or f"retry later: {delay_seconds}s")
        self.delay_seconds = delay_seconds
        self.reason = reason
