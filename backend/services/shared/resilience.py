"""Resilience patterns: Circuit Breaker, Retries, Timeouts"""
import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Any, TypeVar, Coroutine, Optional
from functools import wraps
from datetime import datetime, timedelta
import random

# Import exception from exceptions module
from services.shared.exceptions import CircuitBreakerOpen

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"          # Working normally
    OPEN = "open"              # Failing, reject requests
    HALF_OPEN = "half_open"    # Testing if recovered


# Backward compatibility alias
CircuitBreakerError = CircuitBreakerOpen


class CircuitBreaker:
    """
    Circuit breaker pattern for handling failures gracefully
    
    States:
    - CLOSED: Normal operation
    - OPEN: Too many failures, reject requests
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
    
    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        logger.info("Circuit breaker manually reset to CLOSED")
    
    def get_state_info(self) -> dict:
        """Get current state information."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None
        }
    
    def should_allow_request(self) -> bool:
        """Check if a request should be allowed based on current state."""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker entering HALF_OPEN state")
            else:
                raise CircuitBreakerError(
                    f"Circuit breaker is OPEN. Retry after "
                    f"{self.recovery_timeout}s"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    async def call_async(
        self, 
        func: Callable[..., Coroutine[Any, Any, T]], 
        *args, 
        **kwargs
    ) -> T:
        """Execute async function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker entering HALF_OPEN state")
            else:
                raise CircuitBreakerError(
                    f"Circuit breaker is OPEN. Retry after "
                    f"{self.recovery_timeout}s"
                )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            # Close circuit after reaching success threshold
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0
                logger.info("Circuit breaker CLOSED (service recovered)")
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker OPEN after {self.failure_count} failures"
            )
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should try to recover"""
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def get_state(self) -> str:
        """Get current state"""
        return self.state.value
    
    def record_failure(self) -> None:
        """Manually record a failure (for testing/external use)."""
        self._on_failure()
    
    def record_success(self) -> None:
        """Manually record a success (for testing/external use)."""
        # Auto-transition from OPEN to HALF_OPEN if timeout has elapsed
        if self.state == CircuitState.OPEN and self._should_attempt_reset():
            self.state = CircuitState.HALF_OPEN
            logger.info("Circuit breaker auto-transitioned to HALF_OPEN")
        self._on_success()
    
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN
    
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (including timeout-triggered transition)."""
        # Auto-transition from OPEN to HALF_OPEN if timeout has elapsed
        if self.state == CircuitState.OPEN and self._should_attempt_reset():
            self.state = CircuitState.HALF_OPEN
            logger.info("Circuit breaker auto-transitioned to HALF_OPEN")
        return self.state == CircuitState.HALF_OPEN
    
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.state == CircuitState.CLOSED


def retry_async(
    max_retries: int = None,
    base_delay: float = None,
    max_delay: float = 10.0,
    backoff_multiplier: float = 2.0
):
    """
    Decorator for async functions with retry logic and exponential backoff.
    
    Usage:
        @retry_async(max_retries=3, base_delay=0.01)
        async def my_func():
            ...
    """
    _max_attempts = max_retries if max_retries is not None else 3
    _base_delay = base_delay if base_delay is not None else 0.1
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*f_args, **f_kwargs):
            attempt = 0
            delay = _base_delay
            
            while attempt < _max_attempts:
                try:
                    return await func(*f_args, **f_kwargs)
                except Exception as e:
                    attempt += 1
                    
                    if attempt >= _max_attempts:
                        logger.error(f"All {_max_attempts} retry attempts failed")
                        raise
                    
                    # Add jitter to prevent thundering herd
                    jitter = random.uniform(0, delay * 0.1)
                    wait_time = min(delay + jitter, max_delay)
                    
                    logger.warning(
                        f"Attempt {attempt} failed, retrying in {wait_time:.2f}s: {e}"
                    )
                    
                    await asyncio.sleep(wait_time)
                    delay *= backoff_multiplier
        return wrapper
    return decorator


def retry_sync(
    func: Callable[..., T],
    *args,
    max_attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 10.0,
    backoff_multiplier: float = 2.0,
    **kwargs
) -> T:
    """Retry sync function with exponential backoff"""
    attempt = 0
    delay = base_delay
    
    while attempt < max_attempts:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            attempt += 1
            
            if attempt >= max_attempts:
                logger.error(f"All {max_attempts} retry attempts failed")
                raise
            
            jitter = random.uniform(0, delay * 0.1)
            wait_time = min(delay + jitter, max_delay)
            
            logger.warning(
                f"Attempt {attempt} failed, retrying in {wait_time:.2f}s: {e}"
            )
            
            asyncio.run(asyncio.sleep(wait_time))
            delay *= backoff_multiplier


class TimeoutError(Exception):
    """Raised when operation times out"""
    pass


def async_timeout(timeout_seconds: float):
    """Decorator to add timeout to async functions.
    
    Usage:
        @async_timeout(0.1)
        async def my_func():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.error(f"Operation timed out after {timeout_seconds}s")
                raise asyncio.TimeoutError(f"Operation timed out after {timeout_seconds}s")
        return wrapper
    return decorator


# ============================================================
# RetryPolicy class for structured retry configuration
# ============================================================

from dataclasses import dataclass, field


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    # Primary parameters
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    backoff_multiplier: float = 2.0
    retryable_exceptions: tuple = (Exception,)
    
    # Aliases for test compatibility
    max_retries: int = field(default=None, repr=False)
    delay: float = field(default=None, repr=False)
    backoff_factor: float = field(default=None, repr=False)
    exceptions: tuple = field(default=None, repr=False)
    
    def __post_init__(self):
        # Handle aliases
        if self.max_retries is not None:
            self.max_attempts = self.max_retries
        else:
            self.max_retries = self.max_attempts
            
        if self.delay is not None:
            self.base_delay = self.delay
        else:
            self.delay = self.base_delay
            
        if self.backoff_factor is not None:
            self.backoff_multiplier = self.backoff_factor
        else:
            self.backoff_factor = self.backoff_multiplier
            
        if self.exceptions is not None:
            self.retryable_exceptions = self.exceptions
        else:
            self.exceptions = self.retryable_exceptions
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if we should retry given the exception and attempt number."""
        if attempt >= self.max_attempts:
            return False
        return isinstance(exception, self.retryable_exceptions)
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number (0-indexed)."""
        delay = self.base_delay * (self.backoff_multiplier ** attempt)
        return delay  # No jitter for predictable tests


# ============================================================
# Decorator functions
# ============================================================

def with_retry(
    max_attempts: int = None,
    base_delay: float = None,
    max_delay: float = 10.0,
    backoff_multiplier: float = None,
    retryable_exceptions: tuple = (Exception,),
    # Aliases for test compatibility
    max_retries: int = None,
    delay: float = None,
    backoff_factor: float = None,
    exceptions: tuple = None
):
    """
    Decorator to add retry logic to both sync and async functions.
    
    Usage:
        @with_retry(max_attempts=3)
        async def my_function():
            ...
        
        @with_retry(max_retries=3, delay=0.01)
        def sync_function():
            ...
    """
    # Resolve aliases
    _max_attempts = max_retries if max_retries is not None else (max_attempts if max_attempts is not None else 3)
    _base_delay = delay if delay is not None else (base_delay if base_delay is not None else 0.1)
    _backoff_multiplier = backoff_factor if backoff_factor is not None else (backoff_multiplier if backoff_multiplier is not None else 2.0)
    _retryable_exceptions = exceptions if exceptions is not None else retryable_exceptions
    
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            # Async version
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                policy = RetryPolicy(
                    max_attempts=_max_attempts,
                    base_delay=_base_delay,
                    max_delay=max_delay,
                    backoff_multiplier=_backoff_multiplier,
                    retryable_exceptions=_retryable_exceptions
                )
                
                attempt = 0
                last_exception: Optional[Exception] = None
                
                while attempt < policy.max_attempts:
                    try:
                        attempt += 1
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        
                        if not policy.should_retry(e, attempt):
                            raise
                        
                        delay_time = policy.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt}/{policy.max_attempts} failed for {func.__name__}, "
                            f"retrying in {delay_time:.2f}s: {e}"
                        )
                        await asyncio.sleep(delay_time)
                
                if last_exception:
                    raise last_exception
                raise RuntimeError("Retry loop exited without result")
            
            return async_wrapper
        else:
            # Sync version
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                policy = RetryPolicy(
                    max_attempts=_max_attempts,
                    base_delay=_base_delay,
                    max_delay=max_delay,
                    backoff_multiplier=_backoff_multiplier,
                    retryable_exceptions=_retryable_exceptions
                )
                
                attempt = 0
                last_exception: Optional[Exception] = None
                
                while attempt < policy.max_attempts:
                    try:
                        attempt += 1
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        
                        if not policy.should_retry(e, attempt):
                            raise
                        
                        delay_time = policy.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt}/{policy.max_attempts} failed for {func.__name__}, "
                            f"retrying in {delay_time:.2f}s: {e}"
                        )
                        time.sleep(delay_time)
                
                if last_exception:
                    raise last_exception
                raise RuntimeError("Retry loop exited without result")
            
            return sync_wrapper
    
    return decorator


def with_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception
):
    """
    Decorator to add circuit breaker logic to both sync and async functions.
    
    Usage:
        @with_circuit_breaker(failure_threshold=5)
        async def my_function():
            ...
        
        @with_circuit_breaker(failure_threshold=3)
        def sync_function():
            ...
    """
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception
    )
    
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            # Async version
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await breaker.call_async(func, *args, **kwargs)
            
            # Expose breaker for testing
            async_wrapper.circuit_breaker = breaker  # type: ignore
            return async_wrapper
        else:
            # Sync version
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return breaker.call(func, *args, **kwargs)
            
            # Expose breaker for testing
            sync_wrapper.circuit_breaker = breaker  # type: ignore
            return sync_wrapper
    
    return decorator
