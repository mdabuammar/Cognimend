"""
Shared Utilities Module
Eliminates code duplication across all services.
"""
import os
import logging
from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE UTILITIES
# ============================================================

def get_db_fallback() -> psycopg2.extensions.connection:
    """
    Get database connection when pool is unavailable.
    
    This is a fallback for when shared modules aren't loaded.
    Prefer using db_pool.get_connection() when available.
    
    Returns:
        psycopg2 connection object
        
    Raises:
        psycopg2.OperationalError: If connection fails
    """
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "cognimend"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        connect_timeout=5
    )


class DatabaseManager:
    """
    Unified database connection manager.
    
    Provides a consistent interface for database operations
    whether using connection pooling or fallback connections.
    """
    
    def __init__(self, pool: Optional[Any] = None):
        """
        Initialize database manager.
        
        Args:
            pool: Optional database pool (from shared.database)
        """
        self._pool = pool
    
    def get_connection(self) -> psycopg2.extensions.connection:
        """
        Get a database connection.
        
        Returns:
            Database connection from pool or fallback
        """
        if self._pool is not None:
            return self._pool.get_connection()
        return get_db_fallback()
    
    def return_connection(self, conn: psycopg2.extensions.connection) -> None:
        """
        Return connection to pool or close it.
        
        Args:
            conn: Connection to return/close
        """
        if self._pool is not None:
            self._pool.return_connection(conn)
        else:
            try:
                conn.close()
            except Exception:
                pass
    
    def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None,
        fetch: str = "all"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: "all", "one", or "none"
            
        Returns:
            Query results or None
        """
        conn = self.get_connection()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(query, params)
            
            if fetch == "all":
                result = cur.fetchall()
            elif fetch == "one":
                result = cur.fetchone()
            else:
                result = None
                conn.commit()
            
            cur.close()
            return result
        finally:
            self.return_connection(conn)
    
    def execute_write(
        self,
        query: str,
        params: Optional[tuple] = None,
        returning: bool = False
    ) -> Optional[Any]:
        """
        Execute a write operation (INSERT, UPDATE, DELETE).
        
        Args:
            query: SQL query string
            params: Query parameters
            returning: Whether to return the result
            
        Returns:
            Result if returning=True, else None
        """
        conn = self.get_connection()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(query, params)
            
            result = None
            if returning:
                result = cur.fetchone()
            
            conn.commit()
            cur.close()
            return result
        except Exception as e:
            conn.rollback()
            raise
        finally:
            self.return_connection(conn)


# ============================================================
# HEALTH CHECK FACTORY
# ============================================================

class HealthCheckBuilder:
    """
    Factory for creating consistent health check endpoints.
    
    Ensures all services have the same health check structure.
    """
    
    def __init__(self, service_name: str, version: str = "2.0.0"):
        """
        Initialize health check builder.
        
        Args:
            service_name: Name of the service
            version: Service version
        """
        self.service_name = service_name
        self.version = version
        self._checks: Dict[str, Callable[[], Awaitable[str]]] = {}
        self._components: Dict[str, tuple[bool, str]] = {}  # name -> (healthy, message)
    
    def add_component(self, name: str, healthy: bool, message: str = "") -> 'HealthCheckBuilder':
        """Add a component status check.
        
        Args:
            name: Component name
            healthy: Whether component is healthy
            message: Status message
            
        Returns:
            Self for chaining
        """
        self._components[name] = (healthy, message)
        return self
    
    def add_database_check(self, db_manager: DatabaseManager) -> 'HealthCheckBuilder':
        """Add database health check."""
        async def check() -> str:
            try:
                conn = db_manager.get_connection()
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                db_manager.return_connection(conn)
                return "healthy"
            except Exception as e:
                return f"unhealthy: {str(e)[:50]}"
        
        self._checks["database"] = check
        return self
    
    def add_redis_check(self, cache: Optional[Any]) -> 'HealthCheckBuilder':
        """Add Redis health check."""
        async def check() -> str:
            if cache is None:
                return "disabled"
            return "healthy" if cache.is_available() else "unhealthy"
        
        self._checks["redis"] = check
        return self
    
    def add_qdrant_check(self, qdrant_client: Optional[Any]) -> 'HealthCheckBuilder':
        """Add Qdrant health check."""
        async def check() -> str:
            if qdrant_client is None:
                return "disabled"
            try:
                qdrant_client.get_collections()
                return "healthy"
            except Exception as e:
                return f"unhealthy: {str(e)[:50]}"
        
        self._checks["qdrant"] = check
        return self
    
    def add_openrouter_check(self, client: Optional[Any]) -> 'HealthCheckBuilder':
        """Add OpenRouter health check."""
        async def check() -> str:
            return "healthy" if client is not None else "disabled"
        
        self._checks["openrouter"] = check
        return self
    
    def add_external_service_check(
        self,
        name: str,
        url: str,
        timeout: int = 5
    ) -> 'HealthCheckBuilder':
        """Add external service health check."""
        import requests
        
        async def check() -> str:
            try:
                response = requests.get(f"{url}/health", timeout=timeout)
                return "healthy" if response.status_code == 200 else "unhealthy"
            except Exception as e:
                return f"unhealthy: {str(e)[:50]}"
        
        self._checks[name] = check
        return self
    
    def add_custom_check(
        self,
        name: str,
        check_fn: Callable[[], Awaitable[str]]
    ) -> 'HealthCheckBuilder':
        """Add custom health check."""
        self._checks[name] = check_fn
        return self
    
    async def build_async(self) -> Dict[str, Any]:
        """
        Execute all health checks and return results (async version).
        
        Returns:
            Health check response dictionary
        """
        components = {"service": "healthy"}
        
        for name, check_fn in self._checks.items():
            try:
                components[name] = await check_fn()
            except Exception as e:
                components[name] = f"error: {str(e)[:50]}"
        
        # Add component statuses
        for name, (healthy, message) in self._components.items():
            components[name] = message if message else ("healthy" if healthy else "unhealthy")
        
        # Determine overall status
        statuses = list(components.values())
        if any("unhealthy" in str(s) or "error" in str(s) for s in statuses):
            overall = "degraded"
        else:
            overall = "healthy"
        
        return {
            "status": overall,
            "service": self.service_name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "components": components
        }
    
    def build(self) -> Dict[str, Any]:
        """Build health check response (synchronous, for tests).
        
        Returns:
            Health check dictionary
        """
        results = {}
        
        # Add component statuses
        for name, (healthy, message) in self._components.items():
            results[name] = message if message else ("healthy" if healthy else "unhealthy")
        
        # Determine overall status
        all_healthy = all(
            status in ["healthy", "disabled", "connected", "available"] 
            for status in results.values()
        )
        any_unhealthy = any(
            "unhealthy" in str(status).lower() or "refused" in str(status).lower()
            for status in results.values()
        )
        
        status = "healthy" if all_healthy else ("degraded" if any_unhealthy else "healthy")
        
        return {
            "status": status,
            "service": self.service_name,
            "version": self.version,
            "checks": results
        }


# ============================================================
# LOGGING UTILITIES
# ============================================================

def setup_logging(service_name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Setup consistent logging across services.
    
    Args:
        service_name: Name of the service for logger
        level: Logging level
        
    Returns:
        Configured logger instance
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(service_name)


class ServiceLogger:
    """Enhanced logger with structured logging support."""
    
    def __init__(self, service_name: str):
        self.logger = logging.getLogger(service_name)
        self.service_name = service_name
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info with optional structured data."""
        self.logger.info(self._format_message(message, kwargs))
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning with optional structured data."""
        self.logger.warning(self._format_message(message, kwargs))
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error with optional structured data."""
        self.logger.error(self._format_message(message, kwargs))
    
    def _format_message(self, message: str, data: Dict[str, Any]) -> str:
        """Format message with structured data."""
        if data:
            data_str = " ".join(f"{k}={v}" for k, v in data.items())
            return f"{message} | {data_str}"
        return message


