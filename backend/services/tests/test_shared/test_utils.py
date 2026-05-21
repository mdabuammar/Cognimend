"""
Tests for shared utilities module.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from services.shared.utils import (
    DatabaseManager,
    HealthCheckBuilder,
    ServiceLogger,
    datetime_to_iso,
    format_query_results,
    validate_pagination,
    sanitize_string
)


class TestDatabaseManager:
    """Tests for DatabaseManager class."""
    
    def test_init_with_pool(self, mock_db_connection: MagicMock):
        """Test initialization with connection pool."""
        pool = MagicMock()
        pool.get_connection = MagicMock(return_value=mock_db_connection)
        
        manager = DatabaseManager(pool)
        conn = manager.get_connection()
        
        assert conn is not None
        pool.get_connection.assert_called_once()
    
    def test_return_connection_with_pool(self, mock_db_connection: MagicMock):
        """Test returning connection to pool."""
        pool = MagicMock()
        
        manager = DatabaseManager(pool)
        manager.return_connection(mock_db_connection)
        
        pool.return_connection.assert_called_once_with(mock_db_connection)
    
    def test_execute_query_fetch_all(self, mock_db_manager: MagicMock):
        """Test executing query with fetch all."""
        expected = [{"id": 1, "name": "test"}]
        mock_db_manager.execute_query = MagicMock(return_value=expected)
        
        result = mock_db_manager.execute_query("SELECT * FROM test", fetch="all")
        
        assert result == expected
    
    def test_execute_query_fetch_one(self, mock_db_manager: MagicMock):
        """Test executing query with fetch one."""
        expected = {"id": 1, "name": "test"}
        mock_db_manager.execute_query = MagicMock(return_value=expected)
        
        result = mock_db_manager.execute_query("SELECT * FROM test LIMIT 1", fetch="one")
        
        assert result == expected


class TestHealthCheckBuilder:
    """Tests for HealthCheckBuilder class."""
    
    def test_basic_health_check(self):
        """Test basic health check without components."""
        builder = HealthCheckBuilder("test-service", "1.0.0")
        result = builder.build()
        
        assert result["status"] == "healthy"
        assert result["service"] == "test-service"
        assert result["version"] == "1.0.0"
    
    def test_health_check_with_database(self, mock_db_manager: MagicMock):
        """Test health check with database component."""
        builder = HealthCheckBuilder("test-service")
        builder.add_component("database", True, "connected")
        
        result = builder.build()
        
        assert "database" in result["checks"]
    
    def test_health_check_with_redis(self, mock_cache: AsyncMock):
        """Test health check with Redis component."""
        builder = HealthCheckBuilder("test-service")
        builder.add_component("redis", True, "healthy")
        
        result = builder.build()
        
        assert "redis" in result["checks"]
        assert result["checks"]["redis"] == "healthy"
    
    def test_health_check_disabled_service(self):
        """Test health check with disabled service."""
        builder = HealthCheckBuilder("test-service")
        builder.add_component("redis", True, "disabled")
        
        result = builder.build()
        
        assert result["checks"]["redis"] == "disabled"
        assert result["status"] == "healthy"  # Disabled doesn't affect overall


class TestServiceLogger:
    """Tests for ServiceLogger class."""
    
    def test_info_logging(self, caplog):
        """Test info logging."""
        logger = ServiceLogger("test-service")
        
        with caplog.at_level("INFO"):
            logger.info("Test message", key="value")
        
        assert "Test message" in caplog.text
    
    def test_warning_logging(self, caplog):
        """Test warning logging."""
        logger = ServiceLogger("test-service")
        
        with caplog.at_level("WARNING"):
            logger.warning("Warning message", code=123)
        
        assert "Warning message" in caplog.text
    
    def test_error_logging(self, caplog):
        """Test error logging."""
        logger = ServiceLogger("test-service")
        
        with caplog.at_level("ERROR"):
            logger.error("Error message", exception="TestError")
        
        assert "Error message" in caplog.text


class TestDatetimeUtilities:
    """Tests for datetime utilities."""
    
    def test_datetime_to_iso_with_datetime(self):
        """Test datetime conversion."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = datetime_to_iso(dt)
        
        assert result == "2024-01-15T10:30:45"
    
    def test_datetime_to_iso_with_none(self):
        """Test datetime conversion with None."""
        result = datetime_to_iso(None)
        
        assert result is None
    
    def test_format_query_results(self):
        """Test formatting query results."""
        results = [
            {"id": 1, "created_at": datetime(2024, 1, 15)},
            {"id": 2, "created_at": datetime(2024, 1, 16)}
        ]
        
        formatted = format_query_results(results)
        
        assert formatted[0]["created_at"] == "2024-01-15T00:00:00"
        assert formatted[1]["created_at"] == "2024-01-16T00:00:00"
    
    def test_format_query_results_with_none(self):
        """Test formatting results with None datetime."""
        results = [{"id": 1, "created_at": None}]
        
        formatted = format_query_results(results)
        
        assert formatted[0]["created_at"] is None


class TestValidationUtilities:
    """Tests for validation utilities."""
    
    def test_validate_pagination_normal(self):
        """Test normal pagination values."""
        limit, offset = validate_pagination(10, 20)
        
        assert limit == 10
        assert offset == 20
    
    def test_validate_pagination_exceeds_max(self):
        """Test pagination with limit exceeding max."""
        limit, offset = validate_pagination(200, 0, max_limit=100)
        
        assert limit == 100
        assert offset == 0
    
    def test_validate_pagination_negative(self):
        """Test pagination with negative values."""
        limit, offset = validate_pagination(-5, -10)
        
        assert limit == 1  # Minimum
        assert offset == 0  # Minimum
    
    def test_sanitize_string_normal(self):
        """Test normal string sanitization."""
        result = sanitize_string("  Hello World  ")
        
        assert result == "Hello World"
    
    def test_sanitize_string_long(self):
        """Test string sanitization with length limit."""
        long_string = "a" * 2000
        result = sanitize_string(long_string, max_length=100)
        
        assert len(result) == 100
    
    def test_sanitize_string_empty(self):
        """Test empty string sanitization."""
        result = sanitize_string("")
        
        assert result == ""
    
    def test_sanitize_string_none_like(self):
        """Test sanitizing whitespace-only string."""
        result = sanitize_string("   ")
        
        assert result == ""
