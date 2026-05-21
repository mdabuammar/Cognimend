"""
Tests for exceptions module - Exception hierarchy.
"""
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from services.shared.exceptions import (
    # Base
    ServiceException,
    
    # Database
    DatabaseError,
    ConnectionPoolExhausted,
    QueryExecutionError,
    TransactionError,
    
    # Document
    DocumentError,
    DocumentNotFoundError,
    DocumentParsingError,
    DocumentTooLargeError,
    UnsupportedFormatError,
    ChunkingError,
    
    # Query
    QueryError,
    EmbeddingGenerationError,
    VectorSearchError,
    AnswerGenerationError,
    ContextBuildError,
    
    # External Service
    ExternalServiceError,
    OpenRouterError,
    QdrantError,
    RedisError,
    RateLimitError,
    TimeoutError as ServiceTimeoutError,
    
    # Circuit Breaker
    CircuitBreakerOpen,
    
    # Configuration
    ConfigurationError,
    MissingConfigError,
    InvalidConfigError,
    
    # Validation
    ValidationError,
    InvalidInputError,
    MissingFieldError,
    TypeMismatchError
)


class TestServiceException:
    """Tests for base ServiceException."""
    
    def test_create_basic(self):
        """Test creating basic exception."""
        exc = ServiceException("Something went wrong")
        
        assert str(exc) == "Something went wrong"
        assert exc.message == "Something went wrong"
    
    def test_create_with_code(self):
        """Test creating exception with error code."""
        exc = ServiceException("Error", error_code="ERR_001")
        
        assert exc.error_code == "ERR_001"
    
    def test_create_with_details(self):
        """Test creating exception with details."""
        exc = ServiceException(
            "Error",
            error_code="ERR_001",
            details={"key": "value"}
        )
        
        assert exc.details["key"] == "value"
    
    def test_to_dict(self):
        """Test converting exception to dictionary."""
        exc = ServiceException(
            "Error message",
            error_code="ERR_001",
            details={"field": "test"}
        )
        
        data = exc.to_dict()
        
        assert data["message"] == "Error message"
        assert data["error_code"] == "ERR_001"
        assert data["details"]["field"] == "test"
        assert data["type"] == "ServiceException"
    
    def test_is_exception(self):
        """Test ServiceException is a proper Exception."""
        exc = ServiceException("Test")
        
        assert isinstance(exc, Exception)
        
        with pytest.raises(ServiceException):
            raise exc


class TestDatabaseErrors:
    """Tests for database-related exceptions."""
    
    def test_database_error(self):
        """Test DatabaseError."""
        exc = DatabaseError("Connection failed")
        
        assert isinstance(exc, ServiceException)
        assert "Connection failed" in str(exc)
    
    def test_connection_pool_exhausted(self):
        """Test ConnectionPoolExhausted."""
        exc = ConnectionPoolExhausted()
        
        assert isinstance(exc, DatabaseError)
    
    def test_query_execution_error(self):
        """Test QueryExecutionError."""
        exc = QueryExecutionError(query_type="SELECT", timeout_seconds=30)
        
        assert isinstance(exc, DatabaseError)
        assert exc.details["query_type"] == "SELECT"
    
    def test_transaction_error(self):
        """Test TransactionError."""
        exc = TransactionError(operation="commit", reason="Rollback occurred")
        
        assert isinstance(exc, DatabaseError)


