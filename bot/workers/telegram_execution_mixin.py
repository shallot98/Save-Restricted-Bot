"""Telegram execution helpers for MessageWorker."""

import asyncio
import logging

from pyrogram.errors import FloodWait

from bot.workers.errors import RetryLater, UnrecoverableError
from constants import MAX_FLOOD_RETRIES, OPERATION_TIMEOUT

logger = logging.getLogger(__name__)


class TelegramExecutionMixin:
    """Provide timeout and FloodWait handling for Telegram operations."""

    def _run_async_with_timeout(self, coro, timeout: float = OPERATION_TIMEOUT):
        """Execute async operation with timeout in the worker thread."""
        if not asyncio.iscoroutine(coro) and not hasattr(coro, "__await__"):
            error_msg = f"Expected coroutine or awaitable, got {type(coro).__name__}"
            logger.error(f"❌ {error_msg}")
            raise TypeError(error_msg)

        if not self.loop or self.loop.is_closed():
            error_msg = "Event loop not available or closed"
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)

        try:
            return self.loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
        except asyncio.TimeoutError:
            logger.error(f"❌ 操作超时（{timeout}秒）")
            raise

    @staticmethod
    def _coerce_chat_id(chat_id: str):
        """将 chat_id 规范为 Pyrogram 可接受的类型（int 或字符串）。"""
        if chat_id == "me":
            return "me"
        try:
            return int(chat_id)
        except Exception:
            return chat_id

    def _execute_with_flood_retry(
        self,
        operation_name: str,
        operation_func,
        *,
        max_flood_retries: int = MAX_FLOOD_RETRIES,
        timeout: float = OPERATION_TIMEOUT,
    ):
        """Execute operation with FloodWait retry and timeout handling."""
        for flood_attempt in range(max_flood_retries):
            try:
                return self._execute_operation_once(operation_func, timeout)
            except FloodWait as e:
                self._handle_flood_wait(
                    operation_name,
                    e,
                    flood_attempt,
                    max_flood_retries=max_flood_retries,
                )
            except asyncio.TimeoutError:
                logger.error(f"❌ {operation_name}: 操作超时（{timeout}秒），跳过此消息")
                raise UnrecoverableError(f"Timeout ({timeout}s) for {operation_name}")
            except TypeError as e:
                self._handle_type_error(operation_name, e)
            except (ValueError, KeyError) as e:
                self._handle_peer_lookup_error(operation_name, e)
            except Exception as e:
                logger.error(f"❌ {operation_name} 执行失败: {type(e).__name__}: {e}")
                raise

        raise UnrecoverableError(
            f"Operation {operation_name} failed after {max_flood_retries} FloodWait retries"
        )

    def _execute_operation_once(self, operation_func, timeout: float):
        result = operation_func()
        if asyncio.iscoroutine(result):
            return self._run_async_with_timeout(result, timeout=timeout)
        return result

    @staticmethod
    def _handle_flood_wait(
        operation_name: str,
        error: FloodWait,
        flood_attempt: int,
        *,
        max_flood_retries: int,
    ) -> None:
        wait_time = error.value
        if flood_attempt < max_flood_retries - 1:
            logger.warning(f"⏳ {operation_name}: 遇到限流 FLOOD_WAIT, 需等待 {wait_time} 秒")
            logger.info(
                f"   将在 {wait_time + 1} 秒后重试 "
                f"(FloodWait 重试 {flood_attempt + 1}/{max_flood_retries})"
            )
            raise RetryLater(wait_time + 1, reason=f"{operation_name}: FLOOD_WAIT")

        logger.error(f"❌ {operation_name}: FloodWait 重试次数已达上限，放弃操作")
        raise UnrecoverableError(f"FloodWait retry limit exceeded for {operation_name}")

    @staticmethod
    def _handle_type_error(operation_name: str, error: TypeError) -> None:
        error_msg = str(error)
        if "coroutine" in error_msg.lower() or "awaitable" in error_msg.lower():
            logger.error(f"❌ {operation_name}: 异步执行错误: {error_msg}")
            raise UnrecoverableError(f"Async execution error for {operation_name}: {error_msg}")

        logger.error(f"❌ {operation_name} 执行失败: {type(error).__name__}: {error}")
        raise error

    @staticmethod
    def _handle_peer_lookup_error(operation_name: str, error: ValueError | KeyError) -> None:
        error_msg = str(error)
        if "Peer id invalid" in error_msg or "ID not found" in error_msg:
            logger.warning(f"⚠️ {operation_name}: Peer ID 无效，跳过: {error_msg}")
            raise UnrecoverableError(f"Invalid Peer ID: {error_msg}")

        logger.error(f"❌ {operation_name} 执行失败: {type(error).__name__}: {error}")
        raise error
