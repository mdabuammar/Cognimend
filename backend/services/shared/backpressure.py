"""
Production-grade backpressure and resilience management for DriftGuard
Handles external service failures gracefully
"""
import os
import asyncio
import time
from typing import Optional, Dict, Any, Callable, TypeVar, List
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from contextlib import asynccontextmanager
import logging
import random

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceState(Enum):
    """Service health states"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ServiceHealth:
    """Track health of an external service"""
    name: str
    state: ServiceState = ServiceState.HEALTHY
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_success: float = 0
    last_failure: float = 0
    total_requests: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0
    
    def record_success(self, latency_ms: float):
        """Record successful request"""
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success = time.time()
        self.total_requests += 1
        
        # Update rolling average
        self.avg_latency_ms = (self.avg_latency_ms * 0.9) + (latency_ms * 0.1)
        
        # Upgrade state if recovering
        if self.state == ServiceState.UNHEALTHY and self.consecutive_successes >= 3:
            self.state = ServiceState.DEGRADED
        elif self.state == ServiceState.DEGRADED and self.consecutive_successes >= 5:
            self.state = ServiceState.HEALTHY
    
    def record_failure(self):
        """Record failed request"""
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure = time.time()
        self.total_requests += 1
        self.total_failures += 1
        
        # Downgrade state
        if self.consecutive_failures >= 3:
            self.state = ServiceState.UNHEALTHY
        elif self.consecutive_failures >= 1:
            self.state = ServiceState.DEGRADED


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts based on service health
    Implements AIMD (Additive Increase Multiplicative Decrease)
    """
    
    def __init__(
        self,
        initial_rate: float = 100.0,  # requests/second
        min_rate: float = 1.0,
        max_rate: float = 1000.0,
        increase_factor: float = 1.1,
        decrease_factor: float = 0.5,
    ):
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.increase_factor = increase_factor
        self.decrease_factor = decrease_factor
        
        self._tokens = initial_rate
        self._last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """Try to acquire a token"""
        async with self._lock:
            self._refill_tokens()
            
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False
    
    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(
            self.current_rate,
            self._tokens + (elapsed * self.current_rate)
        )
        self._last_refill = now
    
    def on_success(self):
        """Increase rate on success (additive increase)"""
        self.current_rate = min(
            self.max_rate,
            self.current_rate * self.increase_factor
        )
    
    def on_failure(self):
        """Decrease rate on failure (multiplicative decrease)"""
        self.current_rate = max(
            self.min_rate,
            self.current_rate * self.decrease_factor
        )
    
    def get_stats(self) -> Dict[str, float]:
        """Get current limiter stats"""
        return {
            "current_rate": self.current_rate,
            "available_tokens": self._tokens,
            "min_rate": self.min_rate,
            "max_rate": self.max_rate,
        }


class LoadShedder:
    """
    Intelligent load shedding based on system capacity
    Drops low-priority requests when overloaded
    """
    
    def __init__(
        self,
        max_concurrent: int = 1000,
        high_watermark: float = 0.8,
        critical_watermark: float = 0.95,
    ):
        self.max_concurrent = max_concurrent
        self.high_watermark = high_watermark
        self.critical_watermark = critical_watermark
        
        self._current_load = 0
        self._lock = asyncio.Lock()
        self._shed_count = 0
    
    async def should_admit(self, priority: int = 5) -> bool:
        """
        Check if request should be admitted
        Priority: 1 (highest) to 10 (lowest)
        """
        async with self._lock:
            load_factor = self._current_load / self.max_concurrent
            
            # Always admit if under high watermark
            if load_factor < self.high_watermark:
                return True
            
            # Shed based on priority if between high and critical
            if load_factor < self.critical_watermark:
                # Higher priority (lower number) has better chance
                admission_probability = (10 - priority) / 10
                # Reduce probability as load increases
                admission_probability *= (self.critical_watermark - load_factor) / (self.critical_watermark - self.high_watermark)
                
                if random.random() < admission_probability:
                    return True
                
                self._shed_count += 1
                return False
            
            # Only admit highest priority (1-2) at critical load
            if priority <= 2:
                return True
            
            self._shed_count += 1
            return False
    
    async def acquire(self):
        """Acquire a slot"""
        async with self._lock:
            self._current_load += 1
    
    async def release(self):
        """Release a slot"""
        async with self._lock:
            self._current_load = max(0, self._current_load - 1)
    
    @asynccontextmanager
    async def slot(self, priority: int = 5):
        """Context manager for load shedding"""
        if not await self.should_admit(priority):
            raise LoadSheddedException(
                f"Request shed due to high load (priority={priority})"
            )
        
        await self.acquire()
        try:
            yield
        finally:
            await self.release()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get load shedder stats"""
        return {
            "current_load": self._current_load,
            "max_concurrent": self.max_concurrent,
            "load_factor": self._current_load / self.max_concurrent,
            "shed_count": self._shed_count,
        }


class LoadSheddedException(Exception):
    """Raised when request is shed due to high load"""
    pass


class RetryPolicy:
    """Configurable retry policy with exponential backoff"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[tuple] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or (Exception,)
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for attempt"""
        delay = min(
            self.max_delay,
            self.base_delay * (self.exponential_base ** attempt)
        )
        
        if self.jitter:
            delay *= (0.5 + random.random())
        
        return delay
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Check if should retry"""
        if attempt >= self.max_retries:
            return False
        
        return isinstance(exception, self.retryable_exceptions)


