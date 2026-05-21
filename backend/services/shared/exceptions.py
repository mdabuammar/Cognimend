"""
Custom Exceptions Module
Provides specific exceptions for better error handling across services.
"""
from typing import Optional, Dict, Any


class ServiceException(Exception):
    """Base exception for all service errors."""
    
    def __init__(
        self,
        message: str,
        code: str = "SERVICE_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None  # Alias for code
    ):
        super().__init__(message)
        self.message = message
        # Support both 'code' and 'error_code' for compatibility
        self.code = error_code if error_code is not None else code
        self.error_code = self.code  # Alias for test compatibility
        self.status_code = status_code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": self.code,
            "error_code": self.code,
            "message": self.message,
            "details": self.details,
            "type": self.__class__.__name__
        }


# ============================================================
# Database Exceptions
# ============================================================

class DatabaseError(ServiceException):
    """Base database error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, error_code: Optional[str] = None):
        # If error_code provided, add to details
        if details is None:
            details = {}
        if error_code:
            details['error_code'] = error_code
            
        super().__init__(
            message=message,
            code=error_code or "DATABASE_ERROR",
            status_code=500,
            details=details
        )


class ConnectionPoolExhausted(DatabaseError):
    """Raised when connection pool is exhausted."""
    
    def __init__(self):
        super().__init__(
            message="Database connection pool exhausted. Please try again.",
            details={"retry_after_seconds": 5}
        )


class QueryTimeout(DatabaseError):
    """Raised when a query times out."""
    
    def __init__(self, query_type: str = "unknown", timeout_seconds: int = 30):
        super().__init__(
            message=f"Query timed out after {timeout_seconds} seconds",
            details={"query_type": query_type, "timeout": timeout_seconds}
        )


class TransactionError(DatabaseError):
    """Raised when a transaction fails."""
    
    def __init__(self, operation: str, reason: str):
        super().__init__(
            message=f"Transaction failed during {operation}: {reason}",
            details={"operation": operation, "reason": reason}
        )


# ============================================================
# Document Processing Exceptions
# ============================================================

class DocumentError(ServiceException):
    """Base document error."""
    
    def __init__(
        self,
        message: str,
        code: str = "DOCUMENT_ERROR",
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, status_code, details)


class UnsupportedFileType(DocumentError):
    """Raised when file type is not supported."""
    
    def __init__(self, filename: str, supported: list):
        super().__init__(
            message=f"Unsupported file type for '{filename}'",
            code="UNSUPPORTED_FILE_TYPE",
            details={"filename": filename, "supported_types": supported}
        )


class ExtractionError(DocumentError):
    """Raised when text extraction fails."""
    
    def __init__(self, filename: str, reason: str):
        super().__init__(
            message=f"Failed to extract text from '{filename}': {reason}",
            code="EXTRACTION_ERROR",
            details={"filename": filename, "reason": reason}
        )


class EmptyDocumentError(DocumentError):
    """Raised when document has no extractable content."""
    
    def __init__(self, filename: str):
        super().__init__(
            message=f"No text content found in '{filename}'",
            code="EMPTY_DOCUMENT",
            details={"filename": filename}
        )


class FileTooLarge(DocumentError):
    """Raised when file exceeds size limit."""
    
    def __init__(self, size_bytes: int, max_size_bytes: int):
        super().__init__(
            message=f"File size ({size_bytes / (1024*1024):.1f}MB) exceeds maximum ({max_size_bytes / (1024*1024)}MB)",
            code="FILE_TOO_LARGE",
            status_code=413,
            details={
                "size_bytes": size_bytes,
                "max_size_bytes": max_size_bytes
            }
        )


class DuplicateDocument(DocumentError):
    """Raised when document already exists (for idempotency)."""
    
    def __init__(self, document_id: int, file_hash: str):
        super().__init__(
            message="Document already exists",
            code="DUPLICATE_DOCUMENT",
            status_code=409,
            details={
                "existing_document_id": document_id,
                "file_hash": file_hash
            }
        )


# ============================================================
# Query/RAG Exceptions
# ============================================================

class QueryError(ServiceException):
    """Base query error."""
    
    def __init__(
        self,
        message: str,
        code: str = "QUERY_ERROR",
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, status_code, details)


class NoDocumentsFound(QueryError):
    """Raised when no relevant documents are found."""
    
    def __init__(self, query: str, threshold: float = 0.0):
        super().__init__(
            message="No relevant documents found for your query",
            code="NO_DOCUMENTS_FOUND",
            status_code=404,
            details={
                "query_preview": query[:100],
                "similarity_threshold": threshold
            }
        )


class LowConfidenceAnswer(QueryError):
    """Raised when answer confidence is below threshold."""
    
    def __init__(self, confidence: float, threshold: float):
        super().__init__(
            message=f"Answer confidence ({confidence}%) is below threshold ({threshold}%)",
            code="LOW_CONFIDENCE",
            details={
                "confidence": confidence,
                "threshold": threshold
            }
        )


class QueryTooLong(QueryError):
    """Raised when query exceeds maximum length."""
    
    def __init__(self, length: int, max_length: int):
        super().__init__(
            message=f"Query too long ({length} chars). Maximum: {max_length} chars",
            code="QUERY_TOO_LONG",
            details={"length": length, "max_length": max_length}
        )


class EmbeddingError(QueryError):
    """Raised when embedding generation fails."""
    
    def __init__(self, reason: str, retryable: bool = True):
        super().__init__(
            message=f"Failed to generate embedding: {reason}",
            code="EMBEDDING_ERROR",
            status_code=503 if retryable else 400,
            details={"reason": reason, "retryable": retryable}
        )


class SearchError(QueryError):
    """Raised when vector search fails."""
    
    def __init__(self, reason: str, query_preview: str = ""):
        super().__init__(
            message=f"Vector search failed: {reason}",
            code="SEARCH_ERROR",
            status_code=503,
            details={"reason": reason, "query_preview": query_preview[:50]}
        )


# ============================================================
# External Service Exceptions
# ============================================================

class ExternalServiceError(ServiceException):
    """Base external service error."""
    
    def __init__(
        self,
        service_name: str,
        message: str,
        code: str = "EXTERNAL_SERVICE_ERROR",
        status_code: int = 503,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["service"] = service_name
        super().__init__(message, code, status_code, details)


class EmbeddingServiceError(ExternalServiceError):
    """Raised when embedding service fails."""
    
    def __init__(self, reason: str, retryable: bool = True):
        super().__init__(
            service_name="embedding",
            message=f"Embedding service error: {reason}",
            code="EMBEDDING_ERROR",
            details={"reason": reason, "retryable": retryable}
        )


class LLMServiceError(ExternalServiceError):
    """Raised when LLM service fails."""
    
    def __init__(self, reason: str, model: str = "unknown"):
        super().__init__(
            service_name="llm",
            message=f"LLM service error: {reason}",
            code="LLM_ERROR",
            details={"reason": reason, "model": model}
        )


class VectorStoreError(ExternalServiceError):
    """Raised when vector store (Qdrant) fails."""
    
    def __init__(self, operation: str, reason: str):
        super().__init__(
            service_name="qdrant",
            message=f"Vector store error during {operation}: {reason}",
            code="VECTOR_STORE_ERROR",
            details={"operation": operation, "reason": reason}
        )


class CacheError(ExternalServiceError):
    """Raised when cache (Redis) fails."""
    
    def __init__(self, operation: str, reason: str):
        super().__init__(
            service_name="redis",
            message=f"Cache error during {operation}: {reason}",
            code="CACHE_ERROR",
            status_code=500,
            details={"operation": operation, "reason": reason}
        )


# ============================================================
# Circuit Breaker Exceptions
# ============================================================

class CircuitBreakerOpen(ServiceException):
    """Raised when circuit breaker is open."""
    
    def __init__(self, service_name: str, recovery_time_seconds: int):
        super().__init__(
            message=f"Service '{service_name}' is temporarily unavailable",
            code="CIRCUIT_BREAKER_OPEN",
            status_code=503,
            details={
                "service": service_name,
                "retry_after_seconds": recovery_time_seconds
            }
        )


# ============================================================
# Configuration Exceptions
# ============================================================

class ConfigurationError(ServiceException):
    """Base configuration error."""
    
    def __init__(
        self,
        message: str,
        code: str = "CONFIG_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, 500, details)


class ConfigNotFound(ConfigurationError):
    """Raised when configuration key is not found."""
    
    def __init__(self, config_key: str):
        super().__init__(
            message=f"Configuration '{config_key}' not found",
            code="CONFIG_NOT_FOUND",
            details={"config_key": config_key}
        )


class ConfigVersionConflict(ConfigurationError):
    """Raised when configuration version conflict occurs."""
    
    def __init__(self, config_key: str, expected_version: int, actual_version: int):
        super().__init__(
            message=f"Configuration '{config_key}' was modified by another process",
            code="CONFIG_VERSION_CONFLICT",
            details={
                "config_key": config_key,
                "expected_version": expected_version,
                "actual_version": actual_version
            }
        )


# ============================================================
# Drift Detection Exceptions
# ============================================================

class DriftError(ServiceException):
    """Base drift detection error."""
    
    def __init__(
        self,
        message: str,
        code: str = "DRIFT_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, 500, details)


class InsufficientDataForDrift(DriftError):
    """Raised when there's not enough data for drift detection."""
    
    def __init__(self, drift_type: str, required: int, available: int):
        super().__init__(
            message=f"Insufficient data for {drift_type} detection",
            code="INSUFFICIENT_DATA",
            details={
                "drift_type": drift_type,
                "required_samples": required,
                "available_samples": available
            }
        )


