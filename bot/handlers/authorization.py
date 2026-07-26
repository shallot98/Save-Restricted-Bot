"""Owner-only access control for bot-side Telegram handlers.

Handlers registered on the ``bot`` client are reachable by anyone who knows the
bot's @username, yet they drive ``acc`` -- the owner's personal Telegram
account. Every such handler must therefore sit behind :func:`build_owner_filter`.

Resolution order for the owner allow-list:

1. the ``OWNER_ID`` setting (accepts several ids separated by ``,``/``;``/space);
2. the identity of the configured user session, since the account whose
   ``STRING`` session the bot drives is by definition the owner;
3. nothing -- in which case the filter denies every update.

Step 3 is deliberate: an unresolvable owner means an unprotected bot, so the
failure direction is "reject" rather than "allow".
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from pyrogram import filters

logger = logging.getLogger(__name__)

_ID_SEPARATOR = re.compile(r"[,;\s]+")

# Denied senders are logged once each so a hostile peer cannot flood the log.
_denied_senders: set[Optional[int]] = set()


def parse_owner_ids(raw: Any) -> frozenset[int]:
    """Parse an ``OWNER_ID`` setting value into Telegram user ids.

    Non-numeric fragments are reported and skipped rather than aborting the
    whole allow-list, so one typo cannot silently disable every other owner.
    """
    if raw is None:
        return frozenset()

    owner_ids: set[int] = set()
    for token in _ID_SEPARATOR.split(str(raw).strip()):
        if not token:
            continue
        try:
            owner_ids.add(int(token))
        except ValueError:
            logger.error("OWNER_ID 含无法解析的片段，已忽略: %r", token)
    return frozenset(owner_ids)


def _owner_ids_from_settings() -> frozenset[int]:
    try:
        from src.core.config import settings
    except Exception:
        logger.exception("读取 OWNER_ID 配置失败")
        return frozenset()
    return parse_owner_ids(settings.get("OWNER_ID", ""))


def _owner_id_from_session(acc: Any) -> frozenset[int]:
    """Derive the owner id from the configured user session."""
    if acc is None:
        return frozenset()
    try:
        me = acc.get_me()
    except Exception:
        logger.exception("无法从 User 会话推导 OWNER_ID")
        return frozenset()

    owner_id = getattr(me, "id", None)
    if owner_id is None:
        return frozenset()
    return frozenset({int(owner_id)})


def resolve_owner_ids(acc: Any = None) -> frozenset[int]:
    """Resolve the owner allow-list, falling back to the user session."""
    owner_ids = _owner_ids_from_settings()
    if owner_ids:
        logger.info("✅ 已从 OWNER_ID 配置解析出 %d 个所有者", len(owner_ids))
        return owner_ids

    owner_ids = _owner_id_from_session(acc)
    if owner_ids:
        logger.warning(
            "⚠️ OWNER_ID 未配置，已回退为 User 会话身份 %s。"
            "建议显式设置 OWNER_ID，否则更换会话后鉴权范围会随之改变。",
            next(iter(owner_ids)),
        )
        return owner_ids

    logger.error(
        "🚨 OWNER_ID 未配置且无法从 User 会话推导，Bot 将拒绝所有消息与回调。"
        "请设置 OWNER_ID 环境变量为你的 Telegram 用户 ID 后重启。"
    )
    return frozenset()


def build_owner_filter(owner_ids: frozenset[int]):
    """Build a Pyrogram filter accepting only updates sent by an owner.

    An empty ``owner_ids`` rejects everything, which is the intended behaviour
    when the owner cannot be determined.
    """

    def _is_owner(_, __, update) -> bool:
        sender = getattr(update, "from_user", None)
        sender_id = getattr(sender, "id", None)
        if sender_id is not None and sender_id in owner_ids:
            return True
        _log_denied(sender_id)
        return False

    return filters.create(_is_owner, name="OwnerFilter")


def _log_denied(sender_id: Optional[int]) -> None:
    if sender_id in _denied_senders:
        return
    _denied_senders.add(sender_id)
    logger.warning("🚫 已拒绝非所有者的请求，发送者 id=%s（同一发送者仅记录一次）", sender_id)
