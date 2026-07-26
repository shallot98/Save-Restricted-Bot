#!/usr/bin/env python3
"""将磁力备份频道中的消息补录为网页笔记（记录模式同等逻辑）。

默认处理备份频道 message_id 2733-2738（此前补传到备份、尚未入库的 6 条）。
运行前请先停止 bot 容器，避免 session 冲突。
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from pyrogram import Client

from composition.wiring import configure_runtime_implementations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("backfill_notes")

BACKUP_CHAT = -1003202156769
SOURCE_NAME = "磁力备份"
USER_ID = "907446443"
CHINA_TZ = ZoneInfo("Asia/Shanghai")


def _parse_ids(raw: str) -> List[int]:
    ids: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start, end = int(a), int(b)
            if end < start:
                start, end = end, start
            ids.extend(range(start, end + 1))
        else:
            ids.append(int(part))
    seen = set()
    out: List[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _init_storage():
    from src.core.config import settings
    from bot.storage.webdav_client import StorageManager, WebDAVClient

    MEDIA_DIR = str(settings.paths.media_dir)
    os.makedirs(MEDIA_DIR, exist_ok=True)
    webdav_config = settings.webdav_config or {}
    if not webdav_config.get("enabled", False):
        logger.info("使用本地存储")
        return StorageManager(MEDIA_DIR), MEDIA_DIR

    url = (webdav_config.get("url") or "").strip()
    username = (webdav_config.get("username") or "").strip()
    password = (webdav_config.get("password") or "").strip()
    base_path = webdav_config.get("base_path", "/telegram_media")
    if not (url and username and password):
        logger.warning("WebDAV 配置不完整，使用本地存储")
        return StorageManager(MEDIA_DIR), MEDIA_DIR

    client = WebDAVClient(url, username, password, base_path)
    if not client.test_connection():
        logger.warning("WebDAV 连接失败，使用本地存储")
        return StorageManager(MEDIA_DIR), MEDIA_DIR

    logger.info("WebDAV 存储已启用")
    return StorageManager(MEDIA_DIR, client), MEDIA_DIR


async def _warm_peers(app: Client, chat_ids: List[int]) -> None:
    wanted = set(chat_ids)
    found = set()
    async for d in app.get_dialogs(limit=80):
        if d.chat and d.chat.id in wanted:
            found.add(d.chat.id)
            logger.info("resolved %s (%s)", d.chat.id, d.chat.title or d.chat.first_name)
        if found >= wanted:
            break
    for cid in wanted - found:
        try:
            chat = await app.get_chat(cid)
            logger.info("get_chat ok %s (%s)", cid, getattr(chat, "title", None))
        except Exception as e:
            logger.warning("cannot resolve %s: %s: %s", cid, type(e).__name__, e)


async def _download_media(
    app: Client,
    msg,
    media_dir: str,
    storage_manager,
    keep_local: bool,
) -> Tuple[Optional[str], Optional[str], List[str]]:
    """返回 (media_type, media_path, media_paths)。"""
    ts = datetime.now(CHINA_TZ).strftime("%Y%m%d_%H%M%S")

    if msg.photo:
        file_name = f"{msg.id}_{ts}.jpg"
        file_path = os.path.join(media_dir, file_name)
        await app.download_media(msg.photo.file_id, file_name=file_path)
        ok, location = storage_manager.save_file(file_path, file_name, keep_local=keep_local)
        if ok:
            return "photo", location, [location]
        return "photo", file_name, [file_name]

    if msg.video:
        media_obj = msg.video
        kind = "video"
    elif msg.animation:
        media_obj = msg.animation
        kind = "animation"
    else:
        return None, None, []

    if not (media_obj.thumbs and len(media_obj.thumbs) > 0):
        logger.warning("msg %s %s 无缩略图", msg.id, kind)
        return kind, None, []

    thumb = media_obj.thumbs[-1]
    file_name = f"{msg.id}_{ts}_thumb.jpg"
    file_path = os.path.join(media_dir, file_name)
    await app.download_media(thumb.file_id, file_name=file_path)
    ok, location = storage_manager.save_file(file_path, file_name, keep_local=keep_local)
    if ok:
        return kind, location, [location]
    return kind, f"local:{file_name}", [f"local:{file_name}"]


def _save_note(
    *,
    user_id: str,
    source_chat_id: str,
    source_name: str,
    text: str,
    media_type: Optional[str],
    media_path: Optional[str],
    media_paths: List[str],
    media_group_id: Optional[str],
) -> int:
    from composition.container import get_message_worker_service

    svc = get_message_worker_service()
    return svc.save_recorded_note(
        user_id=user_id,
        source_chat_id=source_chat_id,
        source_name=source_name,
        content_to_save=text,
        media_type=media_type,
        media_path=media_path,
        media_paths=media_paths,
        media_group_id=media_group_id,
    )


async def backfill(message_ids: List[int], *, dry_run: bool) -> int:
    from src.core.config import settings

    mc = settings.main_config
    keep_local = bool((settings.webdav_config or {}).get("keep_local_copy", False))
    storage_manager, media_dir = _init_storage()

    app = Client(
        "backfill_notes",
        api_id=int(mc["ID"]),
        api_hash=mc["HASH"],
        session_string=mc["STRING"],
        in_memory=True,
    )

    ok = skipped = failed = 0
    created: List[Tuple[int, int]] = []

    async with app:
        me = await app.get_me()
        logger.info("login as %s (%s)", me.id, me.first_name)
        await _warm_peers(app, [BACKUP_CHAT])

        for mid in message_ids:
            logger.info("=" * 60)
            logger.info("processing backup message_id=%s", mid)
            try:
                msg = await app.get_messages(BACKUP_CHAT, mid)
            except Exception as e:
                logger.error("get_messages failed: %s: %s", type(e).__name__, e)
                failed += 1
                continue

            if not msg or getattr(msg, "empty", False):
                logger.warning("empty/missing, skip")
                skipped += 1
                continue

            text = msg.text or msg.caption or ""
            logger.info(
                "media=%s text_len=%s has_magnet=%s",
                msg.media,
                len(text),
                "magnet:" in text.lower(),
            )
            if text:
                logger.info("preview=%r", text[:120])

            if dry_run:
                logger.info("DRY-RUN would save note for msg %s", mid)
                ok += 1
                continue

            try:
                media_type, media_path, media_paths = await _download_media(
                    app, msg, media_dir, storage_manager, keep_local
                )
                logger.info(
                    "media saved type=%s path=%s count=%s",
                    media_type,
                    media_path,
                    len(media_paths),
                )
                note_id = _save_note(
                    user_id=USER_ID,
                    source_chat_id=str(BACKUP_CHAT),
                    source_name=SOURCE_NAME,
                    text=text,
                    media_type=media_type,
                    media_path=media_path,
                    media_paths=media_paths,
                    media_group_id=str(msg.media_group_id) if msg.media_group_id else None,
                )
                logger.info("NOTE CREATED id=%s for backup_msg=%s", note_id, mid)
                created.append((mid, note_id))
                ok += 1
            except Exception as e:
                from src.core.exceptions import ValidationError

                if isinstance(e, ValidationError) and "Duplicate" in str(e):
                    logger.info("duplicate note, skip msg %s", mid)
                    skipped += 1
                else:
                    logger.exception("save failed for msg %s: %s", mid, e)
                    failed += 1
            # 轻微限速，避免 flood / webdav 压力
            await asyncio.sleep(1.0)

    logger.info("=" * 60)
    logger.info("done ok=%s skipped=%s failed=%s", ok, skipped, failed)
    if created:
        logger.info("created notes: %s", created)
    return 0 if failed == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill backup channel messages into web notes")
    parser.add_argument("--ids", default="2733-2738", help="backup message ids")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    ids = _parse_ids(args.ids)
    if not ids:
        print("no ids", file=sys.stderr)
        return 2
    logger.info("ids=%s dry_run=%s", ids, args.dry_run)
    # 组合根装配：脚本同样经 NoteService 写入，需要注入校准/存储实现
    configure_runtime_implementations()
    return asyncio.run(backfill(ids, dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