# ============================================================
# Validation Exceptions
# ============================================================

class ValidationError(ServiceException):
    """Base validation error."""
    
    def __init__(
        self,
        field: str,
        message: str,
        value: Any = None
    ):
        super().__init__(
            message=f"Validation error for '{field}': {message}",
            code="VALIDATION_ERROR",
            status_code=400,
            details={
                "field": field,
                "message": message,
                "value": str(value) if value is not None else None
            }
        )


class RequiredFieldMissing(ValidationError):
    """Raised when a required field is missing."""
    
    def __init__(self, field: str):
        super().__init__(
            field=field,
            message="This field is required"
        )


class InvalidFieldValue(ValidationError):
    """Raised when a field value is invalid."""
    
    def __init__(self, field: str, value: Any, reason: str):
        super().__init__(
            field=field,
            message=reason,
            value=value
        )


# ============================================================
# Aliases for Test Compatibility
# ============================================================

# Database aliases
QueryExecutionError = QueryTimeout


# Document aliases
class DocumentNotFoundError(DocumentError):
    """Raised when a document is not found."""
    
    def __init__(self, message_or_id: Any = None, message: str = None, details: dict = None, document_id: Any = None):
        """
        Initialize DocumentNotFoundError.
        
        Supports multiple API styles:
        - Legacy: DocumentNotFoundError("message", details={"document_id": 123})
        - New: DocumentNotFoundError(document_id=123)
        - Positional new: DocumentNotFoundError(123)  # where 123 is an int
        """
        # Determine if first arg is a message (string) or document_id (int/other)
        if message_or_id is not None:
            if isinstance(message_or_id, str):
                # First arg is a message string (legacy API)
                final_message = message_or_id
                final_details = details if details else {}
            else:
                # First arg is a document_id (new API with positional arg)
                final_message = f"Document not found: {message_or_id}"
                final_details = {"document_id": message_or_id}
        elif document_id is not None:
            # document_id keyword arg provided
            final_message = f"Document not found: {document_id}"
            final_details = {"document_id": document_id}
        elif message is not None:
            # message keyword arg provided
            final_message = message
            final_details = details if details else {}
        else:
            # No args - default message
            final_message = "Document not found"
            final_details = {}
        
        super().__init__(
            message=final_message,
            code="DOCUMENT_NOT_FOUND",
            status_code=404,
            details=final_details
        )


