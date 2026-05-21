"""
Shared pytest fixtures and configuration for all tests.

This module provides:
- Database fixtures (PostgreSQL, Qdrant, Redis)
- Service client fixtures
- Mock fixtures for external APIs
- Test data generators
- Async test support
"""

import os
import sys
import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator, Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow running tests")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    os.environ.update({
        "TESTING": "true",
        "POSTGRES_HOST": os.getenv("TEST_POSTGRES_HOST", "localhost"),
        "POSTGRES_PORT": os.getenv("TEST_POSTGRES_PORT", "5432"),
        "POSTGRES_DB": os.getenv("TEST_POSTGRES_DB", "cognimend_test"),
        "POSTGRES_USER": os.getenv("TEST_POSTGRES_USER", "postgres"),
        "POSTGRES_PASSWORD": os.getenv("TEST_POSTGRES_PASSWORD", "testpassword"),
        "QDRANT_HOST": os.getenv("TEST_QDRANT_HOST", "localhost"),
        "QDRANT_PORT": os.getenv("TEST_QDRANT_PORT", "6333"),
        "REDIS_HOST": os.getenv("TEST_REDIS_HOST", "localhost"),
        "REDIS_PORT": os.getenv("TEST_REDIS_PORT", "6379"),
        "OPENROUTER_API_KEY": "test-api-key",
        "OPENROUTER_PRESET": "budget",
        "CORS_ORIGINS": "http://localhost:8080",
        "LOG_LEVEL": "WARNING",
    })
    yield
    # Cleanup if needed


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_openrouter_embedding():
    """Mock OpenRouter embedding API response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [{"embedding": [0.1] * 1536}],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 10, "total_tokens": 10}
    }
    return mock_response


@pytest.fixture
def mock_openrouter_chat():
    """Mock OpenRouter chat completion API response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "test-completion-id",
        "model": "claude-3-haiku",
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Based on the Employee Handbook, the vacation policy allows 20 days of PTO per year. [Source: Employee Handbook, page 42]"
            },
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    }
    return mock_response


@pytest.fixture
def mock_openrouter_client(mock_openrouter_embedding, mock_openrouter_chat):
    """Mock complete OpenRouter client."""
    client = MagicMock()
    client.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    client.get_embeddings_batch = AsyncMock(return_value=[[0.1] * 1536])
    client.chat_completion = AsyncMock(return_value={
        "answer": "Based on the Employee Handbook, the vacation policy allows 20 days of PTO per year.",
        "tokens_used": 150,
        "model": "claude-3-haiku"
    })
    return client


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for vector operations."""
    client = MagicMock()
    
    # Mock search results
    search_result = MagicMock()
    search_result.id = "chunk-123"
    search_result.score = 0.95
    search_result.payload = {
        "document_id": "doc-123",
        "document_name": "Employee Handbook",
        "content": "Full-time employees are entitled to 20 days of paid time off annually.",
        "chunk_index": 5,
        "page": 42
    }
    
    client.search = MagicMock(return_value=[search_result])
    client.upsert = MagicMock(return_value=True)
    client.delete = MagicMock(return_value=True)
    client.create_collection = MagicMock(return_value=True)
    client.get_collections = MagicMock(return_value=MagicMock(collections=[]))
    
    return client


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for caching."""
    client = MagicMock()
    cache_store = {}
    
    async def mock_get(key):
        return cache_store.get(key)
    
    async def mock_set(key, value, ex=None):
        cache_store[key] = value
        return True
    
    async def mock_delete(key):
        if key in cache_store:
            del cache_store[key]
        return True
    
    client.get = AsyncMock(side_effect=mock_get)
    client.set = AsyncMock(side_effect=mock_set)
    client.delete = AsyncMock(side_effect=mock_delete)
    client.exists = AsyncMock(return_value=0)
    client.incr = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    client._cache_store = cache_store
    
    return client