# ============================================================
# DATETIME UTILITIES
# ============================================================

def datetime_to_iso(dt: Optional[datetime]) -> Optional[str]:
    """
    Convert datetime to ISO format string.
    
    Args:
        dt: Datetime object or None
        
    Returns:
        ISO format string or None
    """
    return dt.isoformat() if dt else None


def format_query_results(
    results: List[Dict[str, Any]],
    datetime_fields: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Format query results for JSON serialization.
    
    Args:
        results: List of result dictionaries
        datetime_fields: List of datetime field names to convert
        
    Returns:
        Formatted results
    """
    datetime_fields = datetime_fields or ['created_at', 'updated_at']
    
    for row in results:
        for field in datetime_fields:
            if field in row and row[field]:
                row[field] = datetime_to_iso(row[field])
    
    return results


# ============================================================
# VALIDATION UTILITIES
# ============================================================

def validate_pagination(
    limit: int,
    offset: int = 0,
    max_limit: int = 100
) -> tuple[int, int]:
    """
    Validate and normalize pagination parameters.
    
    Args:
        limit: Requested limit
        offset: Requested offset
        max_limit: Maximum allowed limit
        
    Returns:
        Tuple of (validated_limit, validated_offset)
    """
    validated_limit = min(max(1, limit), max_limit)
    validated_offset = max(0, offset)
    return validated_limit, validated_offset


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitize string input.
    
    Args:
        value: Input string
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not value:
        return ""
    return value.strip()[:max_length]
