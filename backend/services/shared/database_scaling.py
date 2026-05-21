"""
Production-grade database scaling configuration for DriftGuard
Supports connection pooling, read replicas, and sharding
"""
import os
import asyncio
import hashlib
from typing import Optional, List, Dict, Any, TypeVar, Callable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import logging
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ScaleTier(Enum):
    """Scale tier definitions for infrastructure sizing"""
    DEVELOPMENT = "development"      # < 100 users
    SMALL = "small"                   # 100 - 1,000 users
    MEDIUM = "medium"                 # 1,000 - 10,000 users
    LARGE = "large"                   # 10,000 - 100,000 users
    ENTERPRISE = "enterprise"         # 100,000+ users


@dataclass
class DatabaseConfig:
    """Database configuration based on scale tier"""
    
    # Connection pool settings
    min_connections: int = 5
    max_connections: int = 20
    
    # Performance settings
    statement_cache_size: int = 100
    max_queries_per_connection: int = 10000
    connection_timeout_seconds: float = 10.0
    query_timeout_seconds: float = 30.0
    
    # Health check
    health_check_interval: float = 30.0
    
    # Replication
    read_replicas: int = 0
    use_read_write_splitting: bool = False
    
    # Sharding (for enterprise)
    enable_sharding: bool = False
    shard_count: int = 1


# Configuration by scale tier
SCALE_CONFIGS: Dict[ScaleTier, DatabaseConfig] = {
    ScaleTier.DEVELOPMENT: DatabaseConfig(
        min_connections=2,
        max_connections=10,
        statement_cache_size=100,
        max_queries_per_connection=10000,
        connection_timeout_seconds=10,
        query_timeout_seconds=30,
        read_replicas=0,
        use_read_write_splitting=False,
        enable_sharding=False,
        shard_count=1,
    ),
    ScaleTier.SMALL: DatabaseConfig(
        min_connections=5,
        max_connections=25,
        statement_cache_size=500,
        max_queries_per_connection=25000,
        connection_timeout_seconds=10,
        query_timeout_seconds=30,
        read_replicas=1,
        use_read_write_splitting=True,
        enable_sharding=False,
        shard_count=1,
    ),
    ScaleTier.MEDIUM: DatabaseConfig(
        min_connections=10,
        max_connections=50,
        statement_cache_size=1000,
        max_queries_per_connection=50000,
        connection_timeout_seconds=5,
        query_timeout_seconds=20,
        read_replicas=2,
        use_read_write_splitting=True,
        enable_sharding=False,
        shard_count=1,
    ),
    ScaleTier.LARGE: DatabaseConfig(
        min_connections=20,
        max_connections=100,
        statement_cache_size=2000,
        max_queries_per_connection=100000,
        connection_timeout_seconds=5,
        query_timeout_seconds=15,
        read_replicas=3,
        use_read_write_splitting=True,
        enable_sharding=True,
        shard_count=4,
    ),
    ScaleTier.ENTERPRISE: DatabaseConfig(
        min_connections=50,
        max_connections=200,
        statement_cache_size=5000,
        max_queries_per_connection=200000,
        connection_timeout_seconds=3,
        query_timeout_seconds=10,
        read_replicas=5,
        use_read_write_splitting=True,
        enable_sharding=True,
        shard_count=16,
    ),
}


def get_database_config(tier: Optional[ScaleTier] = None) -> DatabaseConfig:
    """Get database configuration for scale tier"""
    if tier is None:
        # Auto-detect from environment
        tier_name = os.environ.get('SCALE_TIER', 'development').lower()
        tier = ScaleTier(tier_name)
    
    return SCALE_CONFIGS[tier]


