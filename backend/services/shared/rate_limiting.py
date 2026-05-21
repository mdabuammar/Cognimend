"""
Production-grade distributed rate limiting and backpressure management
"""
import os
import time
import asyncio
import hashlib
from typing import Optional, Dict, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithms"""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_window: int
    window_seconds: int
    burst_size: Optional[int] = None
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW


@dataclass
class RateLimitResult:
    """Rate limit check result"""
    allowed: bool
    remaining: int
    reset_at: float
    retry_after: Optional[float] = None
    limit: int = 0


# Default rate limits by tier
RATE_LIMIT_TIERS = {
    "free": {
        "search": RateLimitConfig(50, 60),      # 50/min
        "upload": RateLimitConfig(10, 60),       # 10/min
        "api": RateLimitConfig(100, 60),         # 100/min
        "global": RateLimitConfig(200, 60),      # 200/min total
    },
    "pro": {
        "search": RateLimitConfig(200, 60),     # 200/min
        "upload": RateLimitConfig(50, 60),       # 50/min
        "api": RateLimitConfig(500, 60),         # 500/min
        "global": RateLimitConfig(1000, 60),     # 1000/min total
    },
    "enterprise": {
        "search": RateLimitConfig(1000, 60),    # 1000/min
        "upload": RateLimitConfig(200, 60),      # 200/min
        "api": RateLimitConfig(2000, 60),        # 2000/min
        "global": RateLimitConfig(5000, 60),     # 5000/min total
    },
}


def get_rate_limit_config(tier: str, action: str) -> RateLimitConfig:
    """Get rate limit config for tier and action"""
    tier_config = RATE_LIMIT_TIERS.get(tier, RATE_LIMIT_TIERS["free"])
    return tier_config.get(action, tier_config["api"])


class DistributedRateLimiter:
    """
    Redis-backed distributed rate limiter
    Supports sliding window algorithm for accuracy
    """
    
    # Lua script for atomic sliding window rate limiting
    SLIDING_WINDOW_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    
    -- Remove old entries outside the window
    redis.call('ZREMRANGEBYSCORE', key, 0, now - window * 1000)
    
    -- Count current requests in window
    local count = redis.call('ZCARD', key)
    
    if count < limit then
        -- Add new request with current timestamp as score and unique member
        redis.call('ZADD', key, now, now .. ':' .. math.random(1000000))
        redis.call('EXPIRE', key, window + 1)
        return {1, limit - count - 1, now + window * 1000}
    else
        -- Get the oldest request to calculate reset time
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local reset_at = oldest[2] + window * 1000
        return {0, 0, reset_at}
    end
    """
    
    def __init__(self, redis_client=None, prefix: str = "ratelimit"):
        self._redis = redis_client
        self.prefix = prefix
        self._script_sha: Optional[str] = None
        self._local_limits: Dict[str, list] = {}  # Fallback when Redis unavailable
    
    async def _get_redis(self):
        """Get Redis client"""
        if self._redis:
            return self._redis
        
        try:
            from .cache_service import get_cache_service
            cache = await get_cache_service()
            return cache._client
        except Exception:
            return None
    
    async def _ensure_script(self):
        """Load Lua script if not already loaded"""
        if self._script_sha is not None:
            return
        
        redis = await self._get_redis()
        if redis:
            try:
                self._script_sha = await redis.script_load(self.SLIDING_WINDOW_SCRIPT)
            except Exception as e:
                logger.warning(f"Failed to load rate limit script: {e}")
    
    def _local_check(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> RateLimitResult:
        """Local rate limiting fallback"""
        now = time.time()
        window_start = now - config.window_seconds
        
        # Initialize or clean up
        if key not in self._local_limits:
            self._local_limits[key] = []
        
        # Remove old entries
        self._local_limits[key] = [
            t for t in self._local_limits[key]
            if t > window_start
        ]
        
        count = len(self._local_limits[key])
        
        if count < config.requests_per_window:
            self._local_limits[key].append(now)
            return RateLimitResult(
                allowed=True,
                remaining=config.requests_per_window - count - 1,
                reset_at=now + config.window_seconds,
                limit=config.requests_per_window,
            )
        else:
            oldest = min(self._local_limits[key])
            reset_at = oldest + config.window_seconds
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=reset_at,
                retry_after=reset_at - now,
                limit=config.requests_per_window,
            )
    
    async def check(
        self,
        identifier: str,
        action: str,
        config: RateLimitConfig,
    ) -> RateLimitResult:
        """Check if request is allowed"""
        key = f"{self.prefix}:{action}:{identifier}"
        now = int(time.time() * 1000)
        
        redis = await self._get_redis()
        
        if not redis:
            return self._local_check(key, config)
        
        await self._ensure_script()
        
        try:
            if self._script_sha:
                result = await redis.evalsha(
                    self._script_sha,
                    1,
                    key,
                    now,
                    config.window_seconds,
                    config.requests_per_window,
                )
            else:
                result = await redis.eval(
                    self.SLIDING_WINDOW_SCRIPT,
                    1,
                    key,
                    now,
                    config.window_seconds,
                    config.requests_per_window,
                )
            
            allowed = bool(result[0])
            remaining = int(result[1])
            reset_at = result[2] / 1000
            
            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=None if allowed else (reset_at - time.time()),
                limit=config.requests_per_window,
            )
        
        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")
            # Fail open with local fallback
            return self._local_check(key, config)
    
    async def get_usage(
        self,
        identifier: str,
        action: str,
        config: RateLimitConfig,
    ) -> Dict[str, Any]:
        """Get current usage stats"""
        key = f"{self.prefix}:{action}:{identifier}"
        now = int(time.time() * 1000)
        window_start = now - config.window_seconds * 1000
        
        redis = await self._get_redis()
        
        if not redis:
            local_key = key
            if local_key in self._local_limits:
                count = len([
                    t for t in self._local_limits[local_key]
                    if t > (now / 1000 - config.window_seconds)
                ])
            else:
                count = 0
            
            return {
                "used": count,
                "limit": config.requests_per_window,
                "remaining": max(0, config.requests_per_window - count),
                "window_seconds": config.window_seconds,
                "source": "local",
            }
        
        try:
            count = await redis.zcount(key, window_start, now)
            
            return {
                "used": count,
                "limit": config.requests_per_window,
                "remaining": max(0, config.requests_per_window - count),
                "window_seconds": config.window_seconds,
                "source": "redis",
            }
        
        except Exception as e:
            logger.error(f"Rate limit usage check failed: {e}")
            return {"error": str(e)}
    
    async def reset(self, identifier: str, action: str):
        """Reset rate limit for identifier"""
        key = f"{self.prefix}:{action}:{identifier}"
        
        # Clear local
        self._local_limits.pop(key, None)
        
        # Clear Redis
        redis = await self._get_redis()
        if redis:
            try:
                await redis.delete(key)
            except Exception as e:
                logger.warning(f"Failed to reset rate limit: {e}")


