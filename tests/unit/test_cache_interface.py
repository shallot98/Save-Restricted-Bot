"""
Unit tests for cache interface and unified cache implementation
"""

import pytest
import time
from typing import Dict, Any

from src.infrastructure.cache.interface import (
    CacheInterface,
    CacheEventListener,
    InvalidationStrategy,
)
from src.infrastructure.cache.unified import (
    UnifiedCache,
    CacheEntry,
    CacheStats,
)
from src.infrastructure.cache.decorators import (
    cached,
    cache_invalidate,
    cache_aside,
)
from src.infrastructure.cache.managers import (
    NoteCacheManager,
    ConfigCacheManager,
    PeerCacheManager,
)


class TestCacheEntry:
    """Tests for CacheEntry dataclass"""

    def test_entry_not_expired(self):
        """Test entry is not expired when within TTL"""
        entry = CacheEntry(
            value="test",
            expires_at=time.time() + 100,
            created_at=time.time()
        )
        assert not entry.is_expired

    def test_entry_expired(self):
        """Test entry is expired when past TTL"""
        entry = CacheEntry(
            value="test",
            expires_at=time.time() - 1,
            created_at=time.time() - 10
        )
        assert entry.is_expired


class TestCacheStats:
    """Tests for CacheStats"""

    def test_initial_stats(self):
        """Test initial statistics are zero"""
        stats = CacheStats()
        result = stats.to_dict()
        assert result["hits"] == 0
        assert result["misses"] == 0
        assert result["sets"] == 0
        assert result["deletes"] == 0
        assert result["hit_rate"] == 0.0

    def test_record_operations(self):
        """Test recording cache operations"""
        stats = CacheStats()
        stats.record_hit()
        stats.record_hit()
        stats.record_miss()
        stats.record_set()
        stats.record_delete()

        result = stats.to_dict()
        assert result["hits"] == 2
        assert result["misses"] == 1
        assert result["sets"] == 1
        assert result["deletes"] == 1

    def test_hit_rate_calculation(self):
        """Test hit rate calculation"""
        stats = CacheStats()
        stats.record_hit()
        stats.record_hit()
        stats.record_hit()
        stats.record_miss()

        assert stats.hit_rate == 0.75

    def test_reset_stats(self):
        """Test resetting statistics"""
        stats = CacheStats()
        stats.record_hit()
        stats.record_miss()
        stats.reset()

        result = stats.to_dict()
        assert result["hits"] == 0
        assert result["misses"] == 0


class TestUnifiedCache:
    """Tests for UnifiedCache implementation"""

    @pytest.fixture
    def cache(self):
        """Create a fresh cache instance for each test"""
        return UnifiedCache(
            default_ttl=60.0,
            max_size=100,
            cleanup_interval=10.0,
            name="test"
        )

    def test_get_set_basic(self, cache):
        """Test basic get and set operations"""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent(self, cache):
        """Test getting nonexistent key returns None"""
        assert cache.get("nonexistent") is None

    def test_set_with_custom_ttl(self, cache):
        """Test setting value with custom TTL"""
        cache.set("key1", "value1", ttl=0.1)
        assert cache.get("key1") == "value1"
        time.sleep(0.15)
        assert cache.get("key1") is None

    def test_delete_existing(self, cache):
        """Test deleting existing key"""
        cache.set("key1", "value1")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None

    def test_delete_nonexistent(self, cache):
        """Test deleting nonexistent key"""
        assert cache.delete("nonexistent") is False

    def test_clear(self, cache):
        """Test clearing all cache entries"""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.size == 0

    def test_get_or_set_miss(self, cache):
        """Test get_or_set on cache miss"""
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return "computed_value"

        result = cache.get_or_set("key1", factory)
        assert result == "computed_value"
        assert call_count == 1

    def test_get_or_set_hit(self, cache):
        """Test get_or_set on cache hit"""
        cache.set("key1", "cached_value")
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return "computed_value"

        result = cache.get_or_set("key1", factory)
        assert result == "cached_value"
        assert call_count == 0

    def test_exists(self, cache):
        """Test exists method"""
        cache.set("key1", "value1")
        assert cache.exists("key1") is True
        assert cache.exists("nonexistent") is False

    def test_delete_pattern(self, cache):
        """Test deleting keys by pattern"""
        cache.set("user:1:name", "Alice")
        cache.set("user:1:email", "alice@example.com")
        cache.set("user:2:name", "Bob")
        cache.set("other:key", "value")

        deleted = cache.delete_pattern("user:1:*")
        assert deleted == 2
        assert cache.get("user:1:name") is None
        assert cache.get("user:1:email") is None
        assert cache.get("user:2:name") == "Bob"
        assert cache.get("other:key") == "value"

    def test_delete_prefix(self, cache):
        """Test deleting keys by prefix"""
        cache.set("notes:list:1", [1, 2, 3])
        cache.set("notes:list:2", [4, 5, 6])
        cache.set("config:key", "value")

        deleted = cache.delete_prefix("notes:")
        assert deleted == 2
        assert cache.get("notes:list:1") is None
        assert cache.get("config:key") == "value"

    def test_get_many(self, cache):
        """Test getting multiple values"""
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        result = cache.get_many(["key1", "key2", "key3"])
        assert result["key1"] == "value1"
        assert result["key2"] == "value2"
        assert result["key3"] is None

    def test_set_many(self, cache):
        """Test setting multiple values"""
        cache.set_many({
            "key1": "value1",
            "key2": "value2",
            "key3": "value3"
        })

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

    def test_size_property(self, cache):
        """Test size property"""
        assert cache.size == 0
        cache.set("key1", "value1")
        assert cache.size == 1
        cache.set("key2", "value2")
        assert cache.size == 2

    def test_stats(self, cache):
        """Test statistics"""
        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("key2")  # miss

        stats = cache.stats()
        assert stats["name"] == "test"
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_max_size_eviction(self):
        """Test LRU eviction when max size reached"""
        cache = UnifiedCache(default_ttl=60.0, max_size=3, name="small")

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key1 to make it recently used
        cache.get("key1")

        # Add key4, should evict least recently used (key2 or key3)
        cache.set("key4", "value4")

        assert cache.size == 3
        assert cache.get("key1") == "value1"  # Should still exist
        assert cache.get("key4") == "value4"  # Should exist


