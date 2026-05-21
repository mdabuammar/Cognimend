"""
Correlation ID Middleware for Distributed Tracing
Ensures all requests have consistent trace IDs across services.
"""
import uuid
import logging
from typing import Callable, Optional
from contextvars import ContextVar
from functools import wraps

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Context variables for request tracking
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
span_id_var: ContextVar[Optional[str]] = ContextVar('span_id', default=None)

# Header names
CORRELATION_ID_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"
SPAN_ID_HEADER = "X-Span-ID"


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID from context."""
    return correlation_id_var.get()


def get_request_id() -> Optional[str]:
    """Get current request ID from context."""
    return request_id_var.get()


def get_span_id() -> Optional[str]:
    """Get current span ID from context."""
    return span_id_var.get()


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts or generates correlation IDs for distributed tracing.
    
    Features:
    - Extracts correlation ID from incoming request headers
    - Generates new correlation ID if not present
    - Propagates correlation ID to response headers
    - Stores IDs in context for access throughout request lifecycle
    """
    
    def __init__(
        self,
        app: ASGIApp,
        header_name: str = CORRELATION_ID_HEADER,
        generator: Callable[[], str] = generate_id,
    ):
        super().__init__(app)
        self.header_name = header_name
        self.generator = generator
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate correlation ID
        correlation_id = request.headers.get(self.header_name)
        if not correlation_id:
            correlation_id = self.generator()
        
        # Extract or generate request ID (unique per request)
        request_id = request.headers.get(REQUEST_ID_HEADER)
        if not request_id:
            request_id = self.generator()
        
        # Generate span ID for this service
        span_id = self.generator()[:8]  # Short span ID
        
        # Set context variables
        correlation_id_var.set(correlation_id)
        request_id_var.set(request_id)
        span_id_var.set(span_id)
        
        # Add to request state for easy access
        request.state.correlation_id = correlation_id
        request.state.request_id = request_id
        request.state.span_id = span_id
        
        # Process request
        response = await call_next(request)
        
        # Add headers to response
        response.headers[self.header_name] = correlation_id
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACE_ID_HEADER] = correlation_id
        response.headers[SPAN_ID_HEADER] = span_id
        
        return response


class CorrelationIdLogFilter(logging.Filter):
    """
    Logging filter that adds correlation ID to all log records.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or '-'
        record.request_id = get_request_id() or '-'
        record.span_id = get_span_id() or '-'
        return True


def setup_correlation_logging():
    """
    Configure logging to include correlation IDs.
    
    Call this at application startup to enable correlation ID logging.
    """
    # Add filter to root logger
    root_logger = logging.getLogger()
    root_logger.addFilter(CorrelationIdLogFilter())
    
    # Configure log format with correlation ID
    log_format = (
        '%(asctime)s - %(name)s - %(levelname)s - '
        '[correlation_id=%(correlation_id)s request_id=%(request_id)s span_id=%(span_id)s] '
        '%(message)s'
    )
    
    formatter = logging.Formatter(log_format)
    
    # Apply to all handlers
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)


def propagate_correlation_headers(headers: dict) -> dict:
    """
    Get headers to propagate to downstream services.
    
    Call this when making HTTP requests to other services.
    
    Returns:
        dict: Headers to include in outgoing requests
    """
    propagated = {}
    
    correlation_id = get_correlation_id()
    if correlation_id:
        propagated[CORRELATION_ID_HEADER] = correlation_id
        propagated[TRACE_ID_HEADER] = correlation_id
    
    request_id = get_request_id()
    if request_id:
        propagated[REQUEST_ID_HEADER] = request_id
    
    # Generate new span ID for downstream call
    propagated[SPAN_ID_HEADER] = generate_id()[:8]
    
    # Merge with existing headers
    return {**headers, **propagated}


class CorrelatedHttpClient:
    """
    HTTP client wrapper that automatically propagates correlation headers.
    """
    
    def __init__(self, client):
        self.client = client
    
    async def get(self, url: str, **kwargs):
        headers = kwargs.pop('headers', {})
        headers = propagate_correlation_headers(headers)
        return await self.client.get(url, headers=headers, **kwargs)
    
    async def post(self, url: str, **kwargs):
        headers = kwargs.pop('headers', {})
        headers = propagate_correlation_headers(headers)
        return await self.client.post(url, headers=headers, **kwargs)
    
    async def put(self, url: str, **kwargs):
        headers = kwargs.pop('headers', {})
        headers = propagate_correlation_headers(headers)
        return await self.client.put(url, headers=headers, **kwargs)
    
    async def delete(self, url: str, **kwargs):
        headers = kwargs.pop('headers', {})
        headers = propagate_correlation_headers(headers)
        return await self.client.delete(url, headers=headers, **kwargs)


def with_correlation(func: Callable) -> Callable:
    """
    Decorator to ensure correlation context in async functions.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Ensure correlation ID exists
        if not get_correlation_id():
            correlation_id_var.set(generate_id())
        if not get_request_id():
            request_id_var.set(generate_id())
        if not get_span_id():
            span_id_var.set(generate_id()[:8])
        
        return await func(*args, **kwargs)
    
    return wrapper


# JSON log formatter for structured logging
class CorrelationJsonFormatter(logging.Formatter):
    """
    JSON formatter that includes correlation IDs in structured logs.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime
        
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, 'correlation_id', None) or get_correlation_id(),
            "request_id": getattr(record, 'request_id', None) or get_request_id(),
            "span_id": getattr(record, 'span_id', None) or get_span_id(),
            "service": "driftguard",
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        return json.dumps(log_data)


def setup_json_logging():
    """
    Configure JSON logging with correlation IDs.
    
    Ideal for log aggregation systems like Loki, ELK, etc.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add JSON handler
    handler = logging.StreamHandler()
    handler.setFormatter(CorrelationJsonFormatter())
    root_logger.addHandler(handler)
    
    # Add correlation filter
    root_logger.addFilter(CorrelationIdLogFilter())