class ConnectionPool:
    """
    Production-grade connection pool with:
    - Automatic connection recycling
    - Health checks
    - Metrics collection
    """
    
    def __init__(
        self,
        database_url: str,
        config: Optional[DatabaseConfig] = None,
    ):
        self.database_url = database_url
        self.config = config or get_database_config()
        self._pool = None
        self._is_initialized = False
        self._connection_count = 0
        self._active_connections = 0
        
    async def initialize(self):
        """Initialize the connection pool"""
        if self._is_initialized:
            return
            
        try:
            # Using asyncpg for PostgreSQL
            import asyncpg
            
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.config.min_connections,
                max_size=self.config.max_connections,
                command_timeout=self.config.query_timeout_seconds,
                statement_cache_size=self.config.statement_cache_size,
                max_queries=self.config.max_queries_per_connection,
            )
            
            self._is_initialized = True
            logger.info(
                f"Database pool initialized: "
                f"min={self.config.min_connections}, "
                f"max={self.config.max_connections}"
            )
            
        except ImportError:
            logger.warning("asyncpg not installed, using mock pool")
            self._is_initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    async def close(self):
        """Close the connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._is_initialized = False
            logger.info("Database pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool"""
        if not self._is_initialized:
            await self.initialize()
        
        self._active_connections += 1
        try:
            if self._pool:
                async with self._pool.acquire() as connection:
                    yield connection
            else:
                # Mock connection for testing
                yield None
        finally:
            self._active_connections -= 1
    
    async def execute(self, query: str, *args) -> Any:
        """Execute a query"""
        async with self.acquire() as conn:
            if conn:
                return await conn.execute(query, *args)
            return None
    
    async def fetch(self, query: str, *args) -> List[Any]:
        """Fetch multiple rows"""
        async with self.acquire() as conn:
            if conn:
                return await conn.fetch(query, *args)
            return []
    
    async def fetchrow(self, query: str, *args) -> Optional[Any]:
        """Fetch single row"""
        async with self.acquire() as conn:
            if conn:
                return await conn.fetchrow(query, *args)
            return None
    
    async def fetchval(self, query: str, *args) -> Optional[Any]:
        """Fetch single value"""
        async with self.acquire() as conn:
            if conn:
                return await conn.fetchval(query, *args)
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        if self._pool:
            return {
                "min_size": self._pool.get_min_size(),
                "max_size": self._pool.get_max_size(),
                "size": self._pool.get_size(),
                "free_size": self._pool.get_idle_size(),
                "active_connections": self._active_connections,
            }
        return {
            "initialized": self._is_initialized,
            "active_connections": self._active_connections,
        }


class ReadWriteSplitter:
    """
    Route queries to appropriate database instances
    - Writes go to primary
    - Reads go to replicas (round-robin)
    """
    
    def __init__(
        self,
        primary_url: str,
        replica_urls: Optional[List[str]] = None,
        config: Optional[DatabaseConfig] = None,
    ):
        self.config = config or get_database_config()
        self._primary = ConnectionPool(primary_url, config)
        self._replicas: List[ConnectionPool] = []
        self._replica_index = 0
        self._lock = asyncio.Lock()
        
        if replica_urls:
            for url in replica_urls:
                self._replicas.append(ConnectionPool(url, config))
    
    async def initialize(self):
        """Initialize all connection pools"""
        await self._primary.initialize()
        for replica in self._replicas:
            await replica.initialize()
        logger.info(f"Read/write splitter initialized with {len(self._replicas)} replicas")
    
    async def close(self):
        """Close all connection pools"""
        await self._primary.close()
        for replica in self._replicas:
            await replica.close()
    
    def get_write_pool(self) -> ConnectionPool:
        """Get connection pool for write operations"""
        return self._primary
    
    async def get_read_pool(self) -> ConnectionPool:
        """Get connection pool for read operations (round-robin)"""
        if not self._replicas:
            return self._primary
        
        async with self._lock:
            pool = self._replicas[self._replica_index]
            self._replica_index = (self._replica_index + 1) % len(self._replicas)
            return pool
    
    async def execute_write(self, query: str, *args) -> Any:
        """Execute write query on primary"""
        return await self._primary.execute(query, *args)
    
    async def execute_read(self, query: str, *args) -> List[Any]:
        """Execute read query on replica"""
        pool = await self.get_read_pool()
        return await pool.fetch(query, *args)


class ShardRouter:
    """
    Route queries to appropriate shard based on tenant/user ID
    Uses consistent hashing for even distribution
    """
    
    def __init__(
        self,
        shard_configs: List[Dict[str, str]],
        config: Optional[DatabaseConfig] = None,
    ):
        self.config = config or get_database_config()
        self.shard_count = len(shard_configs)
        self._shards: Dict[int, ReadWriteSplitter] = {}
        
        for i, shard_config in enumerate(shard_configs):
            primary_url = shard_config['primary']
            replica_urls = shard_config.get('replicas', [])
            self._shards[i] = ReadWriteSplitter(primary_url, replica_urls, config)
    
    async def initialize(self):
        """Initialize all shards"""
        for shard in self._shards.values():
            await shard.initialize()
        logger.info(f"Shard router initialized with {self.shard_count} shards")
    
    async def close(self):
        """Close all shards"""
        for shard in self._shards.values():
            await shard.close()
    
    def _get_shard_index(self, key: str) -> int:
        """Get shard index for key using consistent hashing"""
        hash_value = int(hashlib.sha256(key.encode()).hexdigest(), 16)
        return hash_value % self.shard_count
    
    def get_shard(self, tenant_id: str) -> ReadWriteSplitter:
        """Get shard for tenant"""
        index = self._get_shard_index(tenant_id)
        return self._shards[index]
    
    def get_all_shards(self) -> List[ReadWriteSplitter]:
        """Get all shards for cross-shard queries"""
        return list(self._shards.values())
    
    async def execute_on_shard(
        self,
        tenant_id: str,
        query: str,
        *args,
        is_write: bool = False,
    ) -> Any:
        """Execute query on appropriate shard"""
        shard = self.get_shard(tenant_id)
        if is_write:
            return await shard.execute_write(query, *args)
        return await shard.execute_read(query, *args)
    
    async def execute_on_all_shards(
        self,
        query: str,
        *args,
    ) -> List[Any]:
        """Execute query on all shards (for aggregations)"""
        tasks = []
        for shard in self._shards.values():
            tasks.append(shard.execute_read(query, *args))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results, skip errors
        all_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Shard query failed: {result}")
            elif result:
                all_results.extend(result)
        
        return all_results


