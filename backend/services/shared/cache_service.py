"""
Production-grade distributed cache service for DriftGuard
Supports Redis cluster, Sentinel, and standalone modes
"""
import os
import json
import hashlib
import asyncio
import time
import zlib
from typing import Optional, Any, TypeVar, Callable, Dict, List
from dataclasses import dataclass
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheConfig:
    """Cache configuration"""
    default_ttl: int = 300  # 5 minutes
    max_ttl: int = 86400  # 24 hours
    compression_threshold: int = 1024  # Compress values > 1KB
    local_cache_size: int = 1000
    local_cache_ttl: int = 60  # 1 minute
    serializer: str = "json"  # json or pickle


class LocalCache:
    """
    L1 in-memory cache for reducing Redis calls
    Uses LRU eviction
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 60):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, tuple] = {}  # key -> (value, expire_at)
        self._access_order: List[str] = []
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from local cache"""
        if key not in self._cache:
            return None
        
        value, expire_at = self._cache[key]
        
        if time.time() > expire_at:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return None
        
        # Update access order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in local cache"""
        ttl = ttl or self.default_ttl
        expire_at = time.time() + ttl
        
        # Evict if at capacity
        while len(self._cache) >= self.max_size:
            if self._access_order:
                oldest = self._access_order.pop(0)
                self._cache.pop(oldest, None)
            else:
                break
        
        self._cache[key] = (value, expire_at)
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
    
    def delete(self, key: str):
        """Delete from local cache"""
        self._cache.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)
    
    def clear(self):
        """Clear all entries"""
        self._cache.clear()
        self._access_order.clear()
    
    def cleanup_expired(self):
        """Remove expired entries"""
        now = time.time()
        expired = [
            key for key, (_, expire_at) in self._cache.items()
            if expire_at < now
        ]
        for key in expired:
            self.delete(key)


