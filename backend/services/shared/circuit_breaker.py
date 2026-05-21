"""
Enhanced Circuit Breaker with Advanced Features
Provides production-grade circuit breaker implementation.

Features:
- Half-open state for gradual recovery
- Sliding window failure tracking
- Per-endpoint circuit breakers
- Metrics and monitoring integration
- Async support with decorators

Usage:
    from services.shared.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
    
    cb = CircuitBreaker("payment-service", config)
    
    @cb.protect
    async def call_payment_api():
        ...
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, TypeVar, Generic, Awaitable, Deque
from functools import wraps
import random

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    """State of the circuit breaker."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failing, requests are rejected
    HALF_OPEN = "half_open"  # Testing recovery, limited requests allowed


class FailureType(str, Enum):
    """Types of failures tracked."""
    EXCEPTION = "exception"
    TIMEOUT = "timeout"
    SLOW_CALL = "slow_call"
    HTTP_ERROR = "http_error"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    # Failure thresholds
    failure_threshold: int = 5  # Failures to open circuit
    failure_rate_threshold: float = 0.5  # 50% failure rate
    slow_call_threshold: float = 0.5  # 50% slow calls
    
    # Timing
    slow_call_duration_seconds: float = 2.0  # Calls slower than this are "slow"
    reset_timeout_seconds: float = 30.0  # Time before trying half-open
    half_open_max_calls: int = 3  # Calls allowed in half-open state
    
    # Sliding window
    sliding_window_size: int = 100  # Number of calls to track
    sliding_window_type: str = "count"  # "count" or "time"
    sliding_window_seconds: float = 60.0  # For time-based window
    
    # Retry
    retry_attempts: int = 0  # Auto-retry before counting failure
    retry_delay_ms: int = 100
    
    # Fallback
    fallback_enabled: bool = True
    
    # Metrics
    record_metrics: bool = True