class CircuitBreaker:
    """
    Circuit breaker for external service calls
    Prevents cascade failures
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_requests: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests
        
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0
        self._state = "closed"  # closed, open, half-open
    
    def _should_attempt(self) -> bool:
        """Check if request should be attempted"""
        if self._state == "closed":
            return True
        
        if self._state == "open":
            # Check if recovery timeout has passed
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = "half-open"
                self._success_count = 0
                return True
            return False
        
        # half-open: allow limited requests
        return self._success_count < self.half_open_requests
    
    def record_success(self):
        """Record successful call"""
        self._failure_count = 0
        
        if self._state == "half-open":
            self._success_count += 1
            if self._success_count >= self.half_open_requests:
                self._state = "closed"
                logger.info("Circuit breaker closed")
    
    def record_failure(self):
        """Record failed call"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures"
            )
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)"""
        return self._state == "open" and not self._should_attempt()
    
    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state"""
        return {
            "state": self._state,
            "failure_count": self._failure_count,
            "last_failure": self._last_failure_time,
        }


class BackpressureManager:
    """
    Manages backpressure for external API calls
    Implements concurrency limiting and circuit breaking
    """
    
    def __init__(
        self,
        service_name: str,
        max_concurrent: int = 100,
        timeout_seconds: float = 30.0,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.service_name = service_name
        self.max_concurrent = max_concurrent
        self.timeout = timeout_seconds
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_requests = 0
        self._total_requests = 0
        self._total_errors = 0
    
    async def acquire(self) -> Tuple[bool, Optional[str]]:
        """
        Acquire permission to make request
        Returns (allowed, reason if denied)
        """
        # Check circuit breaker
        if self.circuit_breaker.is_open:
            return False, "circuit_open"
        
        # Try to acquire semaphore
        try:
            acquired = await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.timeout,
            )
            if acquired:
                self._active_requests += 1
                self._total_requests += 1
                return True, None
        except asyncio.TimeoutError:
            return False, "timeout"
        
        return False, "concurrency_limit"
    
    def release(self):
        """Release acquired slot"""
        self._active_requests -= 1
        self._semaphore.release()
    
    def record_success(self):
        """Record successful request"""
        self.circuit_breaker.record_success()
    
    def record_failure(self):
        """Record failed request"""
        self._total_errors += 1
        self.circuit_breaker.record_failure()
    
    def get_status(self) -> Dict[str, Any]:
        """Get backpressure status"""
        return {
            "service": self.service_name,
            "active_requests": self._active_requests,
            "max_concurrent": self.max_concurrent,
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "circuit_breaker": self.circuit_breaker.get_state(),
        }


