"""Caching layer using Redis"""
import os
import json
import logging
from typing import Optional, Any, TypeVar
import redis
from redis.connection import ConnectionPool

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheManager:
    """Redis-based caching with TTL support"""
    
    _instance: Optional['CacheManager'] = None
    _redis: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._redis is None:
            self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            redis_host = os.getenv("REDIS_HOST", "redis")
            redis_port = int(os.getenv("REDIS_PORT", 6379))
            
            self._redis = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=0,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                retry_on_timeout=True
            )
            
            # Test connection
            self._redis.ping()
            logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.warning("Cache will be disabled (Redis not available)")
            self._redis = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._redis:
            return None
        
        try:
            value = self._redis.get(key)
            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 3600
    ) -> bool:
        """Set value in cache with TTL"""
        if not self._redis:
            return False
        
        try:
            self._redis.setex(
                key,
                ttl_seconds,
                json.dumps(value)
            )
            logger.debug(f"Cache SET: {key} (TTL: {ttl_seconds}s)")
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self._redis:
            return False
        
        try:
            self._redis.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting from cache: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        if not self._redis:
            return 0
        
        try:
            cursor = 0
            count = 0
            while True:
                cursor, keys = self._redis.scan(cursor, match=pattern)
                if keys:
                    count += self._redis.delete(*keys)
                if cursor == 0:
                    break
            logger.debug(f"Cache cleared {count} keys matching {pattern}")
            return count
        except Exception as e:
            logger.error(f"Error clearing cache pattern: {e}")
            return 0
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self._redis is not None
    
    async def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self._redis:
            return {"available": False}
        
        try:
            info = self._redis.info()
            return {
                "available": True,
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands": info.get("total_commands_processed")
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"available": False}


# Singleton instance
cache = CacheManager()


async def cache_get_or_compute(
    key: str,
    compute_fn,
    ttl_seconds: int = 3600,
    *args,
    **kwargs
) -> Any:
    """
    Get value from cache or compute and cache it
    
    Args:
        key: Cache key
        compute_fn: Async function to compute value if not cached
        ttl_seconds: Time to live in seconds
    """
    # Try to get from cache
    cached = await cache.get(key)
    if cached is not None:
        return cached
    
    # Compute value
    value = await compute_fn(*args, **kwargs)
    
    # Cache it
    await cache.set(key, value, ttl_seconds)
    
    return value