class TestCacheEventListener:
    """Tests for cache event listeners"""

    def test_listener_on_set(self):
        """Test listener receives set events"""
        cache = UnifiedCache(name="listener_test")
        events = []

        class TestListener(CacheEventListener):
            def on_set(self, key, value):
                events.append(("set", key, value))

            def on_delete(self, key):
                events.append(("delete", key))

            def on_clear(self):
                events.append(("clear",))

        listener = TestListener()
        cache.add_listener(listener)

        cache.set("key1", "value1")
        assert ("set", "key1", "value1") in events

    def test_listener_on_delete(self):
        """Test listener receives delete events"""
        cache = UnifiedCache(name="listener_test")
        events = []

        class TestListener(CacheEventListener):
            def on_set(self, key, value):
                pass

            def on_delete(self, key):
                events.append(("delete", key))

            def on_clear(self):
                pass

        listener = TestListener()
        cache.add_listener(listener)

        cache.set("key1", "value1")
        cache.delete("key1")
        assert ("delete", "key1") in events

    def test_listener_on_clear(self):
        """Test listener receives clear events"""
        cache = UnifiedCache(name="listener_test")
        events = []

        class TestListener(CacheEventListener):
            def on_set(self, key, value):
                pass

            def on_delete(self, key):
                pass

            def on_clear(self):
                events.append(("clear",))

        listener = TestListener()
        cache.add_listener(listener)

        cache.clear()
        assert ("clear",) in events