class OpenRouterQuotaManager:
    """
    Manages OpenRouter API quota across all users
    Implements fair queuing and quota distribution
    """
    
    def __init__(
        self,
        daily_quota: int = 100000,
        per_user_limit: int = 1000,
        redis_client=None,
    ):
        self.daily_quota = daily_quota
        self.per_user_limit = per_user_limit
        self._redis = redis_client
        
        # Local tracking fallback
        self._local_global = 0
        self._local_users: Dict[str, int] = {}
        self._last_reset = self._get_day_key()
    
    def _get_day_key(self) -> str:
        """Get key for current day"""
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m-%d")
    
    def _seconds_until_midnight(self) -> int:
        """Get seconds until midnight UTC"""
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return int((midnight - now).total_seconds())
    
    async def _get_redis(self):
        """Get Redis client"""
        if self._redis:
            return self._redis
        
        try:
            from .cache_service import get_cache_service
            cache = await get_cache_service()
            return cache._client
        except Exception:
            return None
    
    def _local_check(self, user_id: str) -> Dict[str, Any]:
        """Local quota check fallback"""
        day = self._get_day_key()
        
        # Reset on new day
        if day != self._last_reset:
            self._local_global = 0
            self._local_users.clear()
            self._last_reset = day
        
        if self._local_global >= self.daily_quota:
            return {
                "allowed": False,
                "reason": "global_quota_exceeded",
                "retry_after": self._seconds_until_midnight(),
            }
        
        user_used = self._local_users.get(user_id, 0)
        if user_used >= self.per_user_limit:
            return {
                "allowed": False,
                "reason": "user_quota_exceeded",
                "retry_after": self._seconds_until_midnight(),
            }
        
        return {
            "allowed": True,
            "global_remaining": self.daily_quota - self._local_global,
            "user_remaining": self.per_user_limit - user_used,
        }
    
    async def check_quota(self, user_id: str) -> Dict[str, Any]:
        """Check if user can make request"""
        redis = await self._get_redis()
        
        if not redis:
            return self._local_check(user_id)
        
        day = self._get_day_key()
        
        try:
            # Check global quota
            global_key = f"quota:openrouter:global:{day}"
            global_used = await redis.get(global_key) or 0
            global_used = int(global_used)
            
            if global_used >= self.daily_quota:
                return {
                    "allowed": False,
                    "reason": "global_quota_exceeded",
                    "retry_after": self._seconds_until_midnight(),
                }
            
            # Check user quota
            user_key = f"quota:openrouter:user:{user_id}:{day}"
            user_used = await redis.get(user_key) or 0
            user_used = int(user_used)
            
            if user_used >= self.per_user_limit:
                return {
                    "allowed": False,
                    "reason": "user_quota_exceeded",
                    "retry_after": self._seconds_until_midnight(),
                }
            
            return {
                "allowed": True,
                "global_remaining": self.daily_quota - global_used,
                "user_remaining": self.per_user_limit - user_used,
            }
        
        except Exception as e:
            logger.warning(f"Quota check failed: {e}")
            return self._local_check(user_id)
    
    async def record_usage(self, user_id: str, tokens: int = 1):
        """Record API usage"""
        day = self._get_day_key()
        ttl = self._seconds_until_midnight() + 3600
        
        # Update local tracking
        if day != self._last_reset:
            self._local_global = 0
            self._local_users.clear()
            self._last_reset = day
        
        self._local_global += tokens
        self._local_users[user_id] = self._local_users.get(user_id, 0) + tokens
        
        # Update Redis
        redis = await self._get_redis()
        if redis:
            try:
                pipe = redis.pipeline()
                
                global_key = f"quota:openrouter:global:{day}"
                await pipe.incrby(global_key, tokens)
                await pipe.expire(global_key, ttl)
                
                user_key = f"quota:openrouter:user:{user_id}:{day}"
                await pipe.incrby(user_key, tokens)
                await pipe.expire(user_key, ttl)
                
                await pipe.execute()
            except Exception as e:
                logger.warning(f"Failed to record usage: {e}")
    
    async def get_usage_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get quota usage statistics"""
        day = self._get_day_key()
        
        redis = await self._get_redis()
        
        if not redis:
            return {
                "global_used": self._local_global,
                "global_limit": self.daily_quota,
                "user_used": self._local_users.get(user_id, 0) if user_id else None,
                "user_limit": self.per_user_limit,
                "source": "local",
            }
        
        try:
            global_key = f"quota:openrouter:global:{day}"
            global_used = int(await redis.get(global_key) or 0)
            
            user_used = None
            if user_id:
                user_key = f"quota:openrouter:user:{user_id}:{day}"
                user_used = int(await redis.get(user_key) or 0)
            
            return {
                "global_used": global_used,
                "global_limit": self.daily_quota,
                "global_remaining": self.daily_quota - global_used,
                "user_used": user_used,
                "user_limit": self.per_user_limit,
                "user_remaining": self.per_user_limit - user_used if user_used else None,
                "resets_in": self._seconds_until_midnight(),
                "source": "redis",
            }
        except Exception as e:
            logger.warning(f"Failed to get usage stats: {e}")
            return {"error": str(e)}


def rate_limited(
    action: str = "api",
    tier: str = "free",
    identifier_extractor: Optional[Callable] = None,
):
    """Decorator for rate limiting functions"""
    def decorator(func: Callable):
        limiter = DistributedRateLimiter()
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract identifier (default to first arg or 'anonymous')
            if identifier_extractor:
                identifier = identifier_extractor(*args, **kwargs)
            elif args:
                identifier = str(args[0])
            else:
                identifier = "anonymous"
            
            config = get_rate_limit_config(tier, action)
            result = await limiter.check(identifier, action, config)
            
            if not result.allowed:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "retry_after": result.retry_after,
                        "limit": result.limit,
                    },
                    headers={"Retry-After": str(int(result.retry_after or 60))},
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Global instances
_rate_limiter: Optional[DistributedRateLimiter] = None
_quota_manager: Optional[OpenRouterQuotaManager] = None


async def get_rate_limiter() -> DistributedRateLimiter:
    """Get global rate limiter"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = DistributedRateLimiter()
    return _rate_limiter


async def get_quota_manager() -> OpenRouterQuotaManager:
    """Get global quota manager"""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = OpenRouterQuotaManager(
            daily_quota=int(os.environ.get('OPENROUTER_DAILY_QUOTA', 100000)),
            per_user_limit=int(os.environ.get('OPENROUTER_USER_LIMIT', 1000)),
        )
    return _quota_manager
