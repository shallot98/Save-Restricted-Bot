"""
Port conformance for the infrastructure implementations behind the new ports.

守的是「实现漂移」：`src.infrastructure` 侧的方法名改了，而
`src.core.interfaces` 的端口没跟上——协议是结构化匹配，不会在 import 期
报错，只会在运行时 AttributeError。

范围说明：`issubclass` 对 runtime_checkable 协议只校验**方法是否存在**，
不校验签名；签名一致性由 mypy 在
`composition/container.py` 的 provider 返回类型上把关（provider 声明返回
端口类型，实现不匹配会直接报 return-value 错误）。

「组合根是否真的把 provider 传进服务」在
`tests/unit/test_container_implementation_wiring.py`。
"""

from __future__ import annotations

from composition.container import (
    _config_cache_provider,
    _note_cache_provider,
)
from src.core.interfaces import (
    BusinessMetricsRecorder,
    ConfigCache,
    ErrorTracker,
    NoteCache,
)
from src.infrastructure.cache.managers import ConfigCacheManager, NoteCacheManager
from src.infrastructure.monitoring.errors.tracker import ErrorTracker as ErrorTrackerImpl
from src.infrastructure.monitoring.performance.business_metrics import (
    BusinessMetricsCollector,
)


class TestImplementationsSatisfyPorts:
    """实现漂移守卫：协议是方法级的，用 issubclass 即可，无需实例化。

    刻意不实例化 `BusinessMetricsCollector`——它的构造会起后台上报线程。
    """

    def test_note_cache_manager_satisfies_port(self) -> None:
        assert issubclass(NoteCacheManager, NoteCache)

    def test_config_cache_manager_satisfies_port(self) -> None:
        assert issubclass(ConfigCacheManager, ConfigCache)

    def test_business_metrics_collector_satisfies_port(self) -> None:
        assert issubclass(BusinessMetricsCollector, BusinessMetricsRecorder)

    def test_error_tracker_satisfies_port(self) -> None:
        assert issubclass(ErrorTrackerImpl, ErrorTracker)

    def test_cache_providers_return_real_managers(self) -> None:
        assert isinstance(_note_cache_provider(), NoteCacheManager)
        assert isinstance(_config_cache_provider(), ConfigCacheManager)
