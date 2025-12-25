"""
安全响应头

目标：提供基础防护（XSS/Clickjacking/信息泄露）且尽量不破坏现有页面。
"""

from __future__ import annotations

import os
import secrets
from typing import Optional

from flask import Flask, g, request


def _truthy_env(var_name: str, default: bool = False) -> bool:
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


_CSP_NONCE_G_KEY = "_csp_nonce"
_CSP_ALLOW_UNSAFE_EVAL_G_KEY = "csp_allow_unsafe_eval"


def _get_csp_nonce() -> str:
    nonce = getattr(g, _CSP_NONCE_G_KEY, None)
    if nonce:
        return nonce
    nonce = secrets.token_urlsafe(16)
    setattr(g, _CSP_NONCE_G_KEY, nonce)
    return nonce


def _build_csp(
    *,
    nonce: Optional[str],
    allow_unsafe_inline: bool,
    allow_unsafe_eval: bool,
) -> str:
    # 由于模板/页面存在内联样式，style-src 仍保留 'unsafe-inline'。
    # script-src 通过 nonce 逐步收紧（并保留 'unsafe-eval' 以兼容 Alpine.js 的表达式求值）。
    #
    # 注意：当前使用的 Alpine.js 构建依赖 `new Function(...)` 进行表达式求值，
    # 若不允许 'unsafe-eval' 会导致前端交互功能失效（CSP 报错并阻断执行）。
    script_src_parts = ["'self'"]
    if nonce:
        script_src_parts.append(f"'nonce-{nonce}'")
    if allow_unsafe_inline:
        script_src_parts.append("'unsafe-inline'")
    if allow_unsafe_eval:
        script_src_parts.append("'unsafe-eval'")
    script_src = "script-src " + " ".join(script_src_parts) + "; "

    return (
        "default-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "img-src 'self' data: blob: http: https:; "
        "media-src 'self' blob: http: https:; "
        f"{script_src}"
        "script-src-attr 'none'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "object-src 'none'"
    )


def init_security_headers(app: Flask, csp: Optional[str] = None) -> None:
    """为所有响应追加基础安全头。"""

    use_script_nonce = _truthy_env("CSP_SCRIPT_NONCE", default=True)
    allow_unsafe_inline = _truthy_env("CSP_ALLOW_UNSAFE_INLINE", default=not use_script_nonce)
    default_allow_unsafe_eval = _truthy_env("CSP_ALLOW_UNSAFE_EVAL", default=True)

    resolved_csp = csp
    enable_hsts = _truthy_env("ENABLE_HSTS", default=False)

    app.add_template_global(_get_csp_nonce, name="csp_nonce")

    @app.after_request
    def _set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )

        if resolved_csp:
            response.headers.setdefault("Content-Security-Policy", resolved_csp)
        else:
            nonce = _get_csp_nonce() if use_script_nonce else None
            allow_unsafe_eval = getattr(g, _CSP_ALLOW_UNSAFE_EVAL_G_KEY, default_allow_unsafe_eval)
            allow_unsafe_eval = bool(allow_unsafe_eval)
            response.headers.setdefault(
                "Content-Security-Policy",
                _build_csp(
                    nonce=nonce,
                    allow_unsafe_inline=allow_unsafe_inline,
                    allow_unsafe_eval=allow_unsafe_eval,
                ),
            )

        # HTML 页面默认不缓存（避免敏感页面被浏览器/代理缓存）。
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        # 仅在 HTTPS 场景下启用 HSTS，避免本地 http 开发被“锁死”。
        if enable_hsts and request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response
