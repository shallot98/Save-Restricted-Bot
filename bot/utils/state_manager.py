"""
用户状态管理器

遵循 SOLID 原则：
- SRP: 仅负责用户状态的存储和管理
- OCP: 通过配置参数扩展行为
- DIP: 提供抽象接口供外部使用

特性：
- 线程安全
- 状态过期自动清理
- 状态大小限制
"""
import time
import threading
import logging
from collections.abc import MutableMapping, Iterator
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class UserState:
    """用户状态数据类"""
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def update(self, **kwargs) -> None:
        """更新状态数据"""
        self.data.update(kwargs)
        self.updated_at = time.time()

    def is_expired(self, ttl_seconds: float) -> bool:
        """检查状态是否过期

        Args:
            ttl_seconds: 生存时间（秒）

        Returns:
            bool: 是否已过期
        """
        return time.time() - self.updated_at > ttl_seconds


class UserStateManager:
    """线程安全的用户状态管理器

    特性：
    - 线程安全的读写操作
    - 自动清理过期状态
    - 状态数量限制防止内存泄漏

    Usage:
        manager = UserStateManager()
        manager.set(user_id, {"action": "add_source"})
        state = manager.get(user_id)
        manager.clear(user_id)
    """

    # 默认配置
    DEFAULT_TTL_SECONDS = 3600  # 1 小时
    DEFAULT_MAX_STATES = 1000   # 最大状态数量
    DEFAULT_CLEANUP_INTERVAL = 300  # 5 分钟清理一次

    def __init__(
        self,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_states: int = DEFAULT_MAX_STATES,
        cleanup_interval: float = DEFAULT_CLEANUP_INTERVAL
    ):
        """初始化状态管理器

        Args:
            ttl_seconds: 状态生存时间（秒）
            max_states: 最大状态数量
            cleanup_interval: 清理间隔（秒）
        """
        self._states: Dict[str, UserState] = {}
        self._lock = threading.RLock()
        self._ttl_seconds = ttl_seconds
        self._max_states = max_states
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

    def get(self, user_id: str) -> Dict[str, Any]:
        """获取用户状态

        Args:
            user_id: 用户 ID

        Returns:
            Dict: 用户状态数据，不存在返回空字典
        """
        with self._lock:
            self._maybe_cleanup()
            state = self._states.get(user_id)
            if state is None:
                return {}
            if state.is_expired(self._ttl_seconds):
                del self._states[user_id]
                return {}
            return state.data.copy()

    def set(self, user_id: str, data: Dict[str, Any]) -> None:
        """设置用户状态

        Args:
            user_id: 用户 ID
            data: 状态数据
        """
        with self._lock:
            self._maybe_cleanup()
            self._enforce_max_states()
            self._states[user_id] = UserState(data=data.copy())

    def update(self, user_id: str, **kwargs) -> None:
        """更新用户状态

        Args:
            user_id: 用户 ID
            **kwargs: 要更新的键值对
        """
        with self._lock:
            if user_id not in self._states:
                self._states[user_id] = UserState()
            self._states[user_id].update(**kwargs)

    def clear(self, user_id: str) -> bool:
        """清除用户状态

        Args:
            user_id: 用户 ID

        Returns:
            bool: 是否成功清除（状态存在）
        """
        with self._lock:
            if user_id in self._states:
                del self._states[user_id]
                return True
            return False

    def exists(self, user_id: str) -> bool:
        """检查用户状态是否存在

        Args:
            user_id: 用户 ID

        Returns:
            bool: 状态是否存在且未过期
        """
        with self._lock:
            state = self._states.get(user_id)
            if state is None:
                return False
            if state.is_expired(self._ttl_seconds):
                del self._states[user_id]
                return False
            return True

    def __contains__(self, user_id: str) -> bool:
        """支持 `in` 操作符"""
        return self.exists(user_id)

    def __getitem__(self, user_id: str) -> Dict[str, Any]:
        """支持 `manager[user_id]` 语法"""
        return self.get(user_id)

    def __setitem__(self, user_id: str, data: Dict[str, Any]) -> None:
        """支持 `manager[user_id] = data` 语法"""
        self.set(user_id, data)

    def __delitem__(self, user_id: str) -> None:
        """支持 `del manager[user_id]` 语法"""
        self.clear(user_id)

    def _maybe_cleanup(self) -> None:
        """如果达到清理间隔，执行清理"""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        self._cleanup_expired()

    def _cleanup_expired(self) -> int:
        """清理过期状态

        Returns:
            int: 清理的状态数量
        """
        expired_keys = [
            user_id for user_id, state in self._states.items()
            if state.is_expired(self._ttl_seconds)
        ]

        for user_id in expired_keys:
            del self._states[user_id]

        if expired_keys:
            logger.debug(f"🧹 清理了 {len(expired_keys)} 个过期用户状态")

        return len(expired_keys)

    def _enforce_max_states(self) -> None:
        """强制执行最大状态数量限制"""
        if len(self._states) < self._max_states:
            return

        # 按更新时间排序，删除最旧的状态
        sorted_states = sorted(
            self._states.items(),
            key=lambda x: x[1].updated_at
        )

        # 删除最旧的 10% 状态
        to_remove = max(1, len(sorted_states) // 10)
        for user_id, _ in sorted_states[:to_remove]:
            del self._states[user_id]

        logger.warning(f"⚠️ 用户状态数量超限，清理了 {to_remove} 个最旧状态")

    def stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            Dict: 统计信息
        """
        with self._lock:
            return {
                "total_states": len(self._states),
                "max_states": self._max_states,
                "ttl_seconds": self._ttl_seconds,
                "cleanup_interval": self._cleanup_interval
            }


# 全局单例实例
_state_manager: Optional[UserStateManager] = None
_instance_lock = threading.Lock()


def get_state_manager() -> UserStateManager:
    """获取全局状态管理器单例

    Returns:
        UserStateManager: 状态管理器实例
    """
    global _state_manager
    if _state_manager is None:
        with _instance_lock:
            if _state_manager is None:
                _state_manager = UserStateManager()
    return _state_manager


# 向后兼容的全局变量代理
class _UserStatesProxy:
    """user_states 全局变量的代理类

    提供向后兼容的字典接口，内部使用 UserStateManager
    """

    class _UserStateDataView(MutableMapping[str, Any]):
        """单用户状态的可变视图。

        目的：兼容历史写法 `user_states[user_id]["k"] = v`，同时确保：
        - 线程安全（所有读写持锁）
        - 任何写操作都会更新 `updated_at`，避免 TTL 清理误删
        """

        def __init__(self, manager: UserStateManager, user_id: str) -> None:
            self._manager = manager
            self._user_id = user_id

        def _get_or_create_state_locked(self) -> UserState:
            state = self._manager._states.get(self._user_id)
            if state is None or state.is_expired(self._manager._ttl_seconds):
                if state is not None:
                    del self._manager._states[self._user_id]
                self._manager._enforce_max_states()
                state = UserState()
                self._manager._states[self._user_id] = state
            return state

        def __getitem__(self, key: str) -> Any:
            with self._manager._lock:
                self._manager._maybe_cleanup()
                state = self._get_or_create_state_locked()
                return state.data[key]

        def __setitem__(self, key: str, value: Any) -> None:
            with self._manager._lock:
                self._manager._maybe_cleanup()
                state = self._get_or_create_state_locked()
                state.data[key] = value
                state.updated_at = time.time()

        def __delitem__(self, key: str) -> None:
            with self._manager._lock:
                self._manager._maybe_cleanup()
                state = self._get_or_create_state_locked()
                del state.data[key]
                state.updated_at = time.time()

        def __iter__(self) -> Iterator[str]:
            with self._manager._lock:
                self._manager._maybe_cleanup()
                state = self._get_or_create_state_locked()
                return iter(list(state.data.keys()))

        def __len__(self) -> int:
            with self._manager._lock:
                self._manager._maybe_cleanup()
                state = self._get_or_create_state_locked()
                return len(state.data)

        def clear(self) -> None:
            with self._manager._lock:
                self._manager._maybe_cleanup()
                state = self._get_or_create_state_locked()
                state.data.clear()
                state.updated_at = time.time()

        def update(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
            with self._manager._lock:
                self._manager._maybe_cleanup()
                state = self._get_or_create_state_locked()
                state.data.update(*args, **kwargs)
                state.updated_at = time.time()

    def __getitem__(self, user_id: str) -> MutableMapping[str, Any]:
        manager = get_state_manager()
        return self._UserStateDataView(manager, user_id)

    def __setitem__(self, user_id: str, data: Dict[str, Any]) -> None:
        get_state_manager().set(user_id, data)

    def __delitem__(self, user_id: str) -> None:
        get_state_manager().clear(user_id)

    def __contains__(self, user_id: str) -> bool:
        return get_state_manager().exists(user_id)

    def get(self, user_id: str, default: Any = None) -> Any:
        state = get_state_manager().get(user_id)
        return state if state else default


# 向后兼容的全局变量
user_states = _UserStatesProxy()
