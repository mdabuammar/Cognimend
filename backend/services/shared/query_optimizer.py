"""
Query Optimizer
Provides query analysis, caching, and optimization hints
"""

import hashlib
import json
import time
import asyncio
from typing import Any, Optional, List, Dict, Callable, TypeVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class QueryStats:
    """Statistics for a query pattern"""
    query_hash: str
    query_template: str
    call_count: int = 0
    total_time_ms: float = 0
    avg_time_ms: float = 0
    max_time_ms: float = 0
    min_time_ms: float = float('inf')
    last_called: Optional[datetime] = None
    cache_hits: int = 0
    cache_misses: int = 0
    
    def update(self, execution_time_ms: float) -> None:
        self.call_count += 1
        self.total_time_ms += execution_time_ms
        self.avg_time_ms = self.total_time_ms / self.call_count
        self.max_time_ms = max(self.max_time_ms, execution_time_ms)
        self.min_time_ms = min(self.min_time_ms, execution_time_ms)
        self.last_called = datetime.utcnow()


@dataclass
class CacheEntry:
    """Cache entry with TTL"""
    data: Any
    created_at: datetime
    ttl_seconds: int
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    @property
    def is_expired(self) -> bool:
        age = datetime.utcnow() - self.created_at
        return age.total_seconds() > self.ttl_seconds
    
    def access(self) -> Any:
        self.access_count += 1
        self.last_accessed = datetime.utcnow()
        return self.data


