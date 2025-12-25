"""
Concurrency tests for cache implementation
"""

import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from src.infrastructure.cache.unified import UnifiedCache
from src.infrastructure.cache.decorators import cached


class TestCacheConcurrency:
    """Tests for thread-safety of cache operations"""

    @pytest.fixture
    def cache(self):
        """Create a fresh cache instance for each test"""
        return UnifiedCache(
            default_ttl=60.0,
            max_size=1000,
            cleanup_interval=10.0,
            name="concurrency_test"
        )

    def test_concurrent_reads(self, cache):
        """Test concurrent read operations"""
        # Pre-populate cache
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}")

        errors = []
        results = []

        def read_task(key_id):
            try:
                value = cache.get(f"key_{key_id}")
                if value != f"value_{key_id}":
                    errors.append(f"Unexpected value for key_{key_id}: {value}")
                results.append(value)
            except Exception as e:
                errors.append(str(e))

        # Run concurrent reads
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(read_task, i % 100) for i in range(500)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 500

    def test_concurrent_writes(self, cache):
        """Test concurrent write operations"""
        errors = []
        write_count = 0
        lock = threading.Lock()

        def write_task(key_id):
            nonlocal write_count
            try:
                cache.set(f"key_{key_id}", f"value_{key_id}")
                with lock:
                    write_count += 1
            except Exception as e:
                errors.append(str(e))

        # Run concurrent writes
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(write_task, i) for i in range(500)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert write_count == 500

        # Verify all values are correct
        for i in range(500):
            assert cache.get(f"key_{i}") == f"value_{i}"

    def test_concurrent_read_write(self, cache):
        """Test concurrent read and write operations"""
        errors = []
        operations = []
        lock = threading.Lock()

        def read_write_task(task_id):
            try:
                key = f"key_{task_id % 50}"
                if task_id % 2 == 0:
                    # Write
                    cache.set(key, f"value_{task_id}")
                    with lock:
                        operations.append(("write", key))
                else:
                    # Read
                    value = cache.get(key)
                    with lock:
                        operations.append(("read", key, value))
            except Exception as e:
                errors.append(str(e))

        # Run concurrent read/write
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(read_write_task, i) for i in range(500)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(operations) == 500

    def test_concurrent_get_or_set(self, cache):
        """Test concurrent get_or_set operations"""
        call_counts: Dict[str, int] = {}
        lock = threading.Lock()

        def factory(key):
            with lock:
                call_counts[key] = call_counts.get(key, 0) + 1
            time.sleep(0.01)  # Simulate slow computation
            return f"computed_{key}"

        errors = []
        results = []

        def get_or_set_task(key_id):
            try:
                key = f"key_{key_id % 10}"  # Only 10 unique keys
                value = cache.get_or_set(key, lambda: factory(key))
                results.append((key, value))
            except Exception as e:
                errors.append(str(e))

        # Run concurrent get_or_set
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(get_or_set_task, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 100

        # Each key should have been computed at most a few times
        # (due to race conditions, might be more than 1 but should be limited)
        for key, count in call_counts.items():
            assert count <= 5, f"Key {key} was computed {count} times"

    def test_concurrent_delete(self, cache):
        """Test concurrent delete operations"""
        # Pre-populate cache
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}")

        errors = []
        delete_results = []
        lock = threading.Lock()

        def delete_task(key_id):
            try:
                result = cache.delete(f"key_{key_id}")
                with lock:
                    delete_results.append((key_id, result))
            except Exception as e:
                errors.append(str(e))

        # Run concurrent deletes (some keys will be deleted multiple times)
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(delete_task, i % 100) for i in range(200)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"

        # All keys should be deleted
        for i in range(100):
            assert cache.get(f"key_{i}") is None

    def test_concurrent_clear(self, cache):
        """Test concurrent clear operations"""
        errors = []

        def populate_and_clear(iteration):
            try:
                # Populate
                for i in range(10):
                    cache.set(f"iter_{iteration}_key_{i}", f"value_{i}")
                # Clear
                cache.clear()
            except Exception as e:
                errors.append(str(e))

        # Run concurrent populate and clear
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(populate_and_clear, i) for i in range(50)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"

    def test_concurrent_stats(self, cache):
        """Test concurrent stats access"""
        errors = []
        stats_results = []
        lock = threading.Lock()

        def stats_task(task_id):
            try:
                # Mix of operations
                cache.set(f"key_{task_id}", f"value_{task_id}")
                cache.get(f"key_{task_id}")
                cache.get(f"nonexistent_{task_id}")

                stats = cache.stats()
                with lock:
                    stats_results.append(stats)
            except Exception as e:
                errors.append(str(e))

        # Run concurrent stats access
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(stats_task, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(stats_results) == 100

        # All stats should be valid dictionaries
        for stats in stats_results:
            assert "size" in stats
            assert "hits" in stats
            assert "misses" in stats

    def test_concurrent_pattern_delete(self, cache):
        """Test concurrent pattern delete operations"""
        # Pre-populate cache
        for i in range(100):
            cache.set(f"user:1:key_{i}", f"value_{i}")
            cache.set(f"user:2:key_{i}", f"value_{i}")

        errors = []
        delete_counts = []
        lock = threading.Lock()

        def pattern_delete_task(user_id):
            try:
                count = cache.delete_pattern(f"user:{user_id}:*")
                with lock:
                    delete_counts.append((user_id, count))
            except Exception as e:
                errors.append(str(e))

        # Run concurrent pattern deletes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(pattern_delete_task, i % 2 + 1) for i in range(20)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"

        # All user keys should be deleted
        for i in range(100):
            assert cache.get(f"user:1:key_{i}") is None
            assert cache.get(f"user:2:key_{i}") is None


class TestDecoratorConcurrency:
    """Tests for thread-safety of cached decorator"""

    def test_concurrent_decorated_function(self):
        """Test concurrent calls to decorated function"""
        cache = UnifiedCache(name="decorator_concurrency_test")
        call_count = 0
        lock = threading.Lock()

        @cached(ttl=60, cache_instance=cache)
        def expensive_function(x):
            nonlocal call_count
            with lock:
                call_count += 1
            time.sleep(0.01)  # Simulate slow computation
            return x * 2

        errors = []
        results = []

        def call_task(value):
            try:
                result = expensive_function(value)
                results.append((value, result))
            except Exception as e:
                errors.append(str(e))

        # Run concurrent calls with same arguments
        with ThreadPoolExecutor(max_workers=20) as executor:
            # 100 calls with only 10 unique values
            futures = [executor.submit(call_task, i % 10) for i in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 100

        # Function should be called at most a few times per unique value
        # (due to race conditions)
        assert call_count <= 30, f"Function called {call_count} times"

        # All results should be correct
        for value, result in results:
            assert result == value * 2


class TestCacheEvictionConcurrency:
    """Tests for thread-safety of cache eviction"""

    def test_concurrent_eviction(self):
        """Test concurrent operations during eviction"""
        cache = UnifiedCache(
            default_ttl=60.0,
            max_size=50,  # Small size to trigger eviction
            name="eviction_test"
        )

        errors = []
        operations = []
        lock = threading.Lock()

        def write_task(key_id):
            try:
                cache.set(f"key_{key_id}", f"value_{key_id}")
                with lock:
                    operations.append(("write", key_id))
            except Exception as e:
                errors.append(str(e))

        # Run many concurrent writes to trigger eviction
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(write_task, i) for i in range(500)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(operations) == 500

        # Cache size should not exceed max_size
        assert cache.size <= 50


class TestCacheExpirationConcurrency:
    """Tests for thread-safety during expiration"""

    def test_concurrent_expiration(self):
        """Test concurrent operations during expiration"""
        cache = UnifiedCache(
            default_ttl=0.1,  # Very short TTL
            max_size=1000,
            cleanup_interval=0.05,
            name="expiration_test"
        )

        errors = []

        def write_and_read_task(key_id):
            try:
                key = f"key_{key_id}"
                cache.set(key, f"value_{key_id}")
                time.sleep(0.05)  # Wait a bit
                value = cache.get(key)  # Might be expired
                # Value can be None (expired) or the original value
                if value is not None and value != f"value_{key_id}":
                    errors.append(f"Unexpected value: {value}")
            except Exception as e:
                errors.append(str(e))

        # Run concurrent operations during expiration
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(write_and_read_task, i) for i in range(200)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