@pytest.fixture
def mock_db_connection():
    """Mock PostgreSQL database connection."""
    conn = MagicMock()
    cursor = MagicMock()
    
    # Default query results
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []
    cursor.rowcount = 0
    
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    conn.commit = MagicMock()
    conn.rollback = MagicMock()
    
    return conn, cursor


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_document_content():
    """Sample document content for testing."""
    return """
    Employee Handbook 2024
    
    Chapter 1: Introduction
    Welcome to the company! This handbook outlines our policies and procedures.
    
    Chapter 2: Vacation Policy
    Full-time employees are entitled to 20 days of paid time off annually.
    Vacation requests should be submitted at least 2 weeks in advance.
    Unused days can be carried over up to 5 days to the next year.
    
    Chapter 3: Benefits
    Health insurance is provided for all full-time employees.
    401(k) matching up to 4% of salary.
    
    Chapter 4: Code of Conduct
    All employees are expected to maintain professional behavior.
    Harassment of any kind will not be tolerated.
    """


@pytest.fixture
def sample_chunks():
    """Sample chunked text for testing."""
    return [
        {
            "content": "Employee Handbook 2024. Chapter 1: Introduction. Welcome to the company!",
            "chunk_index": 0,
            "token_count": 15
        },
        {
            "content": "Chapter 2: Vacation Policy. Full-time employees are entitled to 20 days of paid time off annually.",
            "chunk_index": 1,
            "token_count": 20
        },
        {
            "content": "Vacation requests should be submitted at least 2 weeks in advance. Unused days can be carried over.",
            "chunk_index": 2,
            "token_count": 18
        },
        {
            "content": "Chapter 3: Benefits. Health insurance is provided for all full-time employees.",
            "chunk_index": 3,
            "token_count": 14
        },
        {
            "content": "Chapter 4: Code of Conduct. All employees are expected to maintain professional behavior.",
            "chunk_index": 4,
            "token_count": 15
        }
    ]


@pytest.fixture
def sample_embeddings():
    """Sample embedding vectors for testing."""
    import random
    random.seed(42)
    return [[random.uniform(-1, 1) for _ in range(1536)] for _ in range(5)]


@pytest.fixture
def sample_document_metadata():
    """Sample document metadata."""
    return {
        "document_id": "doc-test-123",
        "filename": "employee_handbook.pdf",
        "file_hash": hashlib.sha256(b"test content").hexdigest(),
        "chunks": 5,
        "status": "processed",
        "created_at": datetime.utcnow().isoformat(),
        "metadata": {
            "pages": 10,
            "word_count": 1500,
            "language": "en"
        }
    }


@pytest.fixture
def sample_query():
    """Sample query request."""
    return {
        "query": "What is the vacation policy?",
        "top_k": 5,
        "include_sources": True
    }


@pytest.fixture
def sample_query_result():
    """Sample query response."""
    return {
        "answer": "Based on the Employee Handbook, full-time employees receive 20 days of PTO per year.",
        "confidence": 0.92,
        "sources": [
            {
                "document_id": "doc-123",
                "document_name": "Employee Handbook",
                "snippet": "Full-time employees are entitled to 20 days...",
                "similarity": 0.95,
                "page": 42
            }
        ],
        "metadata": {
            "response_time_ms": 1250,
            "documents_searched": 10,
            "cached": False
        }
    }


@pytest.fixture
def sample_drift_data():
    """Sample drift detection data."""
    return {
        "baseline_confidence": [0.85, 0.88, 0.90, 0.87, 0.89],
        "recent_confidence": [0.75, 0.72, 0.78, 0.70, 0.73],
        "baseline_latency": [1000, 1100, 1050, 1080, 1020],
        "recent_latency": [1500, 1600, 1550, 1650, 1700],
    }


@pytest.fixture
def sample_telemetry_logs():
    """Sample telemetry query logs."""
    base_time = datetime.utcnow()
    return [
        {
            "query_id": f"qry-{i}",
            "query": f"Test query {i}",
            "confidence": 0.85 + (i * 0.01),
            "response_time_ms": 1000 + (i * 50),
            "cached": i % 2 == 0,
            "created_at": (base_time - timedelta(hours=i)).isoformat()
        }
        for i in range(10)
    ]


# =============================================================================
# File Upload Fixtures
# =============================================================================

@pytest.fixture
def sample_pdf_file():
    """Create a mock PDF file for testing."""
    from io import BytesIO
    
    # Simple PDF-like content (not a valid PDF, but works for testing)
    content = b"%PDF-1.4\nTest PDF content for upload testing"
    file = BytesIO(content)
    file.name = "test_document.pdf"
    return file