class TestDocumentErrors:
    """Tests for document-related exceptions."""
    
    def test_document_error(self):
        """Test DocumentError base class."""
        exc = DocumentError("Document processing failed")
        
        assert isinstance(exc, ServiceException)
    
    def test_document_not_found(self):
        """Test DocumentNotFoundError."""
        exc = DocumentNotFoundError(document_id=123)
        
        assert isinstance(exc, DocumentError)
        assert exc.details["document_id"] == 123
    
    def test_document_parsing_error(self):
        """Test DocumentParsingError."""
        exc = DocumentParsingError(filename="test.pdf", reason="Invalid PDF structure")
        
        assert isinstance(exc, DocumentError)
    
    def test_document_too_large(self):
        """Test DocumentTooLargeError."""
        exc = DocumentTooLargeError(size_bytes=150*1024*1024, max_size_bytes=100*1024*1024)
        
        assert isinstance(exc, DocumentError)
    
    def test_unsupported_format(self):
        """Test UnsupportedFormatError."""
        exc = UnsupportedFormatError(filename="test.xyz", supported=[".pdf", ".docx", ".txt"])
        
        assert isinstance(exc, DocumentError)
        assert exc.details["filename"] == "test.xyz"
    
    def test_chunking_error(self):
        """Test ChunkingError."""
        exc = ChunkingError("Failed to chunk document")
        
        assert isinstance(exc, DocumentError)


class TestQueryErrors:
    """Tests for query-related exceptions."""
    
    def test_query_error(self):
        """Test QueryError base class."""
        exc = QueryError("Query processing failed")
        
        assert isinstance(exc, ServiceException)
    
    def test_embedding_generation_error(self):
        """Test EmbeddingGenerationError."""
        exc = EmbeddingGenerationError(reason="API timeout", retryable=True)
        
        assert isinstance(exc, QueryError)
    
    def test_vector_search_error(self):
        """Test VectorSearchError."""
        exc = VectorSearchError(reason="Collection not found", query_preview="test query")
        
        assert isinstance(exc, QueryError)
    
    def test_answer_generation_error(self):
        """Test AnswerGenerationError."""
        exc = AnswerGenerationError(reason="Model timeout")
        
        assert isinstance(exc, QueryError)
    
    def test_context_build_error(self):
        """Test ContextBuildError."""
        exc = ContextBuildError("Failed to build context")
        
        assert isinstance(exc, QueryError)


class TestExternalServiceErrors:
    """Tests for external service exceptions."""
    
    def test_external_service_error(self):
        """Test ExternalServiceError base class."""
        exc = ExternalServiceError(
            service_name="OpenRouter",
            message="External service unavailable"
        )
        
        assert isinstance(exc, ServiceException)
    
    def test_openrouter_error(self):
        """Test OpenRouterError."""
        exc = OpenRouterError(reason="API call failed", status_code=500)
        
        assert isinstance(exc, ExternalServiceError)
    
    def test_qdrant_error(self):
        """Test QdrantError."""
        exc = QdrantError(operation="search", reason="Vector store unavailable")
        
        assert isinstance(exc, ExternalServiceError)
    
    def test_redis_error(self):
        """Test RedisError."""
        exc = RedisError(operation="get", reason="Cache connection failed")
        
        assert isinstance(exc, ExternalServiceError)
    
    def test_rate_limit_error(self):
        """Test RateLimitError."""
        exc = RateLimitError(service="openrouter", retry_after=60)
        
        assert isinstance(exc, ExternalServiceError)
        assert exc.details["retry_after"] == 60
    
    def test_timeout_error(self):
        """Test ServiceTimeoutError."""
        exc = ServiceTimeoutError(service="embedding", timeout_seconds=30)
        
        assert isinstance(exc, ExternalServiceError)


class TestCircuitBreakerOpen:
    """Tests for CircuitBreakerOpen exception."""
    
    def test_circuit_breaker_open(self):
        """Test CircuitBreakerOpen."""
        exc = CircuitBreakerOpen(service="embedding_api", retry_after=60)
        
        assert isinstance(exc, ServiceException)
        assert exc.details["service"] == "embedding_api"


class TestConfigurationErrors:
    """Tests for configuration exceptions."""
    
    def test_configuration_error(self):
        """Test ConfigurationError base class."""
        exc = ConfigurationError("Invalid configuration")
        
        assert isinstance(exc, ServiceException)
    
    def test_missing_config_error(self):
        """Test MissingConfigError."""
        exc = MissingConfigError(config_key="OPENROUTER_API_KEY")
        
        assert isinstance(exc, ConfigurationError)
        assert exc.details["config_key"] == "OPENROUTER_API_KEY"
    
    def test_invalid_config_error(self):
        """Test InvalidConfigError."""
        exc = InvalidConfigError(
            config_key="TOP_K",
            value=-5,
            reason="must be positive integer"
        )
        
        assert isinstance(exc, ConfigurationError)


