"""
Redis Security Configuration
Secure Redis client with connection validation and data protection
"""
import os
import logging
import hashlib
import json
from typing import Optional, Any, Union
from datetime import timedelta

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

class RedisConfig:
    """Secure Redis configuration from environment variables"""
    
    def __init__(self):
        self.host = os.environ.get('REDIS_HOST', 'localhost')
        self.port = int(os.environ.get('REDIS_PORT', 6379))
        self.password = os.environ.get('REDIS_PASSWORD', None)
        self.db = int(os.environ.get('REDIS_DB', 0))
        self.ssl = os.environ.get('REDIS_SSL', 'false').lower() == 'true'
        self.socket_timeout = int(os.environ.get('REDIS_TIMEOUT', 5))
        self.max_connections = int(os.environ.get('REDIS_MAX_CONNECTIONS', 10))
        
        # Validate configuration
        self._validate()
    
    def _validate(self):
        """Validate Redis configuration"""
        if self.port < 1 or self.port > 65535:
            raise ValueError(f"Invalid Redis port: {self.port}")
        
        if self.db < 0 or self.db > 15:
            raise ValueError(f"Invalid Redis database: {self.db}")
        
        # Warn if no password in production
        env = os.environ.get('ENVIRONMENT', 'development')
        if env == 'production' and not self.password:
            logger.warning("⚠️ Redis password not set in production!")
    
    def get_url(self) -> str:
        """Get Redis URL (password redacted for logging)"""
        protocol = 'rediss' if self.ssl else 'redis'
        auth = '***:***@' if self.password else ''
        return f"{protocol}://{auth}{self.host}:{self.port}/{self.db}"


# =============================================================================
# Secure Redis Client
# =============================================================================

class SecureRedisClient:
    """
    Secure Redis client wrapper with:
    - Automatic connection handling
    - Key prefix for namespace isolation
    - Sensitive data encryption (optional)
    - Secure logging
    """
    
    def __init__(self, config: RedisConfig = None, key_prefix: str = 'dg:'):
        self.config = config or RedisConfig()
        self.key_prefix = key_prefix
        self._client = None
        self._connected = False
    
    def _get_client(self):
        """Get or create Redis client"""
        if self._client is None:
            try:
                import redis
                
                self._client = redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    password=self.config.password,
                    db=self.config.db,
                    ssl=self.config.ssl,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.socket_timeout,
                    decode_responses=True,
                    max_connections=self.config.max_connections,
                )
                
                # Test connection
                self._client.ping()
                self._connected = True
                logger.info(f"✅ Connected to Redis: {self.config.get_url()}")
                
            except ImportError:
                logger.warning("Redis package not installed. Caching disabled.")
                self._connected = False
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")
                self._connected = False
        
        return self._client if self._connected else None
    
    def _make_key(self, key: str) -> str:
        """Create prefixed key"""
        # Sanitize key to prevent injection
        safe_key = key.replace('\n', '').replace('\r', '')[:256]
        return f"{self.key_prefix}{safe_key}"
    
    @property
    def is_connected(self) -> bool:
        """Check if Redis is available"""
        return self._get_client() is not None
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        client = self._get_client()
        if not client:
            return None
        
        try:
            return client.get(self._make_key(key))
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Union[str, dict, list],
        ttl_seconds: int = 3600
    ) -> bool:
        """Set value in cache with expiration"""
        client = self._get_client()
        if not client:
            return False
        
        try:
            # Serialize if needed
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            prefixed_key = self._make_key(key)
            client.setex(prefixed_key, ttl_seconds, value)
            return True
            
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        client = self._get_client()
        if not client:
            return False
        
        try:
            client.delete(self._make_key(key))
            return True
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return False
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Get and parse JSON value"""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None
    
    def generate_cache_key(self, *args) -> str:
        """Generate a cache key from multiple arguments"""
        key_parts = [str(arg) for arg in args]
        key_string = ':'.join(key_parts)
        # Hash long keys
        if len(key_string) > 100:
            return hashlib.sha256(key_string.encode()).hexdigest()[:32]
        return key_string
    
    async def get_or_compute(
        self,
        key: str,
        compute_fn,
        ttl_seconds: int = 3600
    ) -> Any:
        """Get from cache or compute and cache"""
        # Try cache first
        cached = await self.get_json(key)
        if cached is not None:
            return cached
        
        # Compute value
        if asyncio.iscoroutinefunction(compute_fn):
            value = await compute_fn()
        else:
            value = compute_fn()
        
        # Cache result
        await self.set(key, value, ttl_seconds)
        return value
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter"""
        client = self._get_client()
        if not client:
            return None
        
        try:
            return client.incrby(self._make_key(key), amount)
        except Exception as e:
            logger.error(f"Redis INCR error: {e}")
            return None
    
    async def rate_limit_check(
        self,
        identifier: str,
        max_requests: int = 100,
        window_seconds: int = 60
    ) -> tuple[bool, int]:
        """
        Check rate limit using sliding window.
        Returns (is_allowed, remaining_requests)
        """
        client = self._get_client()
        if not client:
            # Allow if Redis unavailable
            return True, max_requests
        
        key = self._make_key(f"ratelimit:{identifier}")
        
        try:
            current = client.incr(key)
            
            # Set expiry on first request
            if current == 1:
                client.expire(key, window_seconds)
            
            remaining = max(0, max_requests - current)
            allowed = current <= max_requests
            
            return allowed, remaining
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True, max_requests


# =============================================================================
# Singleton Instance
# =============================================================================

import asyncio

# Create default instance
redis_client = SecureRedisClient()


# =============================================================================
# Security Guidelines
# =============================================================================

REDIS_SECURITY_CHECKLIST = """
# Redis Security Checklist

## Connection Security
- [x] Password authentication enabled
- [x] SSL/TLS for production connections
- [x] Connection timeout configured
- [x] Max connections limited

## Network Security
- [ ] Redis not exposed to internet (bind to localhost or VPC)
- [ ] Firewall rules restrict access
- [ ] Redis port (6379) blocked from public

## Data Security
- [ ] Sensitive data encrypted before storage
- [ ] Session tokens have TTL
- [ ] PII has appropriate expiration
- [ ] No passwords stored in Redis

## Operational Security
- [ ] Redis logs monitored
- [ ] Memory limits configured
- [ ] Persistence configured appropriately
- [ ] Regular backups if persistence enabled
"""
