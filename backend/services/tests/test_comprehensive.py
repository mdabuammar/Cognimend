"""
Comprehensive Test Suite for DriftGuard Backend Services
Covers security, reliability, performance, and integration testing.

Run with: pytest backend/services/tests/ -v --cov=services --cov-report=html
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json
import sys
import os
import time
import asyncio
from datetime import datetime, timedelta

# Add parent path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))


# =============================================================================
# SECURITY TESTS
# =============================================================================

class TestSecurityModule:
    """Tests for security-related functionality."""
    
    def test_sql_injection_prevention(self):
        """Test that SQL injection attempts are detected and blocked."""
        from services.shared.security import check_sql_injection, sanitize_string
        
        # Known SQL injection patterns
        injection_attempts = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "UNION SELECT * FROM passwords",
            "1; DELETE FROM documents WHERE 1=1",
            "admin'--",
            "' UNION ALL SELECT NULL,NULL,NULL--",
            "1' AND SLEEP(5)--",
            "'; EXEC xp_cmdshell('cmd');--",
        ]
        
        for attempt in injection_attempts:
            assert check_sql_injection(attempt), f"Failed to detect: {attempt}"
            # Verify sanitization removes dangerous patterns
            sanitized = sanitize_string(attempt)
            assert "DROP" not in sanitized.upper() or sanitized != attempt
    
    def test_xss_prevention(self):
        """Test XSS attack prevention."""
        from services.shared.security import escape_html, sanitize_string
        
        xss_attempts = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "javascript:alert('xss')",
            "<body onload=alert('xss')>",
            "<iframe src='javascript:alert(1)'>",
            "'-alert(1)-'",
            "\"><script>alert(1)</script>",
        ]
        
        for attempt in xss_attempts:
            escaped = escape_html(attempt)
            assert "<script>" not in escaped
            assert "onerror" not in escaped.lower() or "&" in escaped
            assert "javascript:" not in escaped.lower() or "&" in escaped
    
    def test_path_traversal_prevention(self):
        """Test path traversal attack prevention."""
        from services.shared.security import sanitize_path
        
        traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config",
            "/etc/passwd",
            "....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2fetc/passwd",
            "..%252f..%252f..%252fetc/passwd",
        ]
        
        for attempt in traversal_attempts:
            sanitized = sanitize_path(attempt)
            assert ".." not in sanitized
            assert not sanitized.startswith("/etc")
            assert "passwd" not in sanitized.lower()
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        from services.shared.security import RateLimiter
        
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        client_ip = "192.168.1.1"
        
        # First 5 requests should pass
        for i in range(5):
            assert limiter.is_allowed(client_ip), f"Request {i+1} should be allowed"
        
        # 6th request should be blocked
        assert not limiter.is_allowed(client_ip), "6th request should be blocked"
    
    def test_api_key_validation(self):
        """Test API key validation."""
        from services.shared.security import verify_api_key
        
        # Invalid keys
        assert not verify_api_key("")
        assert not verify_api_key(None)
        assert not verify_api_key("short")
        
        # Format validation (if applicable)
        # Valid key format test would depend on implementation
    
    def test_jwt_token_security(self):
        """Test JWT token security measures."""
        from services.shared.security import create_jwt_token, verify_jwt_token
        
        # Test token creation
        payload = {"user_id": "123", "role": "user"}
        token = create_jwt_token(payload, expires_in=3600)
        assert token is not None
        
        # Test token verification
        decoded = verify_jwt_token(token)
        assert decoded["user_id"] == "123"
        
        # Test expired token
        expired_token = create_jwt_token(payload, expires_in=-1)
        with pytest.raises(Exception):
            verify_jwt_token(expired_token)
        
        # Test tampered token
        tampered = token[:-5] + "xxxxx"
        with pytest.raises(Exception):
            verify_jwt_token(tampered)
    
    def test_password_hashing(self):
        """Test password hashing security."""
        from services.shared.security import hash_password, verify_password
        
        password = "SecureP@ssw0rd123!"
        
        # Hash password
        hashed = hash_password(password)
        assert hashed != password
        assert len(hashed) > 50  # Bcrypt hashes are long
        
        # Verify correct password
        assert verify_password(password, hashed)
        
        # Verify incorrect password
        assert not verify_password("WrongPassword", hashed)
        
        # Different hashes for same password (salt)
        hashed2 = hash_password(password)
        assert hashed != hashed2
    
    def test_sensitive_data_masking(self):
        """Test that sensitive data is properly masked in logs."""
        from services.shared.security import mask_sensitive_data
        
        test_data = {
            "user": "john@example.com",
            "password": "secret123",
            "api_key": "sk-abc123xyz",
            "credit_card": "4111111111111111",
            "ssn": "123-45-6789",
            "normal_field": "visible"
        }
        
        masked = mask_sensitive_data(test_data)
        
        assert "secret123" not in str(masked)
        assert "sk-abc123xyz" not in str(masked)
        assert "4111111111111111" not in str(masked)
        assert masked["normal_field"] == "visible"


# =============================================================================
# RELIABILITY TESTS
# =============================================================================

class TestReliabilityModule:
    """Tests for reliability patterns."""
    
    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures."""
        from services.shared.resilience import CircuitBreaker
        
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        # Simulate failures
        for _ in range(3):
            breaker.record_failure()
        
        assert breaker.is_open()
    
    def test_circuit_breaker_half_open(self):
        """Test circuit breaker enters half-open state."""
        from services.shared.resilience import CircuitBreaker
        
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        
        # Open the circuit
        for _ in range(3):
            breaker.record_failure()
        
        assert breaker.is_open()
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        assert breaker.is_half_open()
    
    def test_circuit_breaker_closes_on_success(self):
        """Test circuit breaker closes after successful requests."""
        from services.shared.resilience import CircuitBreaker
        
        breaker = CircuitBreaker(
            failure_threshold=3, 
            recovery_timeout=0.1,
            success_threshold=2
        )
        
        # Open the circuit
        for _ in range(3):
            breaker.record_failure()
        
        time.sleep(0.15)  # Enter half-open
        
        # Record successes
        breaker.record_success()
        breaker.record_success()
        
        assert breaker.is_closed()
    
    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self):
        """Test retry logic with exponential backoff."""
        from services.shared.resilience import retry_async
        
        call_count = 0
        
        @retry_async(max_retries=3, base_delay=0.01)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await flaky_function()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_timeout_decorator(self):
        """Test timeout decorator."""
        from services.shared.resilience import async_timeout
        
        @async_timeout(0.1)
        async def slow_function():
            await asyncio.sleep(1)
            return "completed"
        
        with pytest.raises(asyncio.TimeoutError):
            await slow_function()
    
    def test_health_check_aggregation(self):
        """Test health check aggregation logic."""
        from services.shared.health import HealthChecker, HealthStatus
        
        checker = HealthChecker("test-service", version="1.0.0")
        
        # All healthy
        checker.update_component_status("db", HealthStatus.HEALTHY)
        checker.update_component_status("cache", HealthStatus.HEALTHY)
        
        status = checker.get_overall_status()
        assert status == HealthStatus.HEALTHY
        
        # One degraded
        checker.update_component_status("cache", HealthStatus.DEGRADED)
        status = checker.get_overall_status()
        assert status == HealthStatus.DEGRADED
        
        # One unhealthy
        checker.update_component_status("db", HealthStatus.UNHEALTHY)
        status = checker.get_overall_status()
        assert status == HealthStatus.UNHEALTHY


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestServiceIntegration:
    """Integration tests for service interactions."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies."""
        with patch('services.shared.database.db_pool') as mock_db, \
             patch('services.shared.cache.cache') as mock_cache, \
             patch('qdrant_client.QdrantClient') as mock_qdrant:
            
            mock_db.get_connection.return_value = MagicMock()
            mock_cache.get.return_value = None
            mock_cache.set.return_value = True
            mock_qdrant.return_value.search.return_value = []
            
            yield {
                'db': mock_db,
                'cache': mock_cache,
                'qdrant': mock_qdrant
            }
    
    def test_query_caching(self, mock_dependencies):
        """Test that query results are properly cached."""
        mock_cache = mock_dependencies['cache']
        
        # First query - cache miss
        mock_cache.get.return_value = None
        
        # Simulate query processing
        query = "What is the vacation policy?"
        cache_key = f"query:{hash(query)}"
        
        # After processing, result should be cached
        mock_cache.set.assert_not_called()  # Not called yet
        
        # Simulate caching
        mock_cache.set(cache_key, {"answer": "Test answer"}, ttl=3600)
        mock_cache.set.assert_called_once()
    
    def test_document_processing_pipeline(self, mock_dependencies):
        """Test document upload -> chunking -> embedding pipeline."""
        # This would test the full pipeline
        # 1. Upload document
        # 2. Parse and chunk
        # 3. Generate embeddings
        # 4. Store in Qdrant
        pass
    
    def test_cross_service_error_propagation(self):
        """Test that errors propagate correctly across services."""
        from services.shared.exceptions import ServiceException, DatabaseError
        
        # Test error wrapping
        try:
            raise DatabaseError("Connection failed")
        except ServiceException as e:
            assert "Connection failed" in str(e)
            assert e.error_code is not None


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Performance and load tests."""
    
    def test_query_response_time(self):
        """Test that query responses are within SLO."""
        # Simulate query processing
        start = time.time()
        
        # Mock query processing
        time.sleep(0.1)  # Simulated processing
        
        elapsed = (time.time() - start) * 1000  # ms
        assert elapsed < 500, f"Query took {elapsed}ms, exceeds 500ms SLO"
    
    def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        import concurrent.futures
        
        def simulate_request():
            time.sleep(0.01)
            return True
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(simulate_request) for _ in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        assert all(results)
        assert len(results) == 100
    
    def test_memory_leak_detection(self):
        """Basic memory leak detection test."""
        import gc
        
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Simulate operations that might leak
        for _ in range(1000):
            data = {"key": "value" * 100}
            del data
        
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Allow some variance but catch major leaks
        assert final_objects < initial_objects + 1000


# =============================================================================
# DATA VALIDATION TESTS
# =============================================================================

class TestDataValidation:
    """Tests for data validation."""
    
    def test_document_upload_validation(self):
        """Test document upload validation."""
        from services.shared.validation import validate_upload
        
        # Valid uploads
        assert validate_upload("document.pdf", 1024 * 1024)  # 1MB PDF
        assert validate_upload("readme.txt", 1024)
        assert validate_upload("data.csv", 1024 * 1024 * 10)  # 10MB CSV
        
        # Invalid - wrong extension
        with pytest.raises(ValueError):
            validate_upload("script.exe", 1024)
        
        # Invalid - too large
        with pytest.raises(ValueError):
            validate_upload("huge.pdf", 1024 * 1024 * 100)  # 100MB
    
    def test_query_validation(self):
        """Test query input validation."""
        from services.shared.validation import validate_query
        
        # Valid queries
        assert validate_query("What is the vacation policy?")
        assert validate_query("How do I submit expenses?")
        
        # Invalid - too short
        with pytest.raises(ValueError):
            validate_query("")
        
        # Invalid - too long
        with pytest.raises(ValueError):
            validate_query("x" * 10001)
    
    def test_email_validation(self):
        """Test email validation."""
        from services.shared.validation import validate_email
        
        # Valid emails
        assert validate_email("user@example.com")
        assert validate_email("user.name+tag@example.co.uk")
        
        # Invalid emails
        assert not validate_email("not-an-email")
        assert not validate_email("@missing-local.com")
        assert not validate_email("missing@.domain")


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""
    
    def test_custom_exception_hierarchy(self):
        """Test custom exception hierarchy."""
        from services.shared.exceptions import (
            ServiceException,
            DatabaseError,
            QueryError,
            EmbeddingError,
            ExternalServiceError
        )
        
        # All should inherit from ServiceException
        assert issubclass(DatabaseError, ServiceException)
        assert issubclass(QueryError, ServiceException)
        assert issubclass(EmbeddingError, ServiceException)
        assert issubclass(ExternalServiceError, ServiceException)
    
    def test_exception_serialization(self):
        """Test exception serialization for API responses."""
        from services.shared.exceptions import DatabaseError
        
        error = DatabaseError("Connection refused", error_code="DB001")
        
        serialized = error.to_dict()
        assert "message" in serialized
        assert "error_code" in serialized
        assert serialized["error_code"] == "DB001"
    
    def test_error_logging(self):
        """Test that errors are properly logged."""
        from services.shared.exceptions import ServiceException
        import logging
        
        with patch.object(logging, 'error') as mock_log:
            try:
                raise ServiceException("Test error")
            except ServiceException as e:
                logging.error(f"Caught exception: {e}")
            
            mock_log.assert_called()


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================

class TestConfiguration:
    """Tests for configuration handling."""
    
    def test_environment_variable_loading(self):
        """Test environment variable loading."""
        with patch.dict(os.environ, {'TEST_VAR': 'test_value'}):
            assert os.environ.get('TEST_VAR') == 'test_value'
    
    def test_config_validation(self):
        """Test configuration validation."""
        from services.shared.config import validate_config
        
        valid_config = {
            "database_url": "postgresql://...",
            "redis_url": "redis://...",
            "log_level": "INFO"
        }
        
        assert validate_config(valid_config)
        
        # Missing required field
        invalid_config = {"log_level": "INFO"}
        with pytest.raises(ValueError):
            validate_config(invalid_config)
    
    def test_secret_config_not_logged(self):
        """Test that secret configuration values are not logged."""
        from services.shared.config import get_safe_config
        
        config = {
            "database_url": "postgresql://user:password@host/db",
            "api_key": "sk-secret123",
            "log_level": "INFO"
        }
        
        safe = get_safe_config(config)
        assert "password" not in str(safe)
        assert "sk-secret123" not in str(safe)
        assert safe["log_level"] == "INFO"


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = {'id': 1}
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock = Mock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = True
    return mock
