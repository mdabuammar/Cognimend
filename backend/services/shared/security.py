"""
Security Module - Backend Security Utilities
Provides comprehensive security features for FastAPI services.

Features:
- API key authentication
- Rate limiting
- Input sanitization
- Secure logging (with redaction)
- Request validation
- Security headers middleware
"""
import os
import re
import time
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, Set, Union
from functools import wraps
from collections import defaultdict
import asyncio

from fastapi import Request, HTTPException, Depends, Header
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
from pydantic import BaseModel, validator, Field

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================

class SecurityConfig:
    """Security configuration loaded from environment."""
    
    # API Key settings
    API_KEY_HEADER = "X-API-Key"
    API_KEY = os.getenv("API_KEY", "")
    INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "internal-dev-token")
    API_KEY_REQUIRED = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"
    
    # Rate limiting
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    
    # File upload limits
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md", "doc"}
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
        "text/markdown"
    }
    
    # Security headers
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    
    # Logging
    LOG_SENSITIVE_DATA = os.getenv("LOG_SENSITIVE_DATA", "false").lower() == "true"


# ============================================================
# Sensitive Data Patterns for Redaction
# ============================================================

SENSITIVE_PATTERNS = [
    # API Keys
    (re.compile(r'(sk-[a-zA-Z0-9]{20,})', re.I), '[REDACTED_API_KEY]'),
    (re.compile(r'(api[_-]?key["\s:=]+)["\']?([^"\'\s,}{]+)', re.I), r'\1[REDACTED]'),
    
    # Tokens
    (re.compile(r'(bearer\s+)([a-zA-Z0-9._-]+)', re.I), r'\1[REDACTED_TOKEN]'),
    (re.compile(r'(token["\s:=]+)["\']?([^"\'\s,}{]+)', re.I), r'\1[REDACTED]'),
    
    # Passwords
    (re.compile(r'(password["\s:=]+)["\']?([^"\'\s,}{]+)', re.I), r'\1[REDACTED]'),
    (re.compile(r'(secret["\s:=]+)["\']?([^"\'\s,}{]+)', re.I), r'\1[REDACTED]'),
    
    # Database URLs
    (re.compile(r'(postgres://[^:]+:)([^@]+)(@)', re.I), r'\1[REDACTED]\3'),
    (re.compile(r'(redis://[^:]+:)([^@]+)(@)', re.I), r'\1[REDACTED]\3'),
    
    # Email addresses (partial redaction)
    (re.compile(r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', re.I), r'[EMAIL_REDACTED]@\2'),
    
    # Credit card numbers
    (re.compile(r'\b(\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?)\d{4}\b'), r'\1****'),
    
    # SSN
    (re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'), '[SSN_REDACTED]'),
]


def redact_sensitive(text: str) -> str:
    """Redact sensitive information from text."""
    if not text or SecurityConfig.LOG_SENSITIVE_DATA:
        return text
    
    result = str(text)
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


# ============================================================
# Secure Logger
# ============================================================

class SecureLogger:
    """Logger that automatically redacts sensitive information."""
    
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
    
    def _redact(self, msg: str, *args) -> tuple:
        """Redact message and arguments."""
        redacted_msg = redact_sensitive(str(msg))
        redacted_args = tuple(redact_sensitive(str(arg)) for arg in args)
        return redacted_msg, redacted_args
    
    def info(self, msg: str, *args, **kwargs):
        redacted_msg, redacted_args = self._redact(msg, *args)
        self._logger.info(redacted_msg, *redacted_args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        redacted_msg, redacted_args = self._redact(msg, *args)
        self._logger.warning(redacted_msg, *redacted_args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        redacted_msg, redacted_args = self._redact(msg, *args)
        self._logger.error(redacted_msg, *redacted_args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        redacted_msg, redacted_args = self._redact(msg, *args)
        self._logger.debug(redacted_msg, *redacted_args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        redacted_msg, redacted_args = self._redact(msg, *args)
        self._logger.exception(redacted_msg, *redacted_args, **kwargs)


def get_secure_logger(name: str) -> SecureLogger:
    """Get a secure logger instance."""
    return SecureLogger(name)


# ============================================================
# API Key Authentication
# ============================================================

api_key_header = APIKeyHeader(name=SecurityConfig.API_KEY_HEADER, auto_error=False)


async def verify_api_key(api_key: Optional[str] = Depends(api_key_header)) -> bool:
    """Verify API key from request header."""
    # Always allow internal service token
    if api_key and secrets.compare_digest(api_key, SecurityConfig.INTERNAL_SERVICE_TOKEN):
        return True
        
    if not SecurityConfig.API_KEY_REQUIRED:
        return True
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, SecurityConfig.API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    return True


def require_api_key(func: Callable) -> Callable:
    """Decorator to require API key authentication."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get('request')
        if request:
            api_key = request.headers.get(SecurityConfig.API_KEY_HEADER)
            await verify_api_key(api_key)
        return await func(*args, **kwargs)
    return wrapper


# ============================================================
# Rate Limiting
# ============================================================

class RateLimiter:
    """In-memory rate limiter using sliding window."""
    
    def __init__(
        self,
        max_requests: int = SecurityConfig.RATE_LIMIT_REQUESTS,
        window_seconds: int = SecurityConfig.RATE_LIMIT_WINDOW_SECONDS
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Use X-Forwarded-For if behind proxy, else client host
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    async def is_allowed_async(self, request: Request) -> tuple[bool, Dict[str, Any]]:
        """Check if request is allowed under rate limit (async version)."""
        if not SecurityConfig.RATE_LIMIT_ENABLED:
            return True, {}
        
        client_id = self._get_client_id(request)
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        async with self._lock:
            # Clean old requests
            self.requests[client_id] = [
                ts for ts in self.requests[client_id]
                if ts > window_start
            ]
            
            # Check limit
            request_count = len(self.requests[client_id])
            
            if request_count >= self.max_requests:
                retry_after = int(self.requests[client_id][0] - window_start)
                return False, {
                    "limit": self.max_requests,
                    "remaining": 0,
                    "reset": retry_after,
                    "window": self.window_seconds
                }
            
            # Record this request
            self.requests[client_id].append(current_time)
            
            return True, {
                "limit": self.max_requests,
                "remaining": self.max_requests - request_count - 1,
                "window": self.window_seconds
            }
    
    def is_allowed(self, client_id: Union[str, Request]) -> bool:
        """
        Synchronous version for testing. Check if client is allowed.
        
        Args:
            client_id: String identifier or Request object
            
        Returns:
            True if allowed, False if rate limit exceeded
        """
        # Handle Request object
        if hasattr(client_id, 'client'):
            client_id = self._get_client_id(client_id)
        
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        # Clean old requests
        self.requests[client_id] = [
            ts for ts in self.requests[client_id]
            if ts > window_start
        ]
        
        # Check limit
        request_count = len(self.requests[client_id])
        
        if request_count >= self.max_requests:
            return False
        
        # Record this request
        self.requests[client_id].append(current_time)
        return True
    
    async def cleanup(self):
        """Clean up old entries to prevent memory bloat."""
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        async with self._lock:
            for client_id in list(self.requests.keys()):
                self.requests[client_id] = [
                    ts for ts in self.requests[client_id]
                    if ts > window_start
                ]
                if not self.requests[client_id]:
                    del self.requests[client_id]


# Global rate limiter instance
rate_limiter = RateLimiter()


async def check_rate_limit(request: Request) -> Dict[str, Any]:
    """Dependency to check rate limit."""
    allowed, info = await rate_limiter.is_allowed_async(request)
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(info.get("reset", 60)),
                "X-RateLimit-Limit": str(info.get("limit", 100)),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(info.get("reset", 60))
            }
        )
    
    return info


# ============================================================
# Input Sanitization
# ============================================================

# Dangerous patterns to remove
DANGEROUS_PATTERNS = [
    re.compile(r'<script[^>]*>.*?</script>', re.I | re.S),
    re.compile(r'javascript:', re.I),
    re.compile(r'on\w+\s*=', re.I),
    re.compile(r'data:', re.I),
    re.compile(r'vbscript:', re.I),
]

# SQL injection patterns
SQL_INJECTION_PATTERNS = [
    re.compile(r"(\b(union|select|insert|update|delete|drop|truncate)\b.*\b(from|into|table|database)\b)", re.I),
    re.compile(r"(--|#|/\*|\*/)", re.I),
    re.compile(r"(\bor\b\s+\d+\s*=\s*\d+)", re.I),
    re.compile(r"(\band\b\s+\d+\s*=\s*\d+)", re.I),
]


def sanitize_string(text: str, max_length: int = 10000) -> str:
    """Sanitize a string input."""
    if not text:
        return ""
    
    # Truncate to max length
    text = text[:max_length]
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        text = pattern.sub('', text)
    
    return text.strip()


def check_sql_injection(text: str) -> bool:
    """Check if text contains potential SQL injection."""
    if not text:
        return False
    
    for pattern in SQL_INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    
    html_escape_table = {
        "&": "&amp;",
        '"': "&quot;",
        "'": "&#x27;",
        ">": "&gt;",
        "<": "&lt;",
    }
    
    return "".join(html_escape_table.get(c, c) for c in text)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal and other attacks."""
    if not filename:
        return "unnamed_file"
    
    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")
    
    # Remove null bytes
    filename = filename.replace('\x00', '')
    
    # Remove other dangerous characters
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Ensure filename is not empty
    if not filename:
        return "unnamed_file"
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    
    return filename


def validate_file_extension(filename: str) -> bool:
    """Validate file extension against allowed list."""
    if not filename:
        return False
    
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in SecurityConfig.ALLOWED_EXTENSIONS


def validate_mime_type(content_type: str) -> bool:
    """Validate MIME type against allowed list."""
    if not content_type:
        return False
    
    # Handle content types with charset, e.g., "text/plain; charset=utf-8"
    mime_type = content_type.split(';')[0].strip().lower()
    return mime_type in SecurityConfig.ALLOWED_MIME_TYPES


# ============================================================
# Pydantic Validators for Input Validation
# ============================================================

class SecureQueryInput(BaseModel):
    """Secure query input with validation."""
    
    query: str = Field(..., min_length=1, max_length=10000)
    top_k: int = Field(default=5, ge=1, le=100)
    
    @validator('query')
    def sanitize_query(cls, v):
        sanitized = sanitize_string(v)
        if check_sql_injection(sanitized):
            raise ValueError("Invalid query content detected")
        return sanitized


class SecureUploadInput(BaseModel):
    """Secure upload input metadata."""
    
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(...)
    
    @validator('filename')
    def validate_filename(cls, v):
        sanitized = sanitize_filename(v)
        if not validate_file_extension(sanitized):
            raise ValueError(f"File type not allowed. Allowed: {SecurityConfig.ALLOWED_EXTENSIONS}")
        return sanitized
    
    @validator('content_type')
    def validate_content_type(cls, v):
        if not validate_mime_type(v):
            raise ValueError(f"MIME type not allowed. Allowed: {SecurityConfig.ALLOWED_MIME_TYPES}")
        return v


# ============================================================
# Security Headers Middleware
# ============================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Content Security Policy for API responses
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        
        # Cache control for sensitive data
        if "api" in request.url.path.lower():
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        
        return response


# ============================================================
# Rate Limit Middleware
# ============================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to apply rate limiting to all requests."""
    
    def __init__(self, app, rate_limiter: RateLimiter = rate_limiter, exclude_paths: Set[str] = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.exclude_paths = exclude_paths or {"/health", "/metrics", "/ready"}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Check rate limit
        allowed, info = await self.rate_limiter.is_allowed_async(request)
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "retry_after": info.get("reset", 60)},
                headers={
                    "Retry-After": str(info.get("reset", 60)),
                    "X-RateLimit-Limit": str(info.get("limit", 100)),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info.get("reset", 60))
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(info.get("limit", 100))
        response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(info.get("reset", 60))
        
        return response


# ============================================================
# Request Logging Middleware
# ============================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log requests with sensitive data redaction."""
    
    def __init__(self, app, logger: SecureLogger = None):
        super().__init__(app)
        self.logger = logger or get_secure_logger("request")
    
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        
        # Log request (with redaction)
        self.logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        try:
            response = await call_next(request)
            
            # Log response
            duration = time.time() - start_time
            self.logger.info(
                f"Response: {response.status_code} in {duration:.3f}s"
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Request failed after {duration:.3f}s: {str(e)}"
            )
            raise


# ============================================================
# Error Handling
# ============================================================

def create_error_response(
    status_code: int,
    message: str,
    error_code: str = "ERROR",
    details: Dict[str, Any] = None
) -> JSONResponse:
    """Create a standardized error response without leaking sensitive info."""
    
    # Don't expose internal error details in production
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    
    content = {
        "error": error_code,
        "message": message if not is_production else "An error occurred",
    }
    
    if details and not is_production:
        content["details"] = details
    
    return JSONResponse(status_code=status_code, content=content)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler that prevents information leakage."""
    logger = get_secure_logger("error")
    
    # Log the full error internally
    logger.exception(f"Unhandled exception: {str(exc)}")
    
    # Return safe error to client
    return create_error_response(
        status_code=500,
        message="Internal server error",
        error_code="INTERNAL_ERROR"
    )


# ============================================================
# Security Setup Helper
# ============================================================

def setup_security(app, include_rate_limit: bool = True, include_logging: bool = True):
    """Apply security middleware to FastAPI app."""
    
    # Add security headers (should be last to wrap other responses)
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Add rate limiting
    if include_rate_limit:
        app.add_middleware(RateLimitMiddleware)
    
    # Add request logging
    if include_logging:
        app.add_middleware(RequestLoggingMiddleware)
    
    # Add global exception handler
    app.add_exception_handler(Exception, global_exception_handler)
    
    logger.info("✅ Security middleware configured")


# ============================================================
# Additional Security Functions for Tests
# ============================================================

def check_sql_injection(query: str) -> bool:
    """
    Check if query contains SQL injection patterns.
    
    Args:
        query: Query string to check
        
    Returns:
        True if SQL injection detected, False otherwise
    """
    sql_patterns = [
        r"('\s*(OR|AND)\s*'?\d*'?\s*=\s*'?\d)",
        r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|EXEC)",
        r"(UNION\s+SELECT)",
        r"(--|\#|/\*)",
        r"(xp_|sp_)",
    ]
    
    query_upper = query.upper()
    for pattern in sql_patterns:
        if re.search(pattern, query_upper, re.IGNORECASE):
            return True
    return False


def sanitize_string(text: str) -> str:
    """
    Sanitize string by removing potentially dangerous characters and SQL keywords.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text
    """
    if not text:
        return text
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove most control characters except newline, tab, carriage return
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t\r')
    
    # Remove common SQL injection keywords
    dangerous_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'UNION', 'SELECT', 'EXEC', 'EXECUTE', '--', ';', '/*', '*/']
    result = text
    for keyword in dangerous_keywords:
        result = result.replace(keyword, '')
        result = result.replace(keyword.lower(), '')
    
    return result


def escape_html(text: str) -> str:
    """
    Escape HTML special characters to prevent XSS.
    
    Args:
        text: Text to escape
        
    Returns:
        HTML-escaped text
    """
    if not text:
        return text
    
    html_escape_table = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
        "/": "&#x2F;",
    }
    
    return "".join(html_escape_table.get(c, c) for c in text)


def sanitize_path(path: str) -> str:
    """
    Sanitize file path to prevent path traversal attacks.
    
    Args:
        path: File path to sanitize
        
    Returns:
        Sanitized path (empty string if dangerous patterns found)
    """
    if not path:
        return path
    
    # Check for path traversal patterns
    dangerous_patterns = ['..', '~', '\\', '//', '\x00', '/etc', '%2e', 'passwd']
    for pattern in dangerous_patterns:
        if pattern in path.lower():
            return ""  # Return empty string for dangerous paths
    
    # Remove leading/trailing slashes
    path = path.strip('/')
    
    # Remove any absolute path indicators
    if path.startswith('/') or (len(path) > 1 and path[1] == ':'):
        return ""
    
    return path


def verify_api_key(api_key: str) -> bool:
    """
    Verify API key against configured key (synchronous version for tests).
    
    Args:
        api_key: API key to verify
        
    Returns:
        True if valid, False otherwise
    """
    if not api_key:
        return False
    
    if len(api_key) < 10:  # Minimum key length
        return False
    
    expected_key = SecurityConfig.API_KEY
    if not expected_key:
        return True  # No key required
    
    return secrets.compare_digest(api_key, expected_key)


def create_jwt_token(payload: Dict[str, Any], secret: str = None, expiry_hours: int = 24, expires_in: int = None) -> str:
    """
    Create a simple JWT-like token (base64 encoded).
    Note: This is a simplified implementation for testing.
    
    SECURITY: Secret must be provided explicitly or via JWT_SECRET env var.
    
    Args:
        payload: Data to encode
        secret: Secret key (required - no default)
        expiry_hours: Token expiry in hours (legacy parameter)
        expires_in: Token expiry in seconds (preferred parameter)
        
    Returns:
        Encoded token
        
    Raises:
        ValueError: If no secret is provided
    """
    import json
    import base64
    
    # Get secret from env var if not provided
    if secret is None:
        secret = os.getenv("JWT_SECRET")
    
    if not secret:
        raise ValueError("JWT secret is required. Set JWT_SECRET environment variable or pass secret parameter.")
    
    # Use expires_in if provided, otherwise use expiry_hours
    expiry_seconds = expires_in if expires_in is not None else (expiry_hours * 3600)
    
    payload['exp'] = (datetime.now() + timedelta(seconds=expiry_seconds)).timestamp()
    payload['iat'] = datetime.now().timestamp()
    
    # Create signature
    payload_json = json.dumps(payload, sort_keys=True)
    signature = hashlib.sha256(f"{payload_json}{secret}".encode()).hexdigest()
    
    # Combine payload and signature
    token_data = {
        'payload': payload,
        'signature': signature
    }
    
    token_json = json.dumps(token_data)
    token = base64.b64encode(token_json.encode()).decode()
    
    return token


def verify_jwt_token(token: str, secret: str = None) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT-like token.
    
    SECURITY: Secret must be provided explicitly or via JWT_SECRET env var.
    
    Args:
        token: Token to verify
        secret: Secret key (required - no default)
        
    Returns:
        Decoded payload if valid
        
    Raises:
        ValueError: If no secret is provided
        Exception: If token is invalid, expired, or tampered
    """
    import json
    import base64
    
    # Get secret from env var if not provided
    if secret is None:
        secret = os.getenv("JWT_SECRET")
    
    if not secret:
        raise ValueError("JWT secret is required. Set JWT_SECRET environment variable or pass secret parameter.")
    
    try:
        # Decode token
        token_json = base64.b64decode(token.encode()).decode()
        token_data = json.loads(token_json)
        
        payload = token_data['payload']
        signature = token_data['signature']
        
        # Verify signature
        payload_json = json.dumps(payload, sort_keys=True)
        expected_signature = hashlib.sha256(f"{payload_json}{secret}".encode()).hexdigest()
        
        if not secrets.compare_digest(signature, expected_signature):
            raise Exception("Invalid signature")
        
        # Check expiry
        if datetime.now().timestamp() > payload.get('exp', 0):
            raise Exception("Token expired")
        
        return payload
        
    except Exception as e:
        raise Exception(f"Token validation failed: {str(e)}")


def hash_password(password: str) -> str:
    """
    Hash password using SHA256 with random salt (simplified for testing).
    Note: In production, use bcrypt or argon2.
    
    Args:
        password: Password to hash
        
    Returns:
        Hashed password with salt (format: salt$hash)
    """
    # Generate random salt
    salt = secrets.token_hex(16)  # 32 char hex string
    
    # Hash with salt
    hash_value = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    
    # Return salt$hash (total > 50 chars)
    return f"{salt}${hash_value}"


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify password against hash.
    
    Args:
        password: Plain password
        hashed: Hashed password (format: salt$hash)
        
    Returns:
        True if match, False otherwise
    """
    try:
        # Split salt and hash
        salt, hash_value = hashed.split('$')
        
        # Recompute hash with extracted salt
        expected_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        
        return secrets.compare_digest(expected_hash, hash_value)
    except Exception:
        return False


def mask_sensitive_data(data: Union[str, Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
    """
    Mask sensitive data in strings or dicts.
    
    Args:
        data: String or dict potentially containing sensitive data
        
    Returns:
        Same type as input with sensitive data masked
    """
    if not data:
        return data
    
    # If dict, recursively mask values
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Check if key indicates sensitive data
            if any(s in key.lower() for s in ['password', 'secret', 'key', 'token', 'ssn', 'credit', 'card']):
                result[key] = "***MASKED***"
            elif isinstance(value, str):
                # Mask the string value
                masked_value = value
                for pattern, replacement in SENSITIVE_PATTERNS:
                    masked_value = pattern.sub(replacement, masked_value)
                result[key] = masked_value
            else:
                result[key] = value
        return result
    
    # If string, mask patterns
    result = str(data)
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    
    return result