class DocumentParsingError(DocumentError):
    """Raised when document parsing fails."""
    
    def __init__(self, filename: str, reason: str):
        super().__init__(
            message=f"Failed to parse document '{filename}': {reason}",
            code="DOCUMENT_PARSING_ERROR",
            details={"filename": filename, "reason": reason}
        )


DocumentTooLargeError = FileTooLarge
UnsupportedFormatError = UnsupportedFileType


class ChunkingError(DocumentError):
    """Raised when document chunking fails."""
    
    def __init__(self, reason: str):
        super().__init__(
            message=f"Failed to chunk document: {reason}",
            code="CHUNKING_ERROR",
            details={"reason": reason}
        )


# Query aliases
EmbeddingGenerationError = EmbeddingError
VectorSearchError = SearchError


class AnswerGenerationError(QueryError):
    """Raised when answer generation fails."""
    
    def __init__(self, reason: str):
        super().__init__(
            message=f"Failed to generate answer: {reason}",
            code="ANSWER_GENERATION_ERROR",
            details={"reason": reason}
        )


class ContextBuildError(QueryError):
    """Raised when context building fails."""
    
    def __init__(self, reason: str):
        super().__init__(
            message=f"Failed to build context: {reason}",
            code="CONTEXT_BUILD_ERROR",
            details={"reason": reason}
        )