class CacheService:
    """
    Production cache service with:
    - Redis cluster support
    - Sentinel for HA
    - Local cache (L1)
    - Compression for large values
    - Cache-aside pattern
    - Metrics
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        cluster_mode: bool = False,
        sentinel_mode: bool = False,
        sentinel_master: str = "mymaster",
        config: Optional[CacheConfig] = None,
    ):
        self.redis_url = redis_url or os.environ.get('REDIS_URL', 'redis://localhost:6379')
        self.cluster_mode = cluster_mode or os.environ.get('REDIS_CLUSTER', 'false').lower() == 'true'
        self.sentinel_mode = sentinel_mode
        self.sentinel_master = sentinel_master
        self.config = config or CacheConfig()
        
        self._client = None
        self._local_cache = LocalCache(
            max_size=self.config.local_cache_size,
            default_ttl=self.config.local_cache_ttl,
        )
        self._is_connected = False
        
        # Metrics
        self._hits = 0
        self._misses = 0
        self._errors = 0
    
    async def connect(self):
        """Initialize Redis connection"""
        if self._is_connected:
            return
        
        try:
            import redis.asyncio as redis
            
            if self.cluster_mode:
                from redis.asyncio.cluster import RedisCluster
                self._client = RedisCluster.from_url(
                    self.redis_url,
                    decode_responses=True,
                )
            elif self.sentinel_mode:
                from redis.asyncio.sentinel import Sentinel
                sentinel = Sentinel.from_url(self.redis_url)
                self._client = sentinel.master_for(
                    self.sentinel_master,
                    decode_responses=True,
                )
            else:
                self._client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                )
            
            # Test connection
            await self._client.ping()
            self._is_connected = True
            logger.info(f"Redis cache connected (cluster={self.cluster_mode})")
            
        except ImportError:
            logger.warning("redis package not installed, using local cache only")
            self._is_connected = False
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._is_connected = False
    
    async def disconnect(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None
        self._is_connected = False
        self._local_cache.clear()
    
    def _serialize(self, value: Any) -> str:
        """Serialize value for storage"""
        data = json.dumps(value, default=str)
        
        if len(data) > self.config.compression_threshold:
            compressed = zlib.compress(data.encode())
            return f"__z__:{compressed.hex()}"
        
        return data
    
    def _deserialize(self, data: str) -> Any:
        """Deserialize stored value"""
        if data is None:
            return None
            
        if data.startswith("__z__:"):
            hex_data = data[6:]
            decompressed = zlib.decompress(bytes.fromhex(hex_data))
            return json.loads(decompressed)
        
        return json.loads(data)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (local first, then Redis)"""
        # Check local cache (L1)
        value = self._local_cache.get(key)
        if value is not None:
            self._hits += 1
            return value
        
        # Check Redis (L2)
        if self._client:
            try:
                data = await self._client.get(key)
                if data is not None:
                    value = self._deserialize(data)
                    # Populate local cache
                    self._local_cache.set(key, value)
                    self._hits += 1
                    return value
            except Exception as e:
                logger.warning(f"Redis get error: {e}")
                self._errors += 1
        
        self._misses += 1
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ):
        """Set value in cache"""
        ttl = min(ttl or self.config.default_ttl, self.config.max_ttl)
        
        # Set local cache
        self._local_cache.set(key, value, min(ttl, self.config.local_cache_ttl))
        
        # Set Redis
        if self._client:
            try:
                data = self._serialize(value)
                await self._client.setex(key, ttl, data)
            except Exception as e:
                logger.warning(f"Redis set error: {e}")
                self._errors += 1
    
    async def delete(self, key: str):
        """Delete from cache"""
        self._local_cache.delete(key)
        
        if self._client:
            try:
                await self._client.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete error: {e}")
                self._errors += 1
    
    async def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        # Clear local cache
        import re
        regex = re.compile(pattern.replace('*', '.*'))
        keys_to_delete = [
            k for k in list(self._local_cache._cache.keys())
            if regex.match(k)
        ]
        for k in keys_to_delete:
            self._local_cache.delete(k)
        
        # Clear Redis
        if self._client:
            try:
                if self.cluster_mode:
                    cursor = 0
                    while True:
                        cursor, keys = await self._client.scan(
                            cursor=cursor,
                            match=pattern,
                            count=100,
                        )
                        if keys:
                            await self._client.delete(*keys)
                        if cursor == 0:
                            break
                else:
                    keys = await self._client.keys(pattern)
                    if keys:
                        await self._client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis pattern delete error: {e}")
                self._errors += 1
    
    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None,
    ) -> Any:
        """Cache-aside pattern: get from cache or compute and store"""
        value = await self.get(key)
        if value is not None:
            return value
        
        # Compute value
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()
        
        await self.set(key, value, ttl)
        return value
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment counter"""
        if self._client:
            try:
                return await self._client.incrby(key, amount)
            except Exception as e:
                logger.warning(f"Redis incr error: {e}")
                self._errors += 1
        return 0
    
    async def expire(self, key: str, ttl: int):
        """Set expiration on key"""
        if self._client:
            try:
                await self._client.expire(key, ttl)
            except Exception as e:
                logger.warning(f"Redis expire error: {e}")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if self._local_cache.get(key) is not None:
            return True
        
        if self._client:
            try:
                return await self._client.exists(key) > 0
            except Exception as e:
                logger.warning(f"Redis exists error: {e}")
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "errors": self._errors,
            "hit_rate": f"{hit_rate:.2f}%",
            "local_cache_size": len(self._local_cache._cache),
            "is_connected": self._is_connected,
            "cluster_mode": self.cluster_mode,
        }
    
    # Convenience methods for common cache keys
    
    @staticmethod
    def hash_key(*args, **kwargs) -> str:
        """Generate cache key from arguments"""
        content = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def cache_search(
        self,
        user_id: str,
        query: str,
        result: Dict[str, Any],
        ttl: int = 600,
    ):
        """Cache search result"""
        key = f"search:{user_id}:{self.hash_key(query)}"
        await self.set(key, result, ttl)
    
    async def get_cached_search(
        self,
        user_id: str,
        query: str,
    ) -> Optional[Dict[str, Any]]:
        """Get cached search result"""
        key = f"search:{user_id}:{self.hash_key(query)}"
        return await self.get(key)
    
    async def cache_document_list(
        self,
        user_id: str,
        documents: List[Dict[str, Any]],
        ttl: int = 300,
    ):
        """Cache document list"""
        key = f"docs:{user_id}:list"
        await self.set(key, documents, ttl)
    
    async def get_cached_documents(
        self,
        user_id: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached documents"""
        key = f"docs:{user_id}:list"
        return await self.get(key)
    
    async def invalidate_user_cache(self, user_id: str):
        """Invalidate all cache for user"""
        await self.delete_pattern(f"*:{user_id}:*")
    
    async def invalidate_document_cache(self, document_id: str):
        """Invalidate document-related cache"""
        await self.delete_pattern(f"*:doc:{document_id}*")


def cached(
    ttl: int = 300,
    key_prefix: str = "",
    key_builder: Optional[Callable] = None,
):
    """Decorator for caching function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = await get_cache_service()
            
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = f"{key_prefix}:{func.__name__}:{CacheService.hash_key(*args, **kwargs)}"
            
            # Try cache
            result = await cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# Global instance
_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """Get global cache service instance"""
    global _cache_service
    
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.connect()
    
    return _cache_service


async def close_cache_service():
    """Close global cache service"""
    global _cache_service
    
    if _cache_service:
        await _cache_service.disconnect()
        _cache_service = None