class TestValidationErrors:
    """Tests for validation exceptions."""
    
    def test_validation_error(self):
        """Test ValidationError base class."""
        exc = ValidationError(field="test_field", message="Validation failed")
        
        assert isinstance(exc, ServiceException)
    
    def test_invalid_input_error(self):
        """Test InvalidInputError."""
        exc = InvalidInputError(field="question", value="x"*1000, reason="too long")
        
        assert isinstance(exc, ValidationError)
    
    def test_missing_field_error(self):
        """Test MissingFieldError."""
        exc = MissingFieldError(field="document_id")
        
        assert isinstance(exc, ValidationError)
    
    def test_type_mismatch_error(self):
        """Test TypeMismatchError."""
        exc = TypeMismatchError(
            field="top_k",
            expected_type="int",
            actual_type="str"
        )
        
        assert isinstance(exc, ValidationError)
        assert "int" in str(exc)


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""
    
    def test_all_inherit_from_base(self):
        """Test all exceptions inherit from ServiceException."""
        exceptions = [
            DatabaseError("test"),
            DocumentError("test"),
            QueryError("test"),
            ExternalServiceError(service_name="test", message="test"),
            CircuitBreakerOpen(service="test"),
            ConfigurationError("test"),
            ValidationError(field="test", message="test")
        ]
        
        for exc in exceptions:
            assert isinstance(exc, ServiceException)
            assert isinstance(exc, Exception)
    
    def test_specific_exceptions_inherit_correctly(self):
        """Test specific exceptions have correct parent."""
        # Database hierarchy
        assert isinstance(ConnectionPoolExhausted(), DatabaseError)
        assert isinstance(QueryExecutionError("test"), DatabaseError)
        
        # Document hierarchy
        assert isinstance(DocumentNotFoundError(123), DocumentError)
        assert isinstance(UnsupportedFormatError("test.xyz", [".pdf"]), DocumentError)
        
        # Query hierarchy
        assert isinstance(EmbeddingGenerationError("test"), QueryError)
        assert isinstance(VectorSearchError("test"), QueryError)
        
        # External service hierarchy
        assert isinstance(OpenRouterError("test"), ExternalServiceError)
        assert isinstance(RateLimitError("test"), ExternalServiceError)
        
        # Configuration hierarchy
        assert isinstance(MissingConfigError("test"), ConfigurationError)
        
        # Validation hierarchy
        assert isinstance(InvalidInputError("f", "v", "test"), ValidationError)
    
    def test_can_catch_by_base_type(self):
        """Test catching exceptions by base type."""
        caught_base = False
        caught_specific = False
        
        try:
            raise DocumentNotFoundError(123)
        except DocumentError:
            caught_base = True
        
        try:
            raise DocumentNotFoundError(123)
        except ServiceException:
            caught_specific = True
        
        assert caught_base is True
        assert caught_specific is True


class TestExceptionSerialization:
    """Tests for exception serialization."""
    
    def test_to_dict_includes_type(self):
        """Test to_dict includes exception type."""
        exc = DocumentNotFoundError(123)
        data = exc.to_dict()
        
        assert "type" in data
        assert data["type"] == "DocumentNotFoundError"
    
    def test_to_dict_json_serializable(self):
        """Test to_dict output is JSON serializable."""
        import json
        
        exc = QueryError(
            message="Query failed",
            code="Q_ERR_001",
            details={
                "query": "test question",
                "top_k": 5,
                "timestamp": "2024-01-01T00:00:00"
            }
        )
        
        data = exc.to_dict()
        json_str = json.dumps(data)
        
        assert len(json_str) > 0
        
        # Deserialize and verify
        parsed = json.loads(json_str)
        assert parsed["message"] == "Query failed"
