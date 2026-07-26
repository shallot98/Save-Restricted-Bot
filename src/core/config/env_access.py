"""配置取值 helper：config.json 优先、环境变量兜底。

原居 ``src/compat/config_compat.py``。Phase 3 删除 ``src/compat`` 时把这两个函数
提升到权威源，而不是随包一起删——它们不是「转接旧 API」的薄壳，而是**唯一**一处
「dict 优先、env 兜底」的取值语义实现（报告 §3 P1-8：真实优先级为
``环境变量 > config.json > .env > 默认值``，但 ``getenv`` 这条读取路径反过来，
是 setup.py 写入的 config.json 优先）。丢掉它等于丢掉一段行为。

两者的差别只在「缺失」的表达：

- :func:`getenv` 返回 ``""``，给的是「一定有个字符串」的旧契约；
- :func:`getenv_optional` 返回 ``None``，用于 session string 这类可选凭据——
  空串与全空白都算「未配置」，避免用空 STRING 去初始化 Pyrogram。

本模块零外部依赖（仅标准库），符合 §5.2 对 ``src.core`` 的约定。
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def getenv(var: str, data: Dict[str, Any]) -> str:
    """按「config.json 优先、环境变量兜底」取值，缺失时返回空字符串。

    Args:
        var: 配置键名。
        data: 已加载的主配置字典（通常是 ``settings.main_config``）。

    Returns:
        取到的值；未配置时为 ``""``。对 STRING 这类变量，空串即「未配置」。
    """
    config_value = data.get(var)
    if config_value:
        return config_value
    # 环境变量不存在返回 ""，存在则原样返回（可能本身就是空串）
    env_value = os.environ.get(var)
    return env_value if env_value is not None else ""


def getenv_optional(var: str, data: Dict[str, Any]) -> Optional[str]:
    """同 :func:`getenv`，但把缺失/空白显式表达为 ``None``。

    适用于 session string 这类可选凭据：空串或纯空白都视为「未配置」，
    调用方据此走「不启用」分支而不是拿着空串去连接。
    """
    config_value = data.get(var)
    if isinstance(config_value, str) and config_value.strip():
        return config_value.strip()

    env_value = os.environ.get(var)
    if env_value is None:
        return None

    env_value = env_value.strip()
    return env_value or None