@dataclass 
class CallResult:
    """Result of a protected call."""
    success: bool
    duration_seconds: float
    failure_type: Optional[FailureType] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    slow_calls: int = 0
    
    total_duration_seconds: float = 0
    
    state_transitions: List[Dict[str, Any]] = field(default_factory=list)
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None
    
    # Rates
    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls
    
    @property
    def slow_call_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.slow_calls / self.total_calls
    
    @property
    def average_duration(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_duration_seconds / self.total_calls


class CircuitBreaker:
    """
    Production-grade circuit breaker with sliding window and half-open state.
    """
    
    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig = None,
        fallback: Callable[..., Awaitable[Any]] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback = fallback
        
        self._state = CircuitState.CLOSED
        self._last_state_change = datetime.now()
        self._last_failure_time: Optional[datetime] = None
        
        # Sliding window
        self._call_results: Deque[CallResult] = deque(maxlen=self.config.sliding_window_size)
        
        # Half-open state tracking
        self._half_open_calls = 0
        self._half_open_successes = 0
        
        # Metrics
        self.metrics = CircuitBreakerMetrics()
        
        # Callbacks
        self._on_state_change: List[Callable[[CircuitState, CircuitState], None]] = []
        self._on_failure: List[Callable[[Exception], None]] = []
        
        logger.info(f"Circuit breaker '{name}' initialized")
    
    @property
    def state(self) -> CircuitState:
        """Get current state, checking for timeout-based transitions."""
        if self._state == CircuitState.OPEN:
            # Check if we should transition to half-open
            elapsed = (datetime.now() - self._last_state_change).total_seconds()
            if elapsed >= self.config.reset_timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
        
        return self._state
    
    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        if new_state == self._state:
            return
        
        old_state = self._state
        self._state = new_state
        self._last_state_change = datetime.now()
        
        # Reset half-open tracking
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._half_open_successes = 0
        
        logger.warning(f"Circuit breaker '{self.name}': {old_state.value} -> {new_state.value}")
        
        # Record transition
        self.metrics.state_transitions.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": datetime.now().isoformat()
        })
        
        # Notify callbacks
        for callback in self._on_state_change:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
    
    def _record_result(self, result: CallResult) -> None:
        """Record a call result and check thresholds."""
        self._call_results.append(result)
        
        # Update metrics
        self.metrics.total_calls += 1
        self.metrics.total_duration_seconds += result.duration_seconds
        
        if result.success:
            self.metrics.successful_calls += 1
            self.metrics.last_success = result.timestamp
        else:
            self.metrics.failed_calls += 1
            self.metrics.last_failure = result.timestamp
            self._last_failure_time = result.timestamp
        
        if result.duration_seconds >= self.config.slow_call_duration_seconds:
            self.metrics.slow_calls += 1
        
        # Handle state transitions
        if self._state == CircuitState.CLOSED:
            self._check_closed_thresholds()
        elif self._state == CircuitState.HALF_OPEN:
            self._check_half_open_result(result)
    
    def _check_closed_thresholds(self) -> None:
        """Check if circuit should open based on failure rates."""
        if len(self._call_results) < 10:  # Minimum sample size
            return
        
        # Apply sliding window
        if self.config.sliding_window_type == "time":
            cutoff = datetime.now() - timedelta(seconds=self.config.sliding_window_seconds)
            results = [r for r in self._call_results if r.timestamp >= cutoff]
        else:
            results = list(self._call_results)
        
        if not results:
            return
        
        # Calculate rates
        failed = sum(1 for r in results if not r.success)
        slow = sum(1 for r in results 
                   if r.duration_seconds >= self.config.slow_call_duration_seconds)
        
        failure_rate = failed / len(results)
        slow_rate = slow / len(results)
        
        # Check thresholds
        should_open = (
            failed >= self.config.failure_threshold or
            failure_rate >= self.config.failure_rate_threshold or
            slow_rate >= self.config.slow_call_threshold
        )
        
        if should_open:
            logger.warning(
                f"Circuit '{self.name}' opening: "
                f"failures={failed}, rate={failure_rate:.1%}, slow_rate={slow_rate:.1%}"
            )
            self._transition_to(CircuitState.OPEN)
    
    def _check_half_open_result(self, result: CallResult) -> None:
        """Check half-open state result."""
        self._half_open_calls += 1
        
        if result.success:
            self._half_open_successes += 1
            
            # If all test calls succeeded, close circuit
            if self._half_open_successes >= self.config.half_open_max_calls:
                logger.info(f"Circuit '{self.name}' recovered, closing")
                self._transition_to(CircuitState.CLOSED)
                self._call_results.clear()  # Reset sliding window
        else:
            # Single failure in half-open reopens circuit
            logger.warning(f"Circuit '{self.name}' still unhealthy, reopening")
            self._transition_to(CircuitState.OPEN)
    
    def _should_allow_call(self) -> bool:
        """Determine if a call should be allowed."""
        state = self.state  # Triggers timeout check
        
        if state == CircuitState.CLOSED:
            return True
        
        if state == CircuitState.OPEN:
            return False
        
        # Half-open: allow limited calls
        if state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.config.half_open_max_calls
        
        return False
    
    async def execute(
        self,
        operation: Callable[..., Awaitable[T]],
        *args,
        fallback: Callable[..., Awaitable[T]] = None,
        **kwargs
    ) -> T:
        """
        Execute an operation with circuit breaker protection.
        
        Args:
            operation: The async operation to execute
            fallback: Optional fallback function if circuit is open
            *args, **kwargs: Arguments passed to operation
        
        Returns:
            Result of operation or fallback
        
        Raises:
            CircuitBreakerOpenError: If circuit is open and no fallback
        """
        # Check if call is allowed
        if not self._should_allow_call():
            self.metrics.rejected_calls += 1
            
            # Try fallback
            fallback_fn = fallback or self.fallback
            if fallback_fn and self.config.fallback_enabled:
                logger.debug(f"Circuit '{self.name}' open, using fallback")
                return await fallback_fn(*args, **kwargs)
            
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is {self._state.value}"
            )
        
        # Execute operation with retry
        start_time = time.time()
        last_error = None
        
        for attempt in range(self.config.retry_attempts + 1):
            try:
                result = await operation(*args, **kwargs)
                
                # Record success
                duration = time.time() - start_time
                self._record_result(CallResult(
                    success=True,
                    duration_seconds=duration
                ))
                
                return result
                
            except Exception as e:
                last_error = e
                
                if attempt < self.config.retry_attempts:
                    await asyncio.sleep(self.config.retry_delay_ms / 1000)
                    continue
                
                # Record failure
                duration = time.time() - start_time
                failure_type = self._classify_error(e)
                
                self._record_result(CallResult(
                    success=False,
                    duration_seconds=duration,
                    failure_type=failure_type,
                    error=str(e)
                ))
                
                # Notify failure callbacks
                for callback in self._on_failure:
                    try:
                        callback(e)
                    except Exception as cb_error:
                        logger.error(f"Failure callback error: {cb_error}")
                
                # Try fallback on failure
                fallback_fn = fallback or self.fallback
                if fallback_fn and self.config.fallback_enabled:
                    logger.debug(f"Circuit '{self.name}' call failed, using fallback")
                    return await fallback_fn(*args, **kwargs)
                
                raise
        
        raise last_error
    
    def _classify_error(self, error: Exception) -> FailureType:
        """Classify error type."""
        if isinstance(error, asyncio.TimeoutError):
            return FailureType.TIMEOUT
        
        # Check for HTTP errors
        error_name = type(error).__name__.lower()
        if "http" in error_name or "status" in error_name:
            return FailureType.HTTP_ERROR
        
        return FailureType.EXCEPTION
    
    def protect(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """
        Decorator to protect a function with circuit breaker.
        
        Usage:
            @circuit_breaker.protect
            async def call_external_api():
                ...
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper
    
    def on_state_change(
        self,
        callback: Callable[[CircuitState, CircuitState], None]
    ) -> None:
        """Register state change callback."""
        self._on_state_change.append(callback)
    
    def on_failure(self, callback: Callable[[Exception], None]) -> None:
        """Register failure callback."""
        self._on_failure.append(callback)
    
    def reset(self) -> None:
        """Force reset to closed state."""
        self._transition_to(CircuitState.CLOSED)
        self._call_results.clear()
        self._half_open_calls = 0
        self._half_open_successes = 0
        logger.info(f"Circuit breaker '{self.name}' manually reset")
    
    def force_open(self) -> None:
        """Force circuit to open state."""
        self._transition_to(CircuitState.OPEN)
        logger.warning(f"Circuit breaker '{self.name}' manually opened")
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "last_state_change": self._last_state_change.isoformat(),
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
            "metrics": {
                "total_calls": self.metrics.total_calls,
                "successful_calls": self.metrics.successful_calls,
                "failed_calls": self.metrics.failed_calls,
                "rejected_calls": self.metrics.rejected_calls,
                "failure_rate": f"{self.metrics.failure_rate:.1%}",
                "slow_call_rate": f"{self.metrics.slow_call_rate:.1%}",
                "average_duration_ms": f"{self.metrics.average_duration * 1000:.0f}"
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "failure_rate_threshold": f"{self.config.failure_rate_threshold:.0%}",
                "reset_timeout_seconds": self.config.reset_timeout_seconds
            }
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# ============================================================================
# Circuit Breaker Registry
# ============================================================================

class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._breakers: Dict[str, CircuitBreaker] = {}
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "CircuitBreakerRegistry":
        return cls()
    
    def register(
        self,
        name: str,
        config: CircuitBreakerConfig = None,
        fallback: Callable = None
    ) -> CircuitBreaker:
        """Register or get a circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config, fallback)
        return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name."""
        return self._breakers.get(name)
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all circuit breakers."""
        return {
            name: cb.get_status()
            for name, cb in self._breakers.items()
        }
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for cb in self._breakers.values():
            cb.reset()


