"""
CSRF 防护

实现策略：
- Token 存在 session 中（每个浏览器会话一个 token）
- 模板通过 `csrf_token()` 注入 token
- 对非安全方法（POST/PUT/PATCH/DELETE）校验 token：
  - Header: X-CSRFToken / X-CSRF-Token
  - Form: csrf_token
  - JSON: csrf_token

说明：不依赖 Flask-WTF，避免额外依赖导致运行失败。
"""

from __future__ import annotations

import hmac
import secrets
from typing import Optional

from flask import Flask, abort, request, session

CSRF_SESSION_KEY = "_csrf_token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_HEADER_NAMES = ("X-CSRFToken", "X-CSRF-Token")
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def csrf_token() -> str:
    """获取（或生成）当前 session 的 CSRF token。"""
    token = session.get(CSRF_SESSION_KEY)
    if isinstance(token, str) and token:
        return token
    token = secrets.token_urlsafe(32)
    session[CSRF_SESSION_KEY] = token
    return token


def _get_request_csrf_token() -> Optional[str]:
    for header_name in CSRF_HEADER_NAMES:
        value = request.headers.get(header_name)
        if value:
            return value

    value = request.form.get(CSRF_FORM_FIELD)
    if value:
        return value

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        value = payload.get(CSRF_FORM_FIELD)
        if isinstance(value, str) and value:
            return value

    return None


def _should_check_csrf() -> bool:
    method = (request.method or "").upper()
    if method in SAFE_METHODS:
        return False

    # Flask 在某些场景下 endpoint 可能为空（如 404），无需校验
    if request.endpoint is None:
        return False

    # 跳过静态文件（通常仅 GET，但这里做防御性处理）
    if request.endpoint.endswith("static"):
        return False

    return True


def init_csrf(app: Flask) -> None:
    """为 Flask App 启用 CSRF 校验与模板注入。"""

    @app.before_request
    def _csrf_protect():
        if not _should_check_csrf():
            return None

        expected = csrf_token()
        provided = _get_request_csrf_token()
        if not provided or not hmac.compare_digest(str(provided), str(expected)):
            abort(403)

        return None

    @app.context_processor
    def _inject_csrf():
        return {"csrf_token": csrf_token}

