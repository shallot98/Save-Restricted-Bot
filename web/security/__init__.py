"""
Web 安全基线模块

遵循 KISS：提供最小可用的 CSRF、防护头与限流组件，避免引入硬依赖。
"""

from web.security.csrf import init_csrf
from web.security.headers import init_security_headers

__all__ = ["init_csrf", "init_security_headers"]