# Convenience function
def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig = None,
    fallback: Callable = None
) -> CircuitBreaker:
    """Get or create a circuit breaker."""
    return CircuitBreakerRegistry.get_instance().register(name, config, fallback)


# ============================================================================
# Bulkhead Pattern
# ============================================================================

class Bulkhead:
    """
    Bulkhead pattern for isolating resources.
    
    Limits concurrent calls to prevent cascade failures.
    """
    
    def __init__(
        self,
        name: str,
        max_concurrent: int = 10,
        max_wait_seconds: float = 5.0
    ):
        self.name = name
        self.max_concurrent = max_concurrent
        self.max_wait_seconds = max_wait_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_calls = 0
        self._rejected_calls = 0
        self._total_calls = 0
    
    async def execute(
        self,
        operation: Callable[..., Awaitable[T]],
        *args,
        **kwargs
    ) -> T:
        """Execute operation within bulkhead limits."""
        self._total_calls += 1
        
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.max_wait_seconds
            )
        except asyncio.TimeoutError:
            self._rejected_calls += 1
            raise BulkheadFullError(
                f"Bulkhead '{self.name}' is full ({self.max_concurrent} concurrent calls)"
            )
        
        self._active_calls += 1
        try:
            return await operation(*args, **kwargs)
        finally:
            self._active_calls -= 1
            self._semaphore.release()
    
    def protect(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """Decorator for bulkhead protection."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper
    
    def get_status(self) -> Dict[str, Any]:
        """Get bulkhead status."""
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent,
            "active_calls": self._active_calls,
            "available_permits": self.max_concurrent - self._active_calls,
            "total_calls": self._total_calls,
            "rejected_calls": self._rejected_calls,
            "rejection_rate": f"{self._rejected_calls / self._total_calls:.1%}" if self._total_calls > 0 else "0%"
        }


class BulkheadFullError(Exception):
    """Raised when bulkhead is full."""
    pass


# ============================================================================
# FastAPI Integration
# ============================================================================

def setup_circuit_breaker_routes(app):
    """Add circuit breaker management endpoints to FastAPI app."""
    from fastapi import APIRouter, HTTPException
    
    router = APIRouter(prefix="/circuit-breakers", tags=["circuit-breakers"])
    registry = CircuitBreakerRegistry.get_instance()
    
    @router.get("/status")
    async def get_all_status():
        """Get status of all circuit breakers."""
        return registry.get_all_status()
    
    @router.get("/status/{name}")
    async def get_status(name: str):
        """Get status of a specific circuit breaker."""
        cb = registry.get(name)
        if not cb:
            raise HTTPException(404, f"Circuit breaker not found: {name}")
        return cb.get_status()
    
    @router.post("/reset/{name}")
    async def reset_breaker(name: str):
        """Reset a specific circuit breaker."""
        cb = registry.get(name)
        if not cb:
            raise HTTPException(404, f"Circuit breaker not found: {name}")
        cb.reset()
        return {"status": "reset", "name": name}
    
    @router.post("/reset-all")
    async def reset_all():
        """Reset all circuit breakers."""
        registry.reset_all()
        return {"status": "all reset"}
    
    @router.post("/force-open/{name}")
    async def force_open(name: str):
        """Force a circuit breaker to open state."""
        cb = registry.get(name)
        if not cb:
            raise HTTPException(404, f"Circuit breaker not found: {name}")
        cb.force_open()
        return {"status": "forced open", "name": name}
    
    app.include_router(router)