class TestCachedDecorator:
    """Tests for @cached decorator"""

    def test_basic_caching(self):
        """Test basic function caching"""
        cache = UnifiedCache(name="decorator_test")
        call_count = 0

        @cached(ttl=60, cache_instance=cache)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_function(5)
        result2 = expensive_function(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count == 1  # Only called once

    def test_different_args(self):
        """Test caching with different arguments"""
        cache = UnifiedCache(name="decorator_test")
        call_count = 0

        @cached(ttl=60, cache_instance=cache)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_function(5)
        result2 = expensive_function(10)

        assert result1 == 10
        assert result2 == 20
        assert call_count == 2  # Called twice for different args

    def test_key_prefix(self):
        """Test caching with key prefix"""
        cache = UnifiedCache(name="decorator_test")

        @cached(ttl=60, key_prefix="user", cache_instance=cache)
        def get_user(user_id):
            return {"id": user_id, "name": f"User {user_id}"}

        result = get_user(1)
        assert result["id"] == 1

        # Check that key has prefix
        stats = cache.stats()
        assert stats["sets"] == 1

    def test_unless_condition(self):
        """Test unless condition prevents caching"""
        cache = UnifiedCache(name="decorator_test")

        @cached(ttl=60, cache_instance=cache, unless=lambda r: r is None)
        def maybe_get_value(key):
            if key == "missing":
                return None
            return f"value_{key}"

        result1 = maybe_get_value("exists")
        result2 = maybe_get_value("missing")

        assert result1 == "value_exists"
        assert result2 is None

        # Only "exists" should be cached
        stats = cache.stats()
        assert stats["sets"] == 1


class TestCacheInvalidateDecorator:
    """Tests for @cache_invalidate decorator"""

    def test_invalidate_prefix(self):
        """Test cache invalidation by prefix"""
        cache = UnifiedCache(name="invalidate_test")

        # Pre-populate cache
        cache.set("notes:list:1", [1, 2, 3])
        cache.set("notes:list:2", [4, 5, 6])

        @cache_invalidate(key_prefix="notes:list", cache_instance=cache)
        def create_note(data):
            return {"id": 3, **data}

        result = create_note({"title": "New Note"})
        assert result["id"] == 3

        # Cache should be invalidated
        assert cache.get("notes:list:1") is None
        assert cache.get("notes:list:2") is None


class TestNoteCacheManager:
    """Tests for NoteCacheManager"""

    @pytest.fixture
    def manager(self):
        cache = UnifiedCache(name="note_manager_test")
        return NoteCacheManager(cache=cache)

    def test_cache_note_list(self, manager):
        """Test caching note list"""
        notes = [{"id": 1, "title": "Note 1"}, {"id": 2, "title": "Note 2"}]
        manager.cache_note_list(
            user_id=1,
            source="channel",
            search=None,
            page=1,
            notes=notes
        )

        cached = manager.get_note_list(
            user_id=1,
            source="channel",
            search=None,
            page=1
        )
        assert cached == notes

    def test_cache_sources(self, manager):
        """Test caching source list"""
        sources = ["channel1", "channel2", "group1"]
        manager.cache_sources(user_id=1, sources=sources)

        cached = manager.get_sources(user_id=1)
        assert cached == sources

    def test_invalidate_user_notes(self, manager):
        """Test invalidating all notes for a user"""
        manager.cache_note_list(1, None, None, 1, [{"id": 1}])
        manager.cache_note_list(1, None, None, 2, [{"id": 2}])
        manager.cache_sources(1, ["source1"])

        deleted = manager.invalidate_user_notes(1)
        assert deleted > 0

        assert manager.get_note_list(1, None, None, 1) is None
        assert manager.get_sources(1) is None


class TestConfigCacheManager:
    """Tests for ConfigCacheManager"""

    @pytest.fixture
    def manager(self):
        cache = UnifiedCache(name="config_manager_test")
        return ConfigCacheManager(cache=cache)

    def test_cache_watch_config(self, manager):
        """Test caching watch configuration"""
        config = {"enabled": True, "sources": [1, 2, 3]}
        manager.cache_watch_config(user_id=1, config=config)

        cached = manager.get_watch_config(user_id=1)
        assert cached == config

    def test_cache_monitored_sources(self, manager):
        """Test caching monitored sources"""
        sources = [{"id": 1, "name": "Channel 1"}, {"id": 2, "name": "Channel 2"}]
        manager.cache_monitored_sources(sources=sources)

        cached = manager.get_monitored_sources()
        assert cached == sources


class TestPeerCacheManager:
    """Tests for PeerCacheManager"""

    @pytest.fixture
    def manager(self):
        cache = UnifiedCache(name="peer_manager_test")
        return PeerCacheManager(cache=cache)

    def test_cache_peer(self, manager):
        """Test caching peer information"""
        peer_info = {"id": 123, "title": "Test Channel", "type": "channel"}
        manager.cache_peer(peer_id=123, peer_type="channel", peer_info=peer_info)

        cached = manager.get_peer(peer_id=123, peer_type="channel")
        assert cached == peer_info

    def test_cache_peer_by_username(self, manager):
        """Test caching peer by username"""
        peer_info = {"id": 123, "username": "testchannel"}
        manager.cache_peer_by_username(username="TestChannel", peer_info=peer_info)

        cached = manager.get_peer_by_username(username="testchannel")
        assert cached == peer_info

    def test_mark_peer_cached(self, manager):
        """Test marking peer as cached"""
        manager.mark_peer_cached(peer_id=123)
        assert manager.is_peer_cached(peer_id=123) is True
        assert manager.is_peer_cached(peer_id=456) is False
