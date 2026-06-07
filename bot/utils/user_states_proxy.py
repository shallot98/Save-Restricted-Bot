"""Backward-compatible mapping proxy for user states."""

from collections.abc import Iterator, MutableMapping
from typing import Any, Callable, Dict


class UserStatesProxy:
    """Dictionary-like proxy backed by UserStateManager."""

    class _UserStateDataView(MutableMapping[str, Any]):
        """Mutable view for one user's state data."""

        def __init__(
            self,
            manager,
            user_id: str,
            *,
            state_factory: Callable[[], Any],
            now: Callable[[], float],
        ) -> None:
            self._manager = manager
            self._user_id = user_id
            self._state_factory = state_factory
            self._now = now

        def _get_or_create_state_locked(self):
            state = self._manager._states.get(self._user_id)
            if state is None or state.is_expired(self._manager._ttl_seconds):
                if state is not None:
                    del self._manager._states[self._user_id]
                self._manager._enforce_max_states()
                state = self._state_factory()
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
                state.updated_at = self._now()

        def __delitem__(self, key: str) -> None:
            with self._manager._lock:
                self._manager._maybe_cleanup()
                state = self._get_or_create_state_locked()
                del state.data[key]
                state.updated_at = self._now()

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
                state.updated_at = self._now()

        def update(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
            with self._manager._lock:
                self._manager._maybe_cleanup()
                state = self._get_or_create_state_locked()
                state.data.update(*args, **kwargs)
                state.updated_at = self._now()

    def __init__(
        self,
        manager_factory: Callable[[], Any],
        state_factory: Callable[[], Any],
        now: Callable[[], float],
    ) -> None:
        self._manager_factory = manager_factory
        self._state_factory = state_factory
        self._now = now

    def __getitem__(self, user_id: str) -> MutableMapping[str, Any]:
        manager = self._manager_factory()
        return self._UserStateDataView(
            manager,
            user_id,
            state_factory=self._state_factory,
            now=self._now,
        )

    def __setitem__(self, user_id: str, data: Dict[str, Any]) -> None:
        self._manager_factory().set(user_id, data)

    def __delitem__(self, user_id: str) -> None:
        self._manager_factory().clear(user_id)

    def __contains__(self, user_id: str) -> bool:
        return self._manager_factory().exists(user_id)

    def get(self, user_id: str, default: Any = None) -> Any:
        state = self._manager_factory().get(user_id)
        return state if state else default

    def pop(self, user_id: str, default: Any = None) -> Any:
        manager = self._manager_factory()
        state = manager.get(user_id)
        if state:
            manager.clear(user_id)
            return state
        return default
