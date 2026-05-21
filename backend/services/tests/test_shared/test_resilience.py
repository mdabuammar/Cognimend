"""
Tests for resilience module - Circuit breaker and retry logic.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import time

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from services.shared.resilience import (
    CircuitBreaker,
    CircuitState,
    RetryPolicy,
    with_retry,
    with_circuit_breaker
)


class TestCircuitState:
    """Tests for CircuitState enum."""
    
    def test_states_exist(self):
        """Test all circuit states exist."""
        assert CircuitState.CLOSED is not None
        assert CircuitState.OPEN is not None
        assert CircuitState.HALF_OPEN is not None
    
    def test_states_are_distinct(self):
        """Test circuit states are distinct."""
        states = [CircuitState.CLOSED, CircuitState.OPEN, CircuitState.HALF_OPEN]
        assert len(set(states)) == 3


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        cb = CircuitBreaker()
        
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30
    
    def test_call_success_keeps_closed(self):
        """Test successful call keeps circuit closed."""
        cb = CircuitBreaker()
        
        def successful_func():
            return "success"
        
        result = cb.call(successful_func)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_call_failure_increments_count(self):
        """Test failed call increments failure count."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED
    
    def test_circuit_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def failing_func():
            raise ValueError("Test error")
        
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
    
    def test_open_circuit_raises_exception(self):
        """Test open circuit raises exception immediately."""
        cb = CircuitBreaker(failure_threshold=1)
        
        def failing_func():
            raise ValueError("Test error")
        
        # Trip the circuit
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        # Now circuit should be open
        from services.shared.exceptions import CircuitBreakerOpen
        
        with pytest.raises(CircuitBreakerOpen):
            cb.call(lambda: "should not run")
    
    def test_half_open_after_recovery(self):
        """Test circuit becomes half-open after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        def failing_func():
            raise ValueError("Test error")
        
        # Trip the circuit
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for recovery
        time.sleep(0.15)
        
        # Check state (should allow a test call)
        assert cb.should_allow_request() is True
    
    def test_half_open_success_closes(self):
        """Test successful call in half-open closes circuit."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        call_count = [0]
        
        def maybe_fail():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("First call fails")
            return "success"
        
        # First call trips circuit
        with pytest.raises(ValueError):
            cb.call(maybe_fail)
        
        # Wait for recovery
        time.sleep(0.15)
        
        # Next call should succeed and close circuit
        result = cb.call(maybe_fail)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
    
    def test_half_open_failure_reopens(self):
        """Test failed call in half-open reopens circuit."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        def always_fail():
            raise ValueError("Always fails")
        
        # Trip the circuit
        with pytest.raises(ValueError):
            cb.call(always_fail)
        
        # Wait for recovery
        time.sleep(0.15)
        
        # This should fail and reopen
        with pytest.raises(ValueError):
            cb.call(always_fail)
        
        assert cb.state == CircuitState.OPEN
    
    def test_reset(self):
        """Test manual reset of circuit breaker."""
        cb = CircuitBreaker(failure_threshold=1)
        
        def failing_func():
            raise ValueError("Test error")
        
        # Trip the circuit
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Reset
        cb.reset()
        
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_get_state_info(self):
        """Test getting state information."""
        cb = CircuitBreaker(failure_threshold=3)
        
        info = cb.get_state_info()
        
        assert info["state"] == "closed"
        assert info["failure_count"] == 0
        assert info["failure_threshold"] == 3
        assert "last_failure_time" in info


class TestRetryPolicy:
    """Tests for RetryPolicy class."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        policy = RetryPolicy()
        
        assert policy.max_retries == 3
        assert policy.delay == 1.0
        assert policy.backoff_factor == 2.0
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        policy = RetryPolicy(
            max_retries=5,
            delay=0.5,
            backoff_factor=1.5,
            exceptions=(ValueError, TypeError)
        )
        
        assert policy.max_retries == 5
        assert policy.delay == 0.5
        assert policy.backoff_factor == 1.5
    
    def test_get_delay(self):
        """Test delay calculation with exponential backoff."""
        policy = RetryPolicy(delay=1.0, backoff_factor=2.0)
        
        assert policy.get_delay(0) == 1.0  # 1 * 2^0
        assert policy.get_delay(1) == 2.0  # 1 * 2^1
        assert policy.get_delay(2) == 4.0  # 1 * 2^2
        assert policy.get_delay(3) == 8.0  # 1 * 2^3
    
    def test_should_retry_true(self):
        """Test should_retry returns True for matching exception."""
        policy = RetryPolicy(max_retries=3, exceptions=(ValueError,))
        
        assert policy.should_retry(ValueError("test"), attempt=0) is True
        assert policy.should_retry(ValueError("test"), attempt=1) is True
        assert policy.should_retry(ValueError("test"), attempt=2) is True
    
    def test_should_retry_false_max_retries(self):
        """Test should_retry returns False when max retries reached."""
        policy = RetryPolicy(max_retries=3, exceptions=(ValueError,))
        
        assert policy.should_retry(ValueError("test"), attempt=3) is False
    
    def test_should_retry_false_wrong_exception(self):
        """Test should_retry returns False for non-matching exception."""
        policy = RetryPolicy(max_retries=3, exceptions=(ValueError,))
        
        assert policy.should_retry(TypeError("test"), attempt=0) is False


