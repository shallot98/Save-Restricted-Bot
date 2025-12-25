"""
Base Worker
===========

Abstract base class for background workers.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkerStatus(str, Enum):
    """Worker status enumeration"""

    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class Worker(ABC):
    """
    Abstract base class for background workers

    Provides common functionality for background task processing.
    """

    def __init__(self, name: str) -> None:
        """
        Initialize worker

        Args:
            name: Worker name for logging
        """
        self._name = name
        self._status = WorkerStatus.IDLE
        self._task: Optional[asyncio.Task] = None
        self._started_at: Optional[datetime] = None
        self._processed_count = 0
        self._error_count = 0

    @property
    def name(self) -> str:
        """Get worker name"""
        return self._name

    @property
    def status(self) -> WorkerStatus:
        """Get worker status"""
        return self._status

    @property
    def is_running(self) -> bool:
        """Check if worker is running"""
        return self._status == WorkerStatus.RUNNING

    @property
    def stats(self) -> dict:
        """Get worker statistics"""
        return {
            "name": self._name,
            "status": self._status.value,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "processed_count": self._processed_count,
            "error_count": self._error_count,
        }

    async def start(self) -> None:
        """Start the worker"""
        if self._status == WorkerStatus.RUNNING:
            logger.warning(f"Worker {self._name} is already running")
            return

        self._status = WorkerStatus.RUNNING
        self._started_at = datetime.now()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Worker {self._name} started")

    async def stop(self) -> None:
        """Stop the worker"""
        if self._status != WorkerStatus.RUNNING:
            return

        self._status = WorkerStatus.STOPPING
        logger.info(f"Worker {self._name} stopping...")

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._status = WorkerStatus.STOPPED
        logger.info(f"Worker {self._name} stopped")

    async def _run_loop(self) -> None:
        """Main worker loop"""
        try:
            while self._status == WorkerStatus.RUNNING:
                try:
                    await self.process()
                    self._processed_count += 1
                except Exception as e:
                    self._error_count += 1
                    logger.error(f"Worker {self._name} error: {e}")
                    await self.on_error(e)

                await asyncio.sleep(self.interval)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._status = WorkerStatus.ERROR
            logger.error(f"Worker {self._name} fatal error: {e}")

    @property
    @abstractmethod
    def interval(self) -> float:
        """Processing interval in seconds"""
        pass

    @abstractmethod
    async def process(self) -> None:
        """Process one iteration"""
        pass

    async def on_error(self, error: Exception) -> None:
        """
        Handle processing error

        Override to implement custom error handling.

        Args:
            error: The exception that occurred
        """
        pass
