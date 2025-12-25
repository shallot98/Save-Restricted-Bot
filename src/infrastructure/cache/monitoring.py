"""
Cache Monitoring
================

Monitoring and statistics for cache layer.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .unified import get_unified_cache
from .managers import (
    get_note_cache_manager,
    get_config_cache_manager,
    get_peer_cache_manager,
)

logger = logging.getLogger(__name__)


@dataclass
class CacheMetrics:
    """Cache metrics snapshot"""
    timestamp: datetime
    total_size: int
    total_hits: int
    total_misses: int
    hit_rate: float
    managers: Dict[str, Dict[str, Any]]


class CacheMonitor:
    """
    Cache monitoring service

    Provides real-time statistics and health checks for cache layer.
    """

    def __init__(self):
        self._start_time = time.time()
        self._metrics_history: List[CacheMetrics] = []
        self._max_history = 100

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics

        Returns:
            Dictionary with cache statistics
        """
        unified_cache = get_unified_cache()
        unified_stats = unified_cache.stats()

        # Get manager-specific stats
        managers_stats = {}

        try:
            note_cache = get_note_cache_manager()
            managers_stats['notes'] = note_cache.stats()
        except Exception as e:
            managers_stats['notes'] = {'error': str(e)}

        try:
            config_cache = get_config_cache_manager()
            managers_stats['config'] = config_cache.stats()
        except Exception as e:
            managers_stats['config'] = {'error': str(e)}

        try:
            peer_cache = get_peer_cache_manager()
            managers_stats['peer'] = peer_cache.stats()
        except Exception as e:
            managers_stats['peer'] = {'error': str(e)}

        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': round(time.time() - self._start_time, 2),
            'unified_cache': unified_stats,
            'managers': managers_stats,
            'summary': self._calculate_summary(unified_stats, managers_stats)
        }

    def _calculate_summary(
        self,
        unified_stats: Dict[str, Any],
        managers_stats: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate summary statistics"""
        total_hits = unified_stats.get('hits', 0)
        total_misses = unified_stats.get('misses', 0)
        total_requests = total_hits + total_misses

        return {
            'total_size': unified_stats.get('size', 0),
            'max_size': unified_stats.get('max_size', 0),
            'utilization': round(
                unified_stats.get('size', 0) / max(unified_stats.get('max_size', 1), 1) * 100, 2
            ),
            'total_hits': total_hits,
            'total_misses': total_misses,
            'total_requests': total_requests,
            'hit_rate': round(total_hits / max(total_requests, 1) * 100, 2),
            'active_managers': len([m for m in managers_stats.values() if 'error' not in m])
        }

    def get_health(self) -> Dict[str, Any]:
        """
        Get cache health status

        Returns:
            Health status dictionary
        """
        stats = self.get_stats()
        summary = stats['summary']

        # Determine health status
        issues = []

        # Check utilization
        if summary['utilization'] > 90:
            issues.append('High cache utilization (>90%)')
        elif summary['utilization'] > 80:
            issues.append('Warning: Cache utilization >80%')

        # Check hit rate
        if summary['total_requests'] > 100:
            if summary['hit_rate'] < 30:
                issues.append('Low hit rate (<30%)')
            elif summary['hit_rate'] < 50:
                issues.append('Warning: Hit rate <50%')

        # Determine overall status
        if any('High' in i or 'Low' in i for i in issues):
            status = 'unhealthy'
        elif issues:
            status = 'degraded'
        else:
            status = 'healthy'

        return {
            'status': status,
            'issues': issues,
            'metrics': summary,
            'timestamp': datetime.now().isoformat()
        }

    def record_metrics(self) -> CacheMetrics:
        """
        Record current metrics to history

        Returns:
            Current metrics snapshot
        """
        stats = self.get_stats()
        summary = stats['summary']

        metrics = CacheMetrics(
            timestamp=datetime.now(),
            total_size=summary['total_size'],
            total_hits=summary['total_hits'],
            total_misses=summary['total_misses'],
            hit_rate=summary['hit_rate'],
            managers=stats['managers']
        )

        self._metrics_history.append(metrics)

        # Trim history if needed
        if len(self._metrics_history) > self._max_history:
            self._metrics_history = self._metrics_history[-self._max_history:]

        return metrics

    def get_metrics_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent metrics history

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of metrics snapshots
        """
        recent = self._metrics_history[-limit:]
        return [
            {
                'timestamp': m.timestamp.isoformat(),
                'total_size': m.total_size,
                'total_hits': m.total_hits,
                'total_misses': m.total_misses,
                'hit_rate': m.hit_rate
            }
            for m in recent
        ]

    def reset_stats(self) -> None:
        """Reset all cache statistics"""
        unified_cache = get_unified_cache()
        unified_cache.reset_stats()
        self._metrics_history.clear()
        logger.info("Cache statistics reset")


# Global monitor instance
_cache_monitor: Optional[CacheMonitor] = None


def get_cache_monitor() -> CacheMonitor:
    """Get global cache monitor instance"""
    global _cache_monitor
    if _cache_monitor is None:
        _cache_monitor = CacheMonitor()
    return _cache_monitor


__all__ = [
    "CacheMonitor",
    "CacheMetrics",
    "get_cache_monitor",
]