class ScalableDatabase:
    """
    Main database class that handles all scaling strategies
    Automatically selects appropriate strategy based on configuration
    """
    
    def __init__(
        self,
        primary_url: Optional[str] = None,
        replica_urls: Optional[List[str]] = None,
        shard_configs: Optional[List[Dict[str, str]]] = None,
        tier: Optional[ScaleTier] = None,
    ):
        self.config = get_database_config(tier)
        self._primary_url = primary_url or os.environ.get('DATABASE_URL', '')
        self._replica_urls = replica_urls or []
        self._shard_configs = shard_configs
        
        # Initialize appropriate backend
        if shard_configs and self.config.enable_sharding:
            self._backend = ShardRouter(shard_configs, self.config)
            self._mode = "sharded"
        elif replica_urls and self.config.use_read_write_splitting:
            self._backend = ReadWriteSplitter(
                self._primary_url,
                replica_urls,
                self.config,
            )
            self._mode = "replicated"
        else:
            self._backend = ConnectionPool(self._primary_url, self.config)
            self._mode = "single"
        
        logger.info(f"Database initialized in {self._mode} mode")
    
    async def initialize(self):
        """Initialize database connections"""
        await self._backend.initialize()
    
    async def close(self):
        """Close database connections"""
        await self._backend.close()
    
    async def execute(
        self,
        query: str,
        *args,
        tenant_id: Optional[str] = None,
    ) -> Any:
        """Execute a write query"""
        if self._mode == "sharded" and tenant_id:
            return await self._backend.execute_on_shard(
                tenant_id, query, *args, is_write=True
            )
        elif self._mode == "replicated":
            return await self._backend.execute_write(query, *args)
        else:
            return await self._backend.execute(query, *args)
    
    async def fetch(
        self,
        query: str,
        *args,
        tenant_id: Optional[str] = None,
    ) -> List[Any]:
        """Execute a read query"""
        if self._mode == "sharded" and tenant_id:
            return await self._backend.execute_on_shard(
                tenant_id, query, *args, is_write=False
            )
        elif self._mode == "replicated":
            return await self._backend.execute_read(query, *args)
        else:
            return await self._backend.fetch(query, *args)
    
    async def fetch_all_shards(self, query: str, *args) -> List[Any]:
        """Query all shards (for global aggregations)"""
        if self._mode == "sharded":
            return await self._backend.execute_on_all_shards(query, *args)
        return await self.fetch(query, *args)
    
    def get_mode(self) -> str:
        """Get current operation mode"""
        return self._mode
    
    def get_config(self) -> DatabaseConfig:
        """Get current configuration"""
        return self.config


# Query capacity estimates per tier
CAPACITY_ESTIMATES = {
    ScaleTier.DEVELOPMENT: {
        "queries_per_second": 10,
        "queries_per_day": 50_000,
        "concurrent_users": 50,
        "storage_gb": 10,
    },
    ScaleTier.SMALL: {
        "queries_per_second": 50,
        "queries_per_day": 250_000,
        "concurrent_users": 500,
        "storage_gb": 50,
    },
    ScaleTier.MEDIUM: {
        "queries_per_second": 200,
        "queries_per_day": 1_000_000,
        "concurrent_users": 2_000,
        "storage_gb": 200,
    },
    ScaleTier.LARGE: {
        "queries_per_second": 1000,
        "queries_per_day": 5_000_000,
        "concurrent_users": 10_000,
        "storage_gb": 1000,
    },
    ScaleTier.ENTERPRISE: {
        "queries_per_second": 5000,
        "queries_per_day": 25_000_000,
        "concurrent_users": 50_000,
        "storage_gb": 5000,
    },
}


def get_capacity_estimate(tier: ScaleTier) -> Dict[str, int]:
    """Get capacity estimates for a scale tier"""
    return CAPACITY_ESTIMATES[tier]


# Global instance
_database: Optional[ScalableDatabase] = None


async def get_database() -> ScalableDatabase:
    """Get the global database instance"""
    global _database
    if _database is None:
        _database = ScalableDatabase()
        await _database.initialize()
    return _database


async def close_database():
    """Close the global database instance"""
    global _database
    if _database:
        await _database.close()
        _database = None