class TestWithRetryDecorator:
    """Tests for with_retry decorator."""
    
    @pytest.mark.asyncio
    async def test_async_success_no_retry(self):
        """Test successful async function doesn't retry."""
        call_count = [0]
        
        @with_retry(max_retries=3, delay=0.01)
        async def successful_func():
            call_count[0] += 1
            return "success"
        
        result = await successful_func()
        
        assert result == "success"
        assert call_count[0] == 1
    
    @pytest.mark.asyncio
    async def test_async_retry_then_success(self):
        """Test async function retries then succeeds."""
        call_count = [0]
        
        @with_retry(max_retries=3, delay=0.01)
        async def flaky_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = await flaky_func()
        
        assert result == "success"
        assert call_count[0] == 3
    
    @pytest.mark.asyncio
    async def test_async_max_retries_exceeded(self):
        """Test async function raises after max retries."""
        call_count = [0]
        
        @with_retry(max_retries=3, delay=0.01)
        async def always_fails():
            call_count[0] += 1
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError):
            await always_fails()
        
        assert call_count[0] == 3  # max_retries=3 means 3 total attempts
    
    def test_sync_success_no_retry(self):
        """Test successful sync function doesn't retry."""
        call_count = [0]
        
        @with_retry(max_retries=3, delay=0.01)
        def successful_func():
            call_count[0] += 1
            return "success"
        
        result = successful_func()
        
        assert result == "success"
        assert call_count[0] == 1
    
    def test_sync_retry_then_success(self):
        """Test sync function retries then succeeds."""
        call_count = [0]
        
        @with_retry(max_retries=3, delay=0.01)
        def flaky_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = flaky_func()
        
        assert result == "success"
        assert call_count[0] == 2


class TestWithCircuitBreakerDecorator:
    """Tests for with_circuit_breaker decorator."""
    
    def test_decorated_function_works(self):
        """Test decorated function works normally."""
        @with_circuit_breaker(failure_threshold=3)
        def normal_func():
            return "result"
        
        assert normal_func() == "result"
    
    def test_decorated_function_trips_circuit(self):
        """Test decorated function trips circuit after failures."""
        @with_circuit_breaker(failure_threshold=2)
        def failing_func():
            raise ValueError("Error")
        
        # First two calls fail
        with pytest.raises(ValueError):
            failing_func()
        with pytest.raises(ValueError):
            failing_func()
        
        # Third call should get CircuitBreakerOpen
        from services.shared.exceptions import CircuitBreakerOpen
        
        with pytest.raises(CircuitBreakerOpen):
            failing_func()
    
    @pytest.mark.asyncio
    async def test_async_decorated_works(self):
        """Test async decorated function works."""
        @with_circuit_breaker(failure_threshold=3)
        async def async_func():
            return "async result"
        
        result = await async_func()
        
        assert result == "async result"


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker patterns."""
    
    def test_circuit_breaker_with_external_service(self):
        """Test circuit breaker protects external service calls."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        call_log = []
        
        def mock_external_service(should_fail: bool):
            call_log.append("called")
            if should_fail:
                raise ConnectionError("Service unavailable")
            return "OK"
        
        # Two failures trip the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                cb.call(mock_external_service, True)
        
        assert len(call_log) == 2
        
        # Circuit is open - should not call service
        from services.shared.exceptions import CircuitBreakerOpen
        
        with pytest.raises(CircuitBreakerOpen):
            cb.call(mock_external_service, False)
        
        # Service was not called
        assert len(call_log) == 2
        
        # Wait for recovery
        time.sleep(0.15)
        
        # Now should work
        result = cb.call(mock_external_service, False)
        
        assert result == "OK"
        assert len(call_log) == 3
    
    def test_multiple_circuit_breakers_independent(self):
        """Test multiple circuit breakers are independent."""
        cb1 = CircuitBreaker(failure_threshold=1)
        cb2 = CircuitBreaker(failure_threshold=1)
        
        def fail():
            raise ValueError()
        
        # Trip cb1
        with pytest.raises(ValueError):
            cb1.call(fail)
        
        # cb1 is open, cb2 is still closed
        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.CLOSED