@pytest.fixture
def sample_txt_file():
    """Create a mock TXT file for testing."""
    from io import BytesIO
    
    content = b"This is a test document.\n\nIt contains multiple paragraphs.\n\nFor testing purposes."
    file = BytesIO(content)
    file.name = "test_document.txt"
    return file


@pytest.fixture
def sample_large_file():
    """Create a large file that exceeds size limits."""
    from io import BytesIO
    
    # Create 60MB file (exceeds 50MB limit)
    content = b"x" * (60 * 1024 * 1024)
    file = BytesIO(content)
    file.name = "large_file.txt"
    return file


@pytest.fixture
def sample_invalid_file():
    """Create an invalid file type for testing."""
    from io import BytesIO
    
    content = b"\x00\x01\x02\x03"  # Binary content
    file = BytesIO(content)
    file.name = "invalid_file.exe"
    return file


# =============================================================================
# Service Client Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def upload_client(mock_openrouter_client, mock_qdrant_client, mock_db_connection):
    """Create test client for upload service."""
    with patch.dict(os.environ, {"TESTING": "true"}):
        # Import after patching
        from services.upload.main import app
        
        # Patch dependencies
        with patch('services.upload.main.openrouter_client', mock_openrouter_client), \
             patch('services.upload.main.qdrant_client', mock_qdrant_client):
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client


@pytest_asyncio.fixture
async def query_client(mock_openrouter_client, mock_qdrant_client, mock_redis_client, mock_db_connection):
    """Create test client for query service."""
    with patch.dict(os.environ, {"TESTING": "true"}):
        from services.query.main import app
        
        with patch('services.query.main.openrouter_client', mock_openrouter_client), \
             patch('services.query.main.qdrant_client', mock_qdrant_client), \
             patch('services.query.main.cache', mock_redis_client):
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client


@pytest_asyncio.fixture
async def telemetry_client(mock_db_connection, mock_redis_client):
    """Create test client for telemetry service."""
    with patch.dict(os.environ, {"TESTING": "true"}):
        from services.telemetry.main import app
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest_asyncio.fixture
async def drift_detector_client(mock_db_connection, mock_qdrant_client):
    """Create test client for drift detector service."""
    with patch.dict(os.environ, {"TESTING": "true"}):
        from services.drift_detector.main import app
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest_asyncio.fixture
async def controller_client(mock_db_connection, mock_redis_client):
    """Create test client for controller service."""
    with patch.dict(os.environ, {"TESTING": "true"}):
        from services.controller.main import app
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


# =============================================================================
# Utility Functions
# =============================================================================

def create_test_embedding(seed: int = 42, dimensions: int = 1536) -> List[float]:
    """Generate a reproducible test embedding."""
    import random
    random.seed(seed)
    return [random.uniform(-1, 1) for _ in range(dimensions)]


def create_test_document(doc_id: str = "test-doc", chunks: int = 5) -> Dict[str, Any]:
    """Create a test document with metadata."""
    return {
        "document_id": doc_id,
        "filename": f"{doc_id}.pdf",
        "file_hash": hashlib.sha256(doc_id.encode()).hexdigest(),
        "status": "processed",
        "chunks": chunks,
        "created_at": datetime.utcnow().isoformat()
    }


def generate_query_logs(count: int = 100, drift: bool = False) -> List[Dict[str, Any]]:
    """Generate synthetic query logs for testing."""
    import random
    random.seed(42)
    
    base_time = datetime.utcnow()
    logs = []
    
    for i in range(count):
        # Simulate drift in second half if drift=True
        if drift and i >= count // 2:
            confidence = random.uniform(0.5, 0.7)
            latency = random.randint(2000, 3000)
        else:
            confidence = random.uniform(0.8, 0.95)
            latency = random.randint(800, 1500)
        
        logs.append({
            "query_id": f"qry-{i}",
            "query": f"Test query {i}",
            "confidence": confidence,
            "response_time_ms": latency,
            "cached": random.choice([True, False]),
            "created_at": (base_time - timedelta(hours=i)).isoformat()
        })
    
    return logs
