"""
qBittorrent Service
===================

Application service for qBittorrent download operations.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple, Dict, Any, List

import requests

from src.domain.magnet import MagnetLinkParser


class QBittorrentService:
    """Encapsulate qBittorrent API interactions for web routes."""

    def __init__(self) -> None:
        self._url = os.environ.get('QBT_URL', 'http://localhost:8080').rstrip('/')
        self._username = os.environ.get('QBT_USERNAME', 'admin')
        self._password = os.environ.get('QBT_PASSWORD', '')
        self._download_path = os.environ.get('QBT_DOWNLOAD_PATH', '/mnt/openlist/downloads')
        self._download_category = os.environ.get('QBT_DOWNLOAD_CATEGORY', 'notes')

    def add_note_download(self, note_dto: Any, magnet_index: Any) -> Tuple[Dict[str, Any], int]:
        magnets = self.extract_note_magnets_for_download(note_dto)
        if not magnets:
            return {'success': False, 'error': '没有找到磁力链接'}, 404

        idx, error = self._normalize_magnet_index(magnet_index, len(magnets))
        if error:
            return error

        selected = magnets[idx]
        magnet, info_hash, selected_error = self._prepare_selected_magnet(selected)
        if selected_error:
            return selected_error

        session = requests.Session()
        try:
            ok, err = self._login(session)
            if not ok:
                return {'success': False, 'error': err or '无法连接到 qBittorrent'}, 502

            resp = self._add_torrent(session, magnet)
            if resp.text != 'Ok.':
                return self._handle_add_torrent_failure(session, info_hash, resp.text)

            return {
                'success': True,
                'info_hash': info_hash.lower(),
                'status': 'pending',
                'progress': 0,
            }, 200
        finally:
            session.close()

    def _prepare_selected_magnet(
        self,
        selected: Dict[str, Optional[str]],
    ) -> Tuple[str, str, Optional[Tuple[Dict[str, Any], int]]]:
        magnet = self._normalize_string(selected.get('magnet'))
        info_hash = self._normalize_string(selected.get('info_hash'))
        if not info_hash and magnet:
            info_hash = self._normalize_string(MagnetLinkParser.extract_info_hash(magnet))
        if not info_hash:
            return '', '', ({'success': False, 'error': '缺少 info_hash，无法添加下载任务'}, 400)
        return magnet or f'magnet:?xt=urn:btih:{info_hash}', info_hash, None

    def _add_torrent(self, session: requests.Session, magnet: str) -> requests.Response:
        return session.post(
            f"{self._url}/api/v2/torrents/add",
            data={
                'urls': magnet,
                'savepath': self._download_path,
                'category': self._download_category,
            },
            timeout=10,
        )

    def _handle_add_torrent_failure(
        self,
        session: requests.Session,
        info_hash: str,
        response_text: str,
    ) -> Tuple[Dict[str, Any], int]:
        torrent, error = self._get_torrent(session, info_hash)
        if not torrent:
            return {'success': False, 'error': f'添加下载任务失败: {error or response_text}'}, 502
        status, progress = self._map_status(torrent)
        return {
            'success': True,
            'info_hash': info_hash.lower(),
            'status': status,
            'progress': progress,
            'message': '任务已存在',
        }, 200

    def get_download_status(self, info_hash: str) -> Tuple[Dict[str, Any], int]:
        normalized = self._normalize_string(info_hash).lower()
        if not normalized:
            return {'success': False, 'error': 'info_hash 必须是非空字符串'}, 400

        session = requests.Session()
        try:
            ok, err = self._login(session)
            if not ok:
                return {'success': False, 'error': err or '无法连接到 qBittorrent'}, 502

            torrent, error = self._get_torrent(session, normalized)
            if not torrent:
                if error:
                    return {'success': False, 'error': error}, 502
                return {
                    'success': True,
                    'info_hash': normalized,
                    'status': 'pending',
                    'progress': 0,
                    'found': False,
                }, 200

            status, progress = self._map_status(torrent)
            return {
                'success': True,
                'info_hash': normalized,
                'status': status,
                'progress': progress,
                'found': True,
                'state': torrent.get('state'),
                'name': torrent.get('name'),
            }, 200
        finally:
            session.close()

    @staticmethod
    def extract_note_magnets_for_download(note_dto: Any) -> List[Dict[str, Optional[str]]]:
        magnet_link = (getattr(note_dto, 'magnet_link', None) or '').strip()
        message_text = getattr(note_dto, 'message_text', None) or ''
        filename = getattr(note_dto, 'filename', None)

        all_info: List[Dict[str, Optional[str]]] = []
        if message_text:
            all_info.extend(MagnetLinkParser.extract_all_magnet_info(message_text))
        if magnet_link:
            all_info.extend(MagnetLinkParser.extract_all_magnet_info(magnet_link, filename=filename))

        results: List[Dict[str, Optional[str]]] = []
        seen_hashes: set[str] = set()
        seen_magnets: set[str] = set()
        for item in all_info:
            if not isinstance(item, dict):
                continue
            magnet = QBittorrentService._normalize_string(item.get('magnet'))
            info_hash = QBittorrentService._normalize_string(item.get('info_hash')) or None
            dn = QBittorrentService._normalize_string(item.get('dn')) or None

            if info_hash:
                key = info_hash.lower()
                if key in seen_hashes:
                    continue
                seen_hashes.add(key)
            else:
                normalized = magnet.lower()
                if not normalized or normalized in seen_magnets:
                    continue
                seen_magnets.add(normalized)

            results.append({'magnet': magnet, 'info_hash': info_hash, 'dn': dn})
        return results

    def _normalize_magnet_index(self, magnet_index: Any, magnet_count: int) -> Tuple[int, Optional[Tuple[Dict[str, Any], int]]]:
        if magnet_index is None:
            if magnet_count > 1:
                return -1, ({'success': False, 'error': '存在多个磁力链接，请指定 magnet_index'}, 400)
            return 0, None
        try:
            idx = int(magnet_index)
        except (TypeError, ValueError):
            return -1, ({'success': False, 'error': 'magnet_index 必须是整数'}, 400)
        if idx < 0 or idx >= magnet_count:
            return -1, ({'success': False, 'error': 'magnet_index 超出范围'}, 400)
        return idx, None

    def _login(self, session: requests.Session) -> Tuple[bool, Optional[str]]:
        try:
            version_url = f"{self._url}/api/v2/app/version"
            version_resp = session.get(version_url, timeout=5)
            if version_resp.status_code == 200:
                return True, None

            login_resp = session.post(
                f"{self._url}/api/v2/auth/login",
                data={'username': self._username, 'password': self._password},
                timeout=5,
            )
            if login_resp.text == 'Ok.':
                verify = session.get(version_url, timeout=5)
                if verify.status_code == 200:
                    return True, None
            return False, f"登录失败: {login_resp.text}"
        except Exception as exc:
            return False, f"连接失败: {exc}"

    def _get_torrent(self, session: requests.Session, info_hash: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            resp = session.get(
                f"{self._url}/api/v2/torrents/info",
                params={'hashes': info_hash.lower()},
                timeout=10,
            )
            if resp.status_code != 200:
                return None, f"查询 torrent 失败: HTTP {resp.status_code}"
            torrents = resp.json() if resp.text else []
            if not torrents:
                return None, None
            if isinstance(torrents, list):
                return torrents[0], None
            return None, 'qBittorrent 返回数据格式异常'
        except Exception as exc:
            return None, f"查询 torrent 失败: {exc}"

    @staticmethod
    def _map_status(torrent: dict) -> Tuple[str, float]:
        raw_progress = torrent.get('progress')
        try:
            progress = float(raw_progress)
        except (TypeError, ValueError):
            progress = 0.0
        progress = max(0.0, min(1.0, progress))
        state = str(torrent.get('state') or '')
        if state in {'error', 'missingFiles'}:
            return 'error', progress
        if progress >= 0.999 or state.endswith('UP') or state == 'uploading':
            return 'done', 1.0
        if progress <= 0.0 and state in {'metaDL', 'queuedDL', 'stalledDL', 'checkingDL', 'allocating', 'pausedDL'}:
            return 'pending', 0.0
        return 'downloading', progress

    @staticmethod
    def _normalize_string(value: Any) -> str:
        if not isinstance(value, str):
            return ''
        return value.strip()