# External service aliases
class OpenRouterError(ExternalServiceError):
    """Raised when OpenRouter API fails."""
    
    def __init__(self, reason: str, status_code: int = 503):
        super().__init__(
            service_name="openrouter",
            message=f"OpenRouter API error: {reason}",
            code="OPENROUTER_ERROR",
            status_code=status_code,
            details={"reason": reason}
        )


class QdrantError(ExternalServiceError):
    """Raised when Qdrant fails."""
    
    def __init__(self, operation: str, reason: str):
        super().__init__(
            service_name="qdrant",
            message=f"Qdrant error during {operation}: {reason}",
            code="QDRANT_ERROR",
            details={"operation": operation, "reason": reason}
        )


class RedisError(ExternalServiceError):
    """Raised when Redis fails."""
    
    def __init__(self, operation: str, reason: str):
        super().__init__(
            service_name="redis",
            message=f"Redis error during {operation}: {reason}",
            code="REDIS_ERROR",
            details={"operation": operation, "reason": reason}
        )


class RateLimitError(ExternalServiceError):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, service: str, retry_after: int = 60):
        super().__init__(
            service_name=service,
            message=f"Rate limit exceeded for {service}. Retry after {retry_after}s",
            code="RATE_LIMIT_ERROR",
            status_code=429,
            details={"retry_after": retry_after}
        )


class TimeoutError(ExternalServiceError):
    """Raised when a service times out."""
    
    def __init__(self, service: str, timeout_seconds: int):
        super().__init__(
            service_name=service,
            message=f"Service {service} timed out after {timeout_seconds}s",
            code="TIMEOUT_ERROR",
            status_code=504,
            details={"timeout_seconds": timeout_seconds}
        )


# Circuit breaker
class CircuitBreakerOpen(ServiceException):
    """Raised when circuit breaker is open."""
    
    def __init__(self, service: str, retry_after: int = 30):
        super().__init__(
            message=f"Circuit breaker open for {service}. Service temporarily unavailable.",
            code="CIRCUIT_BREAKER_OPEN",
            status_code=503,
            details={"service": service, "retry_after": retry_after}
        )


# Configuration
class ConfigurationError(ServiceException):
    """Base configuration error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            status_code=500,
            details=details
        )


class MissingConfigError(ConfigurationError):
    """Raised when a required configuration is missing."""
    
    def __init__(self, config_key: str):
        super().__init__(
            message=f"Missing required configuration: {config_key}",
            details={"config_key": config_key}
        )


class InvalidConfigError(ConfigurationError):
    """Raised when a configuration value is invalid."""
    
    def __init__(self, config_key: str, value: Any, reason: str):
        super().__init__(
            message=f"Invalid configuration for {config_key}: {reason}",
            details={"config_key": config_key, "value": str(value), "reason": reason}
        )


# Authentication
class AuthenticationError(ServiceException):
    """Raised when authentication fails."""
    
    def __init__(self, reason: str = "Authentication failed"):
        super().__init__(
            message=reason,
            code="AUTHENTICATION_ERROR",
            status_code=401,
            details={"reason": reason}
        )


class AuthorizationError(ServiceException):
    """Raised when authorization fails."""
    
    def __init__(self, resource: str, action: str):
        super().__init__(
            message=f"Not authorized to {action} on {resource}",
            code="AUTHORIZATION_ERROR",
            status_code=403,
            details={"resource": resource, "action": action}
        )


# Additional validation aliases
InvalidInputError = InvalidFieldValue
MissingFieldError = RequiredFieldMissing


class TypeMismatchError(ValidationError):
    """Raised when a value has incorrect type."""
    
    def __init__(self, field: str, expected_type: str, actual_type: str):
        super().__init__(
            field=field,
            message=f"Expected type {expected_type}, got {actual_type}",
            value=actual_type
        )
