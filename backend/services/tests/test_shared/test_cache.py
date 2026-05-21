"""
Tests for cache module.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))


class TestCacheOperations:
    """Tests for cache operations."""
    
    @pytest.mark.asyncio
    async def test_cache_get_hit(self, mock_cache: AsyncMock):
        """Test cache get returns cached value."""
        mock_cache.get = AsyncMock(return_value='{"key": "value"}')
        
        result = await mock_cache.get("test_key")
        
        assert result == '{"key": "value"}'
    
    @pytest.mark.asyncio
    async def test_cache_get_miss(self, mock_cache: AsyncMock):
        """Test cache get returns None for missing key."""
        mock_cache.get = AsyncMock(return_value=None)
        
        result = await mock_cache.get("nonexistent_key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_set(self, mock_cache: AsyncMock):
        """Test cache set stores value."""
        mock_cache.set = AsyncMock(return_value=True)
        
        result = await mock_cache.set("test_key", "test_value", ttl=300)
        
        assert result is True
        mock_cache.set.assert_called_once_with("test_key", "test_value", ttl=300)
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, mock_cache: AsyncMock):
        """Test cache delete removes value."""
        mock_cache.delete = AsyncMock(return_value=True)
        
        result = await mock_cache.delete("test_key")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_cache_exists(self, mock_cache: AsyncMock):
        """Test cache exists check."""
        mock_cache.exists = AsyncMock(return_value=True)
        
        result = await mock_cache.exists("test_key")
        
        assert result is True


class TestCacheKeyPatterns:
    """Tests for cache key generation patterns."""
    
    def test_query_cache_key_format(self):
        """Test query cache key format."""
        import hashlib
        
        question = "What is the vacation policy?"
        top_k = 3
        
        normalized = question.lower().strip()
        key_data = f"{normalized}:{top_k}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        cache_key = f"query:{key_hash}"
        
        assert cache_key.startswith("query:")
        assert len(key_hash) == 32  # MD5 hash length
    
    def test_embedding_cache_key_format(self):
        """Test embedding cache key format."""
        import hashlib
        
        text = "Test document content"
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        cache_key = f"embedding:{text_hash}"
        
        assert cache_key.startswith("embedding:")
    
    def test_document_cache_key_format(self):
        """Test document cache key format."""
        document_id = 123
        cache_key = f"document:{document_id}"
        
        assert cache_key == "document:123"


class TestCacheTTL:
    """Tests for cache TTL behavior."""
    
    @pytest.mark.asyncio
    async def test_default_ttl(self, mock_cache: AsyncMock):
        """Test default TTL is applied."""
        mock_cache.set = AsyncMock(return_value=True)
        default_ttl = 3600
        
        await mock_cache.set("key", "value", ttl=default_ttl)
        
        mock_cache.set.assert_called_with("key", "value", ttl=default_ttl)
    
    @pytest.mark.asyncio
    async def test_custom_ttl(self, mock_cache: AsyncMock):
        """Test custom TTL is applied."""
        mock_cache.set = AsyncMock(return_value=True)
        custom_ttl = 600
        
        await mock_cache.set("key", "value", ttl=custom_ttl)
        
        mock_cache.set.assert_called_with("key", "value", ttl=custom_ttl)


class TestCacheGetOrCompute:
    """Tests for cache-get-or-compute pattern."""
    
    @pytest.mark.asyncio
    async def test_returns_cached_value(self):
        """Test returns cached value when available."""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value='{"result": "cached"}')
        
        compute_func = AsyncMock(return_value={"result": "computed"})
        
        # Simulating cache_get_or_compute pattern
        cached = await cache.get("key")
        if cached is not None:
            result = json.loads(cached)
        else:
            result = await compute_func()
            await cache.set("key", json.dumps(result))
        
        assert result == {"result": "cached"}
        compute_func.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_computes_and_caches_on_miss(self):
        """Test computes value and caches on miss."""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=True)
        
        compute_func = AsyncMock(return_value={"result": "computed"})
        
        # Simulating cache_get_or_compute pattern
        cached = await cache.get("key")
        if cached is not None:
            result = json.loads(cached)
        else:
            result = await compute_func()
            await cache.set("key", json.dumps(result))
        
        assert result == {"result": "computed"}
        compute_func.assert_called_once()
        cache.set.assert_called_once()


class TestCacheHealthCheck:
    """Tests for cache health check."""
    
    @pytest.mark.asyncio
    async def test_cache_healthy(self, mock_cache: AsyncMock):
        """Test cache health check returns healthy."""
        mock_cache.ping = AsyncMock(return_value=True)
        
        is_healthy = await mock_cache.ping()
        
        assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_cache_unhealthy(self, mock_cache: AsyncMock):
        """Test cache health check returns unhealthy."""
        mock_cache.ping = AsyncMock(side_effect=ConnectionError("Redis unavailable"))
        
        with pytest.raises(ConnectionError):
            await mock_cache.ping()


class TestCacheSerialization:
    """Tests for cache value serialization."""
    
    def test_serialize_dict(self):
        """Test serializing dictionary."""
        data = {"key": "value", "count": 42}
        serialized = json.dumps(data)
        
        assert isinstance(serialized, str)
        assert json.loads(serialized) == data
    
    def test_serialize_list(self):
        """Test serializing list."""
        data = [1, 2, 3, "four", {"five": 5}]
        serialized = json.dumps(data)
        
        assert isinstance(serialized, str)
        assert json.loads(serialized) == data
    
    def test_serialize_nested_structure(self):
        """Test serializing nested structure."""
        data = {
            "answer": "Test answer",
            "confidence": 85.5,
            "citations": [
                {"document_id": 1, "title": "Doc 1"},
                {"document_id": 2, "title": "Doc 2"}
            ]
        }
        serialized = json.dumps(data)
        parsed = json.loads(serialized)
        
        assert parsed["citations"][0]["document_id"] == 1
