"""
Chain forward mixin for MessageWorker.

Extracts chain-forwarding and loop-protection logic out of message_worker.py
to keep the worker focused on queue scheduling and message execution flow.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from bot.workers.chain_forward_models import (
    ChainProcessContext,
    ChainTaskEntry,
    normalize_chain_task_entry,
)
from bot.workers.processing_models import ForwardModeContext, RecordModeContext
from src.core.container import get_watch_service
from src.domain.entities.watch import WatchTask
from src.domain.services.filter_service import FilterService

logger = logging.getLogger(__name__)


class ChainForwardMixin:
    """Provide chain-forwarding helpers for MessageWorker."""

    def _build_chain_context(self, message, chain_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """构建链式转发上下文（深度 + 已访问节点集合）。"""
        if chain_context is None:
            depth = 0
            max_hops = self._chain_max_hops
            visited: set[str] = set()
        else:
            depth = int(chain_context.get("depth", 0))
            max_hops = int(chain_context.get("max_hops", self._chain_max_hops))
            visited_raw = chain_context.get("visited", set())
            if isinstance(visited_raw, set):
                visited = set(visited_raw)
            elif isinstance(visited_raw, (list, tuple)):
                visited = {str(item) for item in visited_raw}
            else:
                visited = set()

        source_chat = getattr(getattr(message, "chat", None), "id", None)
        if source_chat is not None:
            visited.add(str(source_chat))

        return {
            "depth": max(depth, 0),
            "max_hops": max(1, min(max_hops, 20)),
            "visited": visited,
        }

    def _should_stop_chain(self, dest_chat_id, chain_context: Dict[str, Any]) -> bool:
        """判断链式转发是否应停止（超过深度或出现环路）。"""
        if dest_chat_id in (None, "me"):
            return False

        dest_str = str(dest_chat_id)
        depth = int(chain_context.get("depth", 0))
        max_hops = int(chain_context.get("max_hops", self._chain_max_hops))
        visited = chain_context.get("visited", set())

        if depth >= max_hops:
            logger.warning(
                f"⛔ 链式转发达到最大跳数，停止传播: depth={depth}, max_hops={max_hops}, dest={dest_str}"
            )
            return True

        if dest_str in visited:
            logger.warning(f"⛔ 检测到链式转发环路，停止传播: dest={dest_str}, visited={sorted(visited)}")
            return True

        return False

    def _get_forwarded_message(self, dest_chat_id: str, forwarded_message_id: int):
        """获取转发后的消息对象。"""
        try:
            dest_id = int(dest_chat_id)
            forwarded_message = self._execute_with_flood_retry(
                "获取转发后的消息",
                lambda: self.acc.get_messages(dest_id, forwarded_message_id),
            )
            if forwarded_message:
                logger.debug(
                    f"   成功获取转发后的消息对象: chat_id={forwarded_message.chat.id}, "
                    f"message_id={forwarded_message.id}"
                )
            return forwarded_message
        except Exception as e:
            if type(e).__name__ == "UnrecoverableError":
                logger.warning(f"   ⚠️ 获取转发后的消息对象失败（不可恢复）: {e}")
            else:
                logger.error(f"   ❌ 获取转发后的消息对象失败: {e}")
            return None

    def _apply_chain_filters(self, message_text: str, watch_data: dict) -> bool:
        """应用链式转发的过滤规则。"""
        task = WatchTask(
            source=str(watch_data.get("source") or ""),
            dest=watch_data.get("dest"),
            whitelist=watch_data.get("whitelist", []),
            blacklist=watch_data.get("blacklist", []),
            whitelist_regex=watch_data.get("whitelist_regex", []),
            blacklist_regex=watch_data.get("blacklist_regex", []),
            preserve_forward_source=bool(watch_data.get("preserve_forward_source", False)),
            forward_mode=watch_data.get("forward_mode", "full"),
            extract_patterns=watch_data.get("extract_patterns", []),
            record_mode=bool(watch_data.get("record_mode", False)),
        )

        if not FilterService.should_forward(task, message_text):
            logger.debug("   ⏭️ 目标频道配置：未通过过滤")
            return False

        return True

    def _ensure_peer_cached(self, dest: str) -> bool:
        """确保目标 Peer 已缓存。"""
        from bot.services.peer_cache import cache_peer_if_needed
        from bot.utils.peer import is_dest_cached

        if is_dest_cached(dest):
            logger.debug(f"      下一级目标Peer已缓存: {dest}")
            return True

        logger.debug(f"      尝试缓存下一级目标Peer: {dest}")
        if cache_peer_if_needed(self.acc, int(dest), "下一级目标"):
            return True

        logger.warning(f"   ⚠️ 下一级目标Peer缓存失败: {dest}")
        logger.warning("      💡 提示：如果目标是私聊用户，请确保该用户已与账号建立过对话")
        logger.warning("      💡 可以让该用户向账号发送一条消息，然后重启Bot")
        return False

    def _process_chain_config(
        self,
        context: ChainProcessContext,
    ) -> None:
        """处理单个链式转发配置。"""
        check_record_mode = context.watch_data.get("record_mode", False)
        check_dest = context.watch_data.get("dest")
        check_forward_mode = context.watch_data.get("forward_mode", "full")
        check_extract_patterns = context.watch_data.get("extract_patterns", [])

        if check_record_mode:
            logger.info("   📝 目标频道配置：记录模式")
            try:
                self._handle_record_mode(
                    RecordModeContext(
                        message=context.forwarded_message,
                        user_id=context.user_id,
                        source_chat_id=context.dest_chat_id,
                        message_text=context.message_text,
                        forward_mode=check_forward_mode,
                        extract_patterns=check_extract_patterns,
                    )
                )
            except Exception as e:
                logger.error(f"   ❌ 目标频道记录失败: {e}", exc_info=True)

        if check_dest and check_dest != "me":
            logger.info(f"   📤 目标频道配置：转发到 {check_dest}")
            logger.debug(f"      转发模式: {check_forward_mode}")

            if not self._ensure_peer_cached(str(check_dest)):
                return

            try:
                check_preserve_source = context.watch_data.get("preserve_forward_source", False)
                self._handle_forward_mode(
                    ForwardModeContext(
                        message=context.forwarded_message,
                        dest_chat_id=check_dest,
                        message_text=context.message_text,
                        forward_mode=check_forward_mode,
                        extract_patterns=check_extract_patterns,
                        preserve_forward_source=check_preserve_source,
                        record_mode=False,
                        chain_context=context.chain_context,
                    )
                )
            except Exception as e:
                logger.error(f"   ❌ 目标频道转发失败: {e}", exc_info=True)

    def _trigger_dest_monitoring(
        self,
        dest_chat_id,
        forwarded_message_id,
        message_text,
        *,
        chain_context: Optional[Dict[str, Any]] = None,
    ):
        """手动触发目标频道的监控配置处理。"""
        watch_service = get_watch_service()
        dest_chat_id_str = str(dest_chat_id)
        if dest_chat_id_str not in watch_service.get_monitored_sources():
            return

        self._log_chain_trigger(dest_chat_id, forwarded_message_id, chain_context)
        forwarded_message = self._get_forwarded_message(dest_chat_id_str, forwarded_message_id)
        if not forwarded_message:
            logger.warning("   ⚠️ 无法获取转发后的消息对象，跳过链式转发")
            return

        matched_configs = 0
        for task_entry in self._iter_chain_task_entries(watch_service, dest_chat_id_str):
            matched_configs += 1
            if self._should_skip_self_forward(task_entry, dest_chat_id_str):
                logger.debug("   ⏭️ 跳过转发到自己的配置，避免循环")
                continue

            self._log_chain_task_match(matched_configs, task_entry)
            if not self._apply_chain_filters(message_text, task_entry.watch_data):
                continue

            logger.info("   🎯 目标频道配置：通过过滤规则")
            self._process_chain_config(
                ChainProcessContext(
                    forwarded_message=forwarded_message,
                    user_id=task_entry.user_id,
                    dest_chat_id=dest_chat_id_str,
                    message_text=message_text,
                    watch_data=task_entry.watch_data,
                    chain_context=chain_context,
                )
            )

        self._log_chain_summary(dest_chat_id, matched_configs)

    def _log_chain_trigger(self, dest_chat_id, forwarded_message_id, chain_context) -> None:
        depth = int((chain_context or {}).get("depth", 0))
        max_hops = int((chain_context or {}).get("max_hops", self._chain_max_hops))
        logger.info(
            f"🔄 目标频道 {dest_chat_id} 也是监控源，手动触发其配置处理... (depth={depth}/{max_hops})"
        )
        logger.debug(f"   转发后的消息ID: {forwarded_message_id}")

    def _iter_chain_task_entries(self, watch_service, dest_chat_id: str):
        for raw_entry in watch_service.get_tasks_for_source(dest_chat_id):
            task_entry = normalize_chain_task_entry(raw_entry)
            if task_entry is not None:
                yield task_entry

    @staticmethod
    def _should_skip_self_forward(task_entry: ChainTaskEntry, dest_chat_id: str) -> bool:
        check_dest = task_entry.watch_data.get("dest")
        check_record_mode = task_entry.watch_data.get("record_mode", False)
        return not check_record_mode and check_dest is not None and str(check_dest) == dest_chat_id

    @staticmethod
    def _log_chain_task_match(matched_configs: int, task_entry: ChainTaskEntry) -> None:
        check_dest = task_entry.watch_data.get("dest")
        check_record_mode = task_entry.watch_data.get("record_mode", False)
        logger.info(
            f"   ✅ 找到目标频道的配置 #{matched_configs}: user={task_entry.user_id}, "
            f"key={task_entry.watch_key}, mode={'记录' if check_record_mode else '转发到 ' + str(check_dest)}"
        )

    @staticmethod
    def _log_chain_summary(dest_chat_id, matched_configs: int) -> None:
        if matched_configs == 0:
            logger.debug(f"   ℹ️ 目标频道 {dest_chat_id} 没有匹配的配置")
        else:
            logger.info(f"   📊 链式转发完成: 共处理 {matched_configs} 个配置")