class BulkheadIsolator:
    """
    Bulkhead pattern for isolating failures
    Limits concurrent calls per service/resource
    """
    
    def __init__(self, default_limit: int = 50):
        self.default_limit = default_limit
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._stats: Dict[str, Dict[str, int]] = {}
    
    def _get_semaphore(self, name: str, limit: Optional[int] = None) -> asyncio.Semaphore:
        """Get or create semaphore for resource"""
        if name not in self._semaphores:
            self._semaphores[name] = asyncio.Semaphore(limit or self.default_limit)
            self._stats[name] = {"acquired": 0, "rejected": 0, "active": 0}
        return self._semaphores[name]
    
    @asynccontextmanager
    async def isolate(
        self,
        name: str,
        timeout: Optional[float] = None,
        limit: Optional[int] = None,
    ):
        """
        Isolate a call to a resource
        Raises TimeoutError if bulkhead is full
        """
        semaphore = self._get_semaphore(name, limit)
        stats = self._stats[name]
        
        try:
            acquired = await asyncio.wait_for(
                semaphore.acquire(),
                timeout=timeout,
            )
            if acquired:
                stats["acquired"] += 1
                stats["active"] += 1
        except asyncio.TimeoutError:
            stats["rejected"] += 1
            raise TimeoutError(f"Bulkhead {name} is full")
        
        try:
            yield
        finally:
            stats["active"] -= 1
            semaphore.release()
    
    def get_stats(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Get bulkhead statistics"""
        if name:
            return self._stats.get(name, {})
        return dict(self._stats)


class BackpressureController:
    """
    Unified backpressure controller for managing external service calls
    Combines circuit breaking, rate limiting, retries, and load shedding
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.health = ServiceHealth(name=service_name)
        
        # Components
        self.rate_limiter = AdaptiveRateLimiter()
        self.load_shedder = LoadShedder()
        self.bulkhead = BulkheadIsolator()
        self.retry_policy = RetryPolicy()
        
        # Circuit breaker
        from .rate_limiting import CircuitBreaker
        self.circuit_breaker = CircuitBreaker()
    
    @asynccontextmanager
    async def call(
        self,
        priority: int = 5,
        timeout: Optional[float] = None,
    ):
        """
        Execute a protected call to the service
        Applies all backpressure mechanisms
        """
        # 1. Check circuit breaker
        if self.circuit_breaker.is_open:
            raise CircuitOpenException(
                f"Circuit breaker open for {self.service_name}"
            )
        
        # 2. Load shedding
        if not await self.load_shedder.should_admit(priority):
            raise LoadSheddedException(
                f"Request shed for {self.service_name}"
            )
        
        # 3. Rate limiting
        if not await self.rate_limiter.acquire():
            raise RateLimitedException(
                f"Rate limit exceeded for {self.service_name}"
            )
        
        # 4. Bulkhead isolation
        start_time = time.perf_counter()
        
        async with self.load_shedder.slot(priority):
            async with self.bulkhead.isolate(self.service_name, timeout):
                try:
                    yield
                    
                    # Record success
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    self.health.record_success(latency_ms)
                    self.circuit_breaker.record_success()
                    self.rate_limiter.on_success()
                    
                except Exception as e:
                    # Record failure
                    self.health.record_failure()
                    self.circuit_breaker.record_failure()
                    self.rate_limiter.on_failure()
                    raise
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        priority: int = 5,
        **kwargs,
    ) -> Any:
        """Execute function with automatic retries"""
        last_exception = None
        
        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                async with self.call(priority=priority):
                    return await func(*args, **kwargs)
            
            except (CircuitOpenException, LoadSheddedException):
                raise  # Don't retry these
            
            except Exception as e:
                last_exception = e
                
                if not self.retry_policy.should_retry(e, attempt):
                    raise
                
                delay = self.retry_policy.get_delay(attempt)
                logger.warning(
                    f"Retry {attempt + 1}/{self.retry_policy.max_retries} "
                    f"for {self.service_name} after {delay:.2f}s: {e}"
                )
                await asyncio.sleep(delay)
        
        raise last_exception
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status"""
        return {
            "service": self.service_name,
            "health": {
                "state": self.health.state.value,
                "consecutive_failures": self.health.consecutive_failures,
                "consecutive_successes": self.health.consecutive_successes,
                "total_requests": self.health.total_requests,
                "total_failures": self.health.total_failures,
                "avg_latency_ms": self.health.avg_latency_ms,
            },
            "circuit_breaker": self.circuit_breaker.get_state(),
            "rate_limiter": self.rate_limiter.get_stats(),
            "load_shedder": self.load_shedder.get_stats(),
            "bulkhead": self.bulkhead.get_stats(self.service_name),
        }


class CircuitOpenException(Exception):
    """Raised when circuit breaker is open"""
    pass


class RateLimitedException(Exception):
    """Raised when rate limit is exceeded"""
    pass


# ============================================================
# Service-specific controllers
# ============================================================

class OpenRouterBackpressure(BackpressureController):
    """Specialized backpressure for OpenRouter API"""
    
    def __init__(self):
        super().__init__("openrouter")
        
        # Adjust settings for LLM API
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=50.0,  # Conservative start
            max_rate=500.0,
        )
        
        self.retry_policy = RetryPolicy(
            max_retries=3,
            base_delay=2.0,  # Longer delays for LLM
            max_delay=60.0,
        )
        
        self.load_shedder = LoadShedder(
            max_concurrent=100,  # Limit concurrent LLM calls
        )


class QdrantBackpressure(BackpressureController):
    """Specialized backpressure for Qdrant"""
    
    def __init__(self):
        super().__init__("qdrant")
        
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=200.0,
            max_rate=2000.0,
        )
        
        self.load_shedder = LoadShedder(
            max_concurrent=500,
        )


class DatabaseBackpressure(BackpressureController):
    """Specialized backpressure for database"""
    
    def __init__(self):
        super().__init__("database")
        
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=500.0,
            max_rate=5000.0,
        )
        
        self.load_shedder = LoadShedder(
            max_concurrent=200,  # Match connection pool
        )


# ============================================================
# Global instances
# ============================================================

_backpressure_controllers: Dict[str, BackpressureController] = {}


def get_backpressure(service: str) -> BackpressureController:
    """Get or create backpressure controller for service"""
    if service not in _backpressure_controllers:
        if service == "openrouter":
            _backpressure_controllers[service] = OpenRouterBackpressure()
        elif service == "qdrant":
            _backpressure_controllers[service] = QdrantBackpressure()
        elif service == "database":
            _backpressure_controllers[service] = DatabaseBackpressure()
        else:
            _backpressure_controllers[service] = BackpressureController(service)
    
    return _backpressure_controllers[service]


def get_all_status() -> Dict[str, Any]:
    """Get status of all backpressure controllers"""
    return {
        name: controller.get_status()
        for name, controller in _backpressure_controllers.items()
    }


# ============================================================
# Decorators
# ============================================================

def with_backpressure(
    service: str,
    priority: int = 5,
    timeout: Optional[float] = None,
):
    """Decorator to apply backpressure to a function"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            controller = get_backpressure(service)
            async with controller.call(priority=priority, timeout=timeout):
                return await func(*args, **kwargs)
        return wrapper
    return decorator


def with_retry(
    service: str,
    priority: int = 5,
):
    """Decorator to apply backpressure with retry"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            controller = get_backpressure(service)
            return await controller.execute_with_retry(
                func, *args, priority=priority, **kwargs
            )
        return wrapper
    return decorator
