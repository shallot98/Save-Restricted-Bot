"""
轻量级限流（进程内）

用于降低暴力破解/刷接口风险：
- 默认仅用于登录接口
- 纯内存实现，适合单实例/低量级场景
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


def _int_env(var_name: str, default: int) -> int:
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class RateLimitConfig:
    max_attempts: int
    window_seconds: int


class SlidingWindowRateLimiter:
    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._attempts: Dict[str, List[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self._config.window_seconds

        with self._lock:
            timestamps = self._attempts.get(key, [])
            timestamps = [ts for ts in timestamps if ts >= cutoff]

            if len(timestamps) >= self._config.max_attempts:
                self._attempts[key] = timestamps
                return False

            timestamps.append(now)
            self._attempts[key] = timestamps
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


_login_limiter: Optional[SlidingWindowRateLimiter] = None
_login_limiter_lock = threading.Lock()


def get_login_rate_limiter() -> SlidingWindowRateLimiter:
    """获取登录限流器单例。"""
    global _login_limiter
    if _login_limiter is None:
        with _login_limiter_lock:
            if _login_limiter is None:
                config = RateLimitConfig(
                    max_attempts=_int_env("LOGIN_RATE_LIMIT_MAX", default=10),
                    window_seconds=_int_env("LOGIN_RATE_LIMIT_WINDOW_SECONDS", default=600),
                )
                _login_limiter = SlidingWindowRateLimiter(config)
    return _login_limiter

