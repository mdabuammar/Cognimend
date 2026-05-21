# Test Suite Documentation

## Overview

This test suite provides comprehensive coverage for all shared modules and service integration.

## Test Structure

```
services/tests/
├── __init__.py
├── conftest.py              # Pytest fixtures and mocks
├── test_integration.py      # Integration tests between services
└── test_shared/
    ├── __init__.py
    ├── test_actions.py      # Action registry & strategy pattern
    ├── test_cache.py        # Redis caching operations
    ├── test_document_processor.py  # Document processing pipeline
    ├── test_exceptions.py   # Exception hierarchy
    ├── test_query_processor.py     # Query processing pipeline
    ├── test_resilience.py   # Circuit breaker & retry logic
    └── test_utils.py        # Shared utilities
```

## Running Tests

### Run All Tests
```bash
cd backend
pytest services/tests -v
```

### Run Specific Test File
```bash
pytest services/tests/test_shared/test_actions.py -v
```

### Run with Coverage
```bash
pytest services/tests --cov=services/shared --cov-report=html
```

### Run Only Integration Tests
```bash
pytest services/tests/test_integration.py -v
```

### Run Async Tests
```bash
pytest services/tests -v -k "asyncio"
```

## Test Categories

### Unit Tests (`test_shared/`)

#### test_actions.py
- `TestActionResult`: ActionResult dataclass behavior
- `TestActionRegistry`: Action registration and retrieval
- `TestReindexDocumentsAction`: Document reindexing action
- `TestIncreaseTopKAction`: Top-K adjustment action
- `TestLowerConfidenceThresholdAction`: Confidence threshold action
- `TestIncreaseChunkOverlapAction`: Chunk overlap action
- `TestGlobalActionRegistry`: Global registry singleton
- `TestBaseAction`: Abstract base class enforcement

#### test_cache.py
- `TestCacheOperations`: CRUD operations
- `TestCacheKeyPatterns`: Key generation patterns
- `TestCacheTTL`: TTL behavior
- `TestCacheGetOrCompute`: Compute-on-miss pattern
- `TestCacheHealthCheck`: Health check integration
- `TestCacheSerialization`: JSON serialization

#### test_document_processor.py
- `TestTextExtractor`: PDF/DOCX/TXT extraction
- `TestTextChunker`: Document chunking with tiktoken
- `TestFileHasher`: SHA256/MD5 hashing
- `TestDocumentProcessor`: Full processing pipeline
- `TestEmbeddingProcessor`: Batch embedding with caching

#### test_exceptions.py
- `TestServiceException`: Base exception class
- `TestDatabaseErrors`: Database exception hierarchy
- `TestDocumentErrors`: Document exception hierarchy
- `TestQueryErrors`: Query exception hierarchy
- `TestExternalServiceErrors`: External service exceptions
- `TestCircuitBreakerOpen`: Circuit breaker exception
- `TestConfigurationErrors`: Configuration exceptions
- `TestValidationErrors`: Input validation exceptions
- `TestExceptionHierarchy`: Inheritance verification
- `TestExceptionSerialization`: JSON serialization

#### test_query_processor.py
- `TestCacheKeyGenerator`: Query cache key generation
- `TestConfidenceCalculator`: Weighted confidence scoring
- `TestContextBuilder`: Context building with citations
- `TestQueryProcessor`: Full query pipeline
- `TestCitation`: Citation dataclass
- `TestQueryResult`: Query result dataclass

#### test_resilience.py
- `TestCircuitState`: Circuit state enum
- `TestCircuitBreaker`: Circuit breaker logic
- `TestRetryPolicy`: Retry configuration
- `TestWithRetryDecorator`: Retry decorator
- `TestWithCircuitBreakerDecorator`: CB decorator
- `TestCircuitBreakerIntegration`: Integration scenarios

#### test_utils.py
- `TestDatabaseManager`: Connection pool management
- `TestHealthCheckBuilder`: Health check factory
- `TestServiceLogger`: Logging utilities
- `TestDatetimeUtilities`: Datetime helpers
- `TestValidationFunctions`: Input validation
- `TestFormatQueryResults`: Result formatting
- `TestTruncateText`: Text truncation
- `TestGenerateRequestId`: Request ID generation

### Integration Tests (`test_integration.py`)

- `TestUploadQueryIntegration`: Upload → Query pipeline
- `TestControllerDriftIntegration`: Drift → Action pipeline
- `TestHealthCheckIntegration`: Cross-service health
- `TestResilienceIntegration`: Circuit breaker protection
- `TestExceptionHandlingIntegration`: Exception propagation
- `TestDatabaseIntegration`: Shared DB management
- `TestCacheIntegration`: Shared cache operations

## Fixtures (conftest.py)

### Database Fixtures
- `mock_db_connection`: Mocked PostgreSQL connection
- `mock_db_manager`: Mocked DatabaseManager

### Cache Fixtures
- `mock_cache`: Mocked Redis cache with async methods

### External Service Fixtures
- `mock_embedding_client`: Mocked embedding API
- `mock_qdrant_client`: Mocked Qdrant vector store
- `mock_llm_client`: Mocked LLM API

### Data Fixtures
- `sample_document`: Sample document data
- `sample_chunks`: Sample document chunks
- `sample_embedding`: Sample 1536-dim embedding
- `sample_query_result`: Sample query response

## Best Practices

### 1. Use Fixtures
```python
def test_something(mock_db_connection, mock_cache):
    # Use fixtures instead of creating mocks inline
    pass
```

### 2. Test Async Code
```python
@pytest.mark.asyncio
async def test_async_operation(mock_cache):
    result = await some_async_function()
    assert result is not None
```

### 3. Test Exception Paths
```python
def test_handles_error():
    with pytest.raises(DocumentNotFoundError):
        get_document(-1)
```

### 4. Test Edge Cases
```python
def test_empty_input():
    result = process("")
    assert result == default_value

def test_very_large_input():
    result = process("x" * 100000)
    assert len(result) <= MAX_LENGTH
```

## Code Coverage Goals

| Module | Target Coverage |
|--------|----------------|
| actions.py | 90%+ |
| cache.py | 85%+ |
| document_processor.py | 85%+ |
| exceptions.py | 95%+ |
| query_processor.py | 85%+ |
| resilience.py | 90%+ |
| utils.py | 85%+ |

## Adding New Tests

1. Create test file in appropriate location
2. Import module under test
3. Use existing fixtures from conftest.py
4. Follow naming convention: `test_<module_name>.py`
5. Group related tests in classes
6. Use descriptive test names: `test_<action>_<condition>_<expected_result>`

## CI Integration

```yaml
# Example GitHub Actions workflow
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: pip install -r requirements.txt
    - name: Run tests
      run: pytest services/tests --cov=services/shared --cov-report=xml
```
