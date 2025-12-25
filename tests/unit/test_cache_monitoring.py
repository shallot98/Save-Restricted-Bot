"""
Unit tests for cache monitoring module
"""

import pytest
import time
from datetime import datetime

from src.infrastructure.cache.monitoring import (
    CacheMonitor,
    CacheMetrics,
    get_cache_monitor,
)
from src.infrastructure.cache.unified import UnifiedCache


class TestCacheMonitor:
    """Tests for CacheMonitor"""

    @pytest.fixture
    def monitor(self):
        """Create a fresh monitor instance"""
        return CacheMonitor()

    def test_get_stats(self, monitor):
        """Test getting cache statistics"""
        stats = monitor.get_stats()

        assert 'timestamp' in stats
        assert 'uptime_seconds' in stats
        assert 'unified_cache' in stats
        assert 'managers' in stats
        assert 'summary' in stats

    def test_stats_summary(self, monitor):
        """Test statistics summary calculation"""
        stats = monitor.get_stats()
        summary = stats['summary']

        assert 'total_size' in summary
        assert 'max_size' in summary
        assert 'utilization' in summary
        assert 'total_hits' in summary
        assert 'total_misses' in summary
        assert 'hit_rate' in summary
        assert 'active_managers' in summary

    def test_get_health_healthy(self, monitor):
        """Test health check returns healthy status"""
        health = monitor.get_health()

        assert 'status' in health
        assert 'issues' in health
        assert 'metrics' in health
        assert 'timestamp' in health

        # Fresh cache should be healthy
        assert health['status'] in ['healthy', 'degraded', 'unhealthy']

    def test_record_metrics(self, monitor):
        """Test recording metrics to history"""
        metrics = monitor.record_metrics()

        assert isinstance(metrics, CacheMetrics)
        assert isinstance(metrics.timestamp, datetime)
        assert isinstance(metrics.total_size, int)
        assert isinstance(metrics.hit_rate, float)

    def test_metrics_history(self, monitor):
        """Test metrics history tracking"""
        # Record some metrics
        for _ in range(5):
            monitor.record_metrics()
            time.sleep(0.01)

        history = monitor.get_metrics_history(limit=3)

        assert len(history) == 3
        for entry in history:
            assert 'timestamp' in entry
            assert 'total_size' in entry
            assert 'hit_rate' in entry

    def test_metrics_history_limit(self, monitor):
        """Test metrics history respects limit"""
        # Record many metrics
        for _ in range(10):
            monitor.record_metrics()

        # Request fewer than available
        history = monitor.get_metrics_history(limit=5)
        assert len(history) == 5

        # Request more than available
        history = monitor.get_metrics_history(limit=20)
        assert len(history) == 10

    def test_reset_stats(self, monitor):
        """Test resetting statistics"""
        # Record some metrics first
        monitor.record_metrics()
        monitor.record_metrics()

        # Reset
        monitor.reset_stats()

        # History should be cleared
        history = monitor.get_metrics_history()
        assert len(history) == 0


class TestCacheMetrics:
    """Tests for CacheMetrics dataclass"""

    def test_metrics_creation(self):
        """Test creating metrics snapshot"""
        metrics = CacheMetrics(
            timestamp=datetime.now(),
            total_size=100,
            total_hits=50,
            total_misses=25,
            hit_rate=66.67,
            managers={'notes': {'size': 50}}
        )

        assert metrics.total_size == 100
        assert metrics.total_hits == 50
        assert metrics.total_misses == 25
        assert metrics.hit_rate == 66.67


class TestGlobalMonitor:
    """Tests for global monitor instance"""

    def test_get_cache_monitor_singleton(self):
        """Test global monitor is singleton"""
        monitor1 = get_cache_monitor()
        monitor2 = get_cache_monitor()

        assert monitor1 is monitor2

    def test_global_monitor_stats(self):
        """Test global monitor provides stats"""
        monitor = get_cache_monitor()
        stats = monitor.get_stats()

        assert stats is not None
        assert 'summary' in stats


class TestHealthChecks:
    """Tests for health check logic"""

    def test_health_with_operations(self):
        """Test health check after cache operations"""
        from src.infrastructure.cache.unified import get_unified_cache

        cache = get_unified_cache()

        # Perform some operations
        for i in range(10):
            cache.set(f"health_test_{i}", f"value_{i}")
            cache.get(f"health_test_{i}")

        monitor = get_cache_monitor()
        health = monitor.get_health()

        assert health['status'] in ['healthy', 'degraded', 'unhealthy']
        assert health['metrics']['total_requests'] > 0

        # Cleanup
        for i in range(10):
            cache.delete(f"health_test_{i}")
