"""
Pytest configuration and fixtures.
"""
import pytest
import asyncio
from typing import Generator, Any
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add parent path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))


# ============================================================
# Auto-use Fixtures to Mock External Services
# ============================================================

@pytest.fixture(autouse=True)
def mock_psycopg2():
    """Automatically mock psycopg2 to prevent real database connections."""
    with patch('psycopg2.connect') as mock_connect:
        # Setup mock connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        mock_cursor.execute = MagicMock()
        mock_cursor.fetchone = MagicMock(return_value=None)
        mock_cursor.fetchall = MagicMock(return_value=[])
        mock_cursor.fetchmany = MagicMock(return_value=[])
        mock_cursor.close = MagicMock()
        
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.commit = MagicMock()
        mock_conn.rollback = MagicMock()
        mock_conn.close = MagicMock()
        
        mock_connect.return_value = mock_conn
        yield mock_connect


@pytest.fixture(autouse=True)
def mock_psycopg2_pool():
    """Mock psycopg2 connection pool."""
    with patch('psycopg2.pool.SimpleConnectionPool') as mock_pool:
        pool_instance = MagicMock()
        pool_instance.getconn = MagicMock()
        pool_instance.putconn = MagicMock()
        pool_instance.closeall = MagicMock()
        mock_pool.return_value = pool_instance
        yield mock_pool


# ============================================================
# Async Event Loop Fixture
# ============================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================
# Database Fixtures
# ============================================================

@pytest.fixture
def mock_db_connection() -> MagicMock:
    """Create mock database connection."""
    conn = MagicMock()
    cursor = MagicMock()
    
    # Setup cursor methods
    cursor.execute = MagicMock()
    cursor.fetchone = MagicMock(return_value={'id': 1})
    cursor.fetchall = MagicMock(return_value=[])
    cursor.close = MagicMock()
    
    # Setup connection methods
    conn.cursor = MagicMock(return_value=cursor)
    conn.commit = MagicMock()
    conn.rollback = MagicMock()
    conn.close = MagicMock()
    
    return conn


@pytest.fixture
def mock_db_manager(mock_db_connection: MagicMock) -> MagicMock:
    """Create mock database manager."""
    manager = MagicMock()
    manager.get_connection = MagicMock(return_value=mock_db_connection)
    manager.return_connection = MagicMock()
    manager.execute_query = MagicMock(return_value=[])
    manager.execute_write = MagicMock(return_value={'id': 1})
    return manager


# ============================================================
# Cache Fixtures
# ============================================================

@pytest.fixture
def mock_cache() -> AsyncMock:
    """Create mock cache."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.clear_pattern = AsyncMock(return_value=0)
    cache.is_available = MagicMock(return_value=True)
    cache.get_stats = AsyncMock(return_value={"available": True})
    return cache


# ============================================================
# Embedding Client Fixtures
# ============================================================

@pytest.fixture
def mock_embedding_client() -> AsyncMock:
    """Create mock embedding client."""
    client = AsyncMock()
    # Return a deterministic embedding
    client.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    return client


# ============================================================
# Vector Store Fixtures
# ============================================================

@pytest.fixture
def mock_qdrant_client() -> MagicMock:
    """Create mock Qdrant client."""
    client = MagicMock()
    
    # Mock search result
    mock_result = MagicMock()
    mock_result.score = 0.85
    mock_result.payload = {
        'document_id': 1,
        'title': 'Test Document',
        'text': 'This is test content for the document.',
        'version': 1,
        'chunk_index': 0
    }
    
    client.search = MagicMock(return_value=[mock_result])
    client.get_collections = MagicMock()
    client.upsert = MagicMock()
    client.delete = MagicMock()
    
    return client


# ============================================================
# LLM Client Fixtures
# ============================================================

@pytest.fixture
def mock_llm_client() -> AsyncMock:
    """Create mock LLM client."""
    client = AsyncMock()
    client.generate_answer = AsyncMock(return_value={
        'answer': 'This is a test answer based on the context.',
        'model': 'gpt-4',
        'total_tokens': 100,
        'cost_usd': 0.01
    })
    return client


# ============================================================
# Sample Data Fixtures
# ============================================================

@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Return sample PDF bytes (minimal valid PDF)."""
    # Minimal PDF structure
    return b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj
4 0 obj << /Length 44 >> stream
BT /F1 12 Tf 100 700 Td (Test PDF Content) Tj ET
endstream endobj
xref
0 5
trailer << /Size 5 /Root 1 0 R >>
startxref
0
%%EOF"""


@pytest.fixture
def sample_text() -> str:
    """Return sample text content."""
    return """
    This is a sample document for testing purposes.
    It contains multiple paragraphs with various content.
    
    The vacation policy allows employees to take up to 20 days per year.
    Sick leave is available for up to 10 days per year.
    
    Remote work is permitted for up to 3 days per week.
    """


@pytest.fixture
def sample_chunks() -> list:
    """Return sample text chunks."""
    return [
        "This is the first chunk of text for testing.",
        "This is the second chunk with different content.",
        "This is the third chunk about vacation policy."
    ]


@pytest.fixture
def sample_query_result() -> dict:
    """Return sample query result."""
    return {
        "answer": "The vacation policy allows 20 days per year.",
        "confidence": 85.5,
        "citations": [
            {
                "document_id": 1,
                "title": "HR Handbook",
                "snippet": "The vacation policy allows employees...",
                "similarity": 92.3,
                "version": 1,
                "chunk_index": 0
            }
        ],
        "latency_ms": 150,
        "retrieved_count": 1,
        "cache_hit": False,
        "model_used": "gpt-4"
    }


# ============================================================
# Configuration Fixtures
# ============================================================

@pytest.fixture
def sample_config() -> dict:
    """Return sample configuration."""
    return {
        "chunk_size": 512,
        "chunk_overlap": 50,
        "top_k": 3,
        "confidence_threshold": 0.6,
        "similarity_threshold": 0.5,
        "cache_ttl_seconds": 3600,
        "max_context_length": 4000
    }


@pytest.fixture
def sample_drift_event() -> dict:
    """Return sample drift event."""
    return {
        "drift_type": "retrieval_drift",
        "severity": "medium",
        "metric_value": 0.15,
        "threshold": 0.10,
        "description": "Similarity scores dropped by 15%"
    }