class QueryCache:
    """In-memory query result cache with LRU eviction"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
    
    def _generate_key(self, query: str, params: tuple) -> str:
        """Generate cache key from query and params"""
        content = f"{query}:{json.dumps(params, default=str, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def get(self, query: str, params: tuple = ()) -> Optional[Any]:
        """Get cached result"""
        key = self._generate_key(query, params)
        
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                return None
                
            if entry.is_expired:
                del self._cache[key]
                return None
                
            return entry.access()
    
    async def set(
        self, 
        query: str, 
        params: tuple, 
        data: Any, 
        ttl: Optional[int] = None
    ) -> None:
        """Cache query result"""
        key = self._generate_key(query, params)
        
        async with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self.max_size:
                await self._evict_lru()
            
            self._cache[key] = CacheEntry(
                data=data,
                created_at=datetime.utcnow(),
                ttl_seconds=ttl or self.default_ttl,
            )
    
    async def invalidate(self, pattern: Optional[str] = None) -> int:
        """Invalidate cache entries"""
        async with self._lock:
            if pattern is None:
                count = len(self._cache)
                self._cache.clear()
                return count
            
            # Pattern-based invalidation
            to_remove = [
                key for key in self._cache
                if pattern in key
            ]
            for key in to_remove:
                del self._cache[key]
            return len(to_remove)
    
    async def _evict_lru(self) -> None:
        """Evict least recently used entries"""
        if not self._cache:
            return
            
        # Remove expired first
        expired = [
            key for key, entry in self._cache.items()
            if entry.is_expired
        ]
        for key in expired:
            del self._cache[key]
        
        # If still over capacity, remove least accessed
        if len(self._cache) >= self.max_size:
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: (x[1].access_count, x[1].last_accessed or x[1].created_at)
            )
            # Remove bottom 10%
            to_remove = len(self._cache) - int(self.max_size * 0.9)
            for key, _ in sorted_entries[:to_remove]:
                del self._cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = len(self._cache)
        expired = sum(1 for e in self._cache.values() if e.is_expired)
        total_accesses = sum(e.access_count for e in self._cache.values())
        
        return {
            "total_entries": total,
            "expired_entries": expired,
            "total_accesses": total_accesses,
            "max_size": self.max_size,
            "utilization": total / self.max_size * 100 if self.max_size > 0 else 0,
        }


class QueryAnalyzer:
    """Analyze query patterns and provide optimization hints"""
    
    def __init__(self):
        self._stats: Dict[str, QueryStats] = {}
        self._lock = asyncio.Lock()
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for pattern matching"""
        import re
        # Replace literal values with placeholders
        normalized = re.sub(r"'[^']*'", "'?'", query)
        normalized = re.sub(r"\b\d+\b", "?", normalized)
        normalized = re.sub(r"\$\d+", "?", normalized)
        return normalized.strip().lower()
    
    def _generate_hash(self, query: str) -> str:
        """Generate hash for query pattern"""
        normalized = self._normalize_query(query)
        return hashlib.md5(normalized.encode()).hexdigest()[:12]
    
    async def record(self, query: str, execution_time_ms: float) -> None:
        """Record query execution"""
        query_hash = self._generate_hash(query)
        
        async with self._lock:
            if query_hash not in self._stats:
                self._stats[query_hash] = QueryStats(
                    query_hash=query_hash,
                    query_template=self._normalize_query(query),
                )
            
            self._stats[query_hash].update(execution_time_ms)
    
    async def get_slow_queries(self, threshold_ms: float = 100) -> List[QueryStats]:
        """Get queries exceeding threshold"""
        async with self._lock:
            return sorted(
                [s for s in self._stats.values() if s.avg_time_ms > threshold_ms],
                key=lambda x: x.avg_time_ms,
                reverse=True,
            )
    
    async def get_frequent_queries(self, min_calls: int = 10) -> List[QueryStats]:
        """Get frequently executed queries"""
        async with self._lock:
            return sorted(
                [s for s in self._stats.values() if s.call_count >= min_calls],
                key=lambda x: x.call_count,
                reverse=True,
            )
    
    def get_optimization_hints(self, query: str) -> List[str]:
        """Provide optimization hints for a query"""
        hints = []
        query_lower = query.lower()
        
        # Check for SELECT *
        if 'select *' in query_lower:
            hints.append("Avoid SELECT * - specify only needed columns")
        
        # Check for missing LIMIT
        if 'select' in query_lower and 'limit' not in query_lower:
            if 'count(' not in query_lower and 'exists' not in query_lower:
                hints.append("Consider adding LIMIT to prevent large result sets")
        
        # Check for LIKE with leading wildcard
        if 'like \'%' in query_lower or 'like "%' in query_lower:
            hints.append("Leading wildcards in LIKE prevent index usage")
        
        # Check for OR in WHERE clause
        if ' or ' in query_lower and 'where' in query_lower:
            hints.append("Multiple ORs can prevent index usage - consider UNION")
        
        # Check for functions on indexed columns
        if any(f in query_lower for f in ['lower(', 'upper(', 'coalesce(']):
            hints.append("Functions on columns may prevent index usage")
        
        # Check for NOT IN
        if 'not in' in query_lower:
            hints.append("NOT IN can be slow - consider LEFT JOIN / IS NULL")
        
        # Check for ORDER BY without index hint
        if 'order by' in query_lower:
            hints.append("Ensure ORDER BY columns are indexed")
        
        return hints
    
    async def get_stats_summary(self) -> Dict[str, Any]:
        """Get summary of query statistics"""
        async with self._lock:
            if not self._stats:
                return {"message": "No queries recorded"}
            
            total_queries = sum(s.call_count for s in self._stats.values())
            total_time = sum(s.total_time_ms for s in self._stats.values())
            avg_time = total_time / total_queries if total_queries > 0 else 0
            
            return {
                "unique_patterns": len(self._stats),
                "total_executions": total_queries,
                "total_time_ms": round(total_time, 2),
                "avg_time_ms": round(avg_time, 2),
                "slowest_query": max(self._stats.values(), key=lambda x: x.avg_time_ms).query_template if self._stats else None,
                "most_frequent": max(self._stats.values(), key=lambda x: x.call_count).query_template if self._stats else None,
            }


# Decorator for automatic query caching
def cached_query(ttl: int = 300, cache_instance: Optional[QueryCache] = None):
    """Decorator to cache query results"""
    cache = cache_instance or _default_cache
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [func.__name__, str(args), str(sorted(kwargs.items()))]
            cache_key = hashlib.md5(str(key_parts).encode()).hexdigest()
            
            # Check cache
            cached = await cache.get(cache_key, ())
            if cached is not None:
                return cached
            
            # Execute and cache
            result = await func(*args, **kwargs)
            await cache.set(cache_key, (), result, ttl)
            
            return result
        return wrapper
    return decorator


# Decorator for query timing
def timed_query(analyzer: Optional[QueryAnalyzer] = None):
    """Decorator to time and analyze queries"""
    _analyzer = analyzer or _default_analyzer
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                
                # Try to extract query from args/kwargs
                query = kwargs.get('query', args[0] if args else 'unknown')
                if isinstance(query, str):
                    await _analyzer.record(query, elapsed_ms)
        return wrapper
    return decorator


# Global instances
_default_cache = QueryCache()
_default_analyzer = QueryAnalyzer()


def get_query_cache() -> QueryCache:
    """Get the default query cache instance"""
    return _default_cache


def get_query_analyzer() -> QueryAnalyzer:
    """Get the default query analyzer instance"""
    return _default_analyzer
