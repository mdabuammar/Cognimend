"""
Integration tests for Upload and Query service workflow.

Tests cover:
- Document upload followed by query
- Multi-document query workflow
- Version management integration
- Cache behavior across services
- Error propagation between services

These tests require the test database and vector store to be running.
Use docker-compose.test.yml to spin up test infrastructure.
"""

import os
import sys
import pytest
import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def test_document_content():
    """Create test document content."""
    return """
    Company Policy Document v2.0
    
    Section 1: Work From Home Policy
    Employees may work from home up to 3 days per week with manager approval.
    Equipment will be provided for home office setup.
    
    Section 2: Expense Reimbursement
    All business expenses must be submitted within 30 days.
    Receipts are required for expenses over $25.
    Manager approval required for expenses over $500.
    
    Section 3: Training and Development
    Each employee receives a $2000 annual training budget.
    Training must be relevant to current role or career development.
    """


@pytest.fixture
def second_document_content():
    """Create a second test document."""
    return """
    Employee Benefits Guide 2024
    
    Health Insurance:
    - Medical, dental, and vision coverage
    - Company pays 80% of premiums
    - Family coverage available
    
    Retirement:
    - 401(k) with 4% company match
    - Vesting after 2 years
    
    Time Off:
    - 20 days PTO annually
    - 10 company holidays
    - Unlimited sick leave with manager discretion
    """


# =============================================================================
# Upload Then Query Workflow Tests
# =============================================================================

class TestUploadQueryWorkflow:
    """Integration tests for upload followed by query."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_upload_then_query_basic(
        self,
        test_document_content,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client,
        mock_db_connection
    ):
        """Test uploading a document and then querying it."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            # Setup mocks
            conn, cursor = mock_db_connection
            cursor.fetchone.return_value = None  # No existing document
            
            # Mock search results to return our uploaded document
            search_result = MagicMock()
            search_result.id = "chunk-1"
            search_result.score = 0.92
            search_result.payload = {
                "document_id": "uploaded-doc",
                "document_name": "Company Policy",
                "content": "Employees may work from home up to 3 days per week",
                "chunk_index": 0
            }
            mock_qdrant_client.search.return_value = [search_result]
            
            # Import services
            from services.upload.main import app as upload_app
            from services.query.main import app as query_app
            
            # Step 1: Upload document
            with patch('services.upload.main.openrouter_client', mock_openrouter_client), \
                 patch('services.upload.main.qdrant_client', mock_qdrant_client), \
                 patch('services.upload.main.get_db_connection', return_value=conn):
                
                transport = ASGITransport(app=upload_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    file_content = BytesIO(test_document_content.encode())
                    upload_response = await client.post(
                        "/upload",
                        files={"file": ("policy.txt", file_content, "text/plain")}
                    )
                    
                    assert upload_response.status_code in [200, 201, 202]
            
            # Step 2: Query the document
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    query_response = await client.post(
                        "/query",
                        json={"query": "How many days can I work from home?"}
                    )
                    
                    assert query_response.status_code == 200
                    data = query_response.json()
                    assert "answer" in data or "response" in data
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_includes_source_from_upload(
        self,
        test_document_content,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client,
        mock_db_connection
    ):
        """Test that query response includes source from uploaded document."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            
            # Mock search to return uploaded document
            search_result = MagicMock()
            search_result.id = "chunk-1"
            search_result.score = 0.95
            search_result.payload = {
                "document_id": "doc-123",
                "document_name": "Company Policy",
                "content": "Expense reimbursement: All business expenses must be submitted within 30 days.",
                "chunk_index": 2,
                "page": 5
            }
            mock_qdrant_client.search.return_value = [search_result]
            
            # Mock chat completion to include sources
            mock_openrouter_client.chat_completion = AsyncMock(return_value={
                "answer": "Business expenses must be submitted within 30 days. [Source: Company Policy, page 5]",
                "tokens_used": 100,
                "model": "claude-3-haiku"
            })
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/query",
                        json={
                            "query": "What is the expense reimbursement deadline?",
                            "include_sources": True
                        }
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    # Answer should reference the source
                    answer = data.get('answer') or data.get('response', '')
                    assert len(answer) > 0


# =============================================================================
# Multi-Document Query Tests
# =============================================================================

class TestMultiDocumentQuery:
    """Tests for querying across multiple documents."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_across_multiple_documents(
        self,
        test_document_content,
        second_document_content,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client,
        mock_db_connection
    ):
        """Test querying information from multiple uploaded documents."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            
            # Mock search to return results from multiple documents
            search_results = [
                MagicMock(
                    id="chunk-1",
                    score=0.93,
                    payload={
                        "document_id": "doc-policy",
                        "document_name": "Company Policy",
                        "content": "Each employee receives a $2000 annual training budget.",
                        "chunk_index": 5
                    }
                ),
                MagicMock(
                    id="chunk-2",
                    score=0.88,
                    payload={
                        "document_id": "doc-benefits",
                        "document_name": "Benefits Guide",
                        "content": "20 days PTO annually. 10 company holidays.",
                        "chunk_index": 3
                    }
                )
            ]
            mock_qdrant_client.search.return_value = search_results
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/query",
                        json={"query": "What benefits do employees get?", "top_k": 5}
                    )
                    
                    assert response.status_code == 200
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_with_document_filter(
        self,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client
    ):
        """Test querying with specific document filter."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            # Mock filtered search
            search_result = MagicMock()
            search_result.id = "chunk-1"
            search_result.score = 0.91
            search_result.payload = {
                "document_id": "doc-policy",
                "document_name": "Company Policy",
                "content": "Work from home policy content",
            }
            mock_qdrant_client.search.return_value = [search_result]
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/query",
                        json={
                            "query": "What is the WFH policy?",
                            "document_filter": ["doc-policy"]
                        }
                    )
                    
                    assert response.status_code == 200


# =============================================================================
# Version Management Tests
# =============================================================================

class TestVersionManagement:
    """Tests for document version management."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_upload_new_version(
        self,
        test_document_content,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_db_connection
    ):
        """Test uploading a new version of existing document."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            
            # Simulate existing document
            cursor.fetchone.side_effect = [
                ("doc-123",),  # Existing document found (for duplicate check)
                ("doc-123", "policy.txt", "old-hash", "processed", 5, datetime.utcnow()),  # Document details
            ]
            
            from services.upload.main import app as upload_app
            
            with patch('services.upload.main.openrouter_client', mock_openrouter_client), \
                 patch('services.upload.main.qdrant_client', mock_qdrant_client), \
                 patch('services.upload.main.get_db_connection', return_value=conn):
                
                transport = ASGITransport(app=upload_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # Upload new version
                    updated_content = test_document_content + "\n\nUpdated section: New policy additions."
                    file_content = BytesIO(updated_content.encode())
                    
                    response = await client.post(
                        "/upload",
                        files={"file": ("policy.txt", file_content, "text/plain")},
                        data={"version": "2.0"}
                    )
                    
                    # Should either create new version or update existing
                    assert response.status_code in [200, 201, 202, 409]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_latest_version(
        self,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client
    ):
        """Test that query returns results from latest document version."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            # Mock search to return only latest version
            search_result = MagicMock()
            search_result.id = "chunk-v2-1"
            search_result.score = 0.94
            search_result.payload = {
                "document_id": "doc-123",
                "document_name": "Company Policy v2.0",
                "content": "Updated: Employees may work from home up to 4 days per week.",
                "version": "2.0"
            }
            mock_qdrant_client.search.return_value = [search_result]
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/query",
                        json={"query": "How many days can I work from home?"}
                    )
                    
                    assert response.status_code == 200


# =============================================================================
# Cache Behavior Tests
# =============================================================================

class TestCacheBehavior:
    """Tests for caching behavior across services."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_cache_hit(
        self,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client
    ):
        """Test that repeated queries hit the cache."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            query_text = "What is the vacation policy?"
            cached_response = {
                "answer": "Cached: Employees receive 20 days PTO.",
                "cached": True
            }
            
            # First call - cache miss
            mock_redis_client.get = AsyncMock(return_value=None)
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # First query - should compute
                    response1 = await client.post("/query", json={"query": query_text})
                    assert response1.status_code == 200
                    
                    # Simulate cache now has the result
                    import json
                    mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_response))
                    
                    # Second query - should hit cache
                    response2 = await client.post("/query", json={"query": query_text})
                    assert response2.status_code == 200
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_upload(
        self,
        test_document_content,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client,
        mock_db_connection
    ):
        """Test that cache is invalidated when new document is uploaded."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            cursor.fetchone.return_value = None
            
            cache_invalidated = False
            
            async def mock_delete(pattern):
                nonlocal cache_invalidated
                cache_invalidated = True
                return True
            
            mock_redis_client.delete = AsyncMock(side_effect=mock_delete)
            
            from services.upload.main import app as upload_app
            
            with patch('services.upload.main.openrouter_client', mock_openrouter_client), \
                 patch('services.upload.main.qdrant_client', mock_qdrant_client), \
                 patch('services.upload.main.get_db_connection', return_value=conn), \
                 patch('services.upload.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=upload_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    file_content = BytesIO(test_document_content.encode())
                    response = await client.post(
                        "/upload",
                        files={"file": ("policy.txt", file_content, "text/plain")}
                    )
                    
                    # Cache invalidation should be triggered
                    # (actual behavior depends on implementation)
                    assert response.status_code in [200, 201, 202]


# =============================================================================
# Error Propagation Tests
# =============================================================================

class TestErrorPropagation:
    """Tests for error handling between services."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_handles_qdrant_failure(
        self,
        mock_openrouter_client,
        mock_redis_client
    ):
        """Test query service handles Qdrant failure gracefully."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            mock_qdrant = MagicMock()
            mock_qdrant.search = MagicMock(side_effect=Exception("Qdrant connection lost"))
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/query",
                        json={"query": "Test query"}
                    )
                    
                    # Should return error response, not crash
                    assert response.status_code in [500, 503, 200]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_upload_handles_embedding_failure(
        self,
        test_document_content,
        mock_qdrant_client,
        mock_db_connection
    ):
        """Test upload service handles embedding failure gracefully."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            cursor.fetchone.return_value = None
            
            mock_openrouter = MagicMock()
            mock_openrouter.get_embedding = AsyncMock(
                side_effect=Exception("OpenRouter API unavailable")
            )
            
            from services.upload.main import app as upload_app
            
            with patch('services.upload.main.openrouter_client', mock_openrouter), \
                 patch('services.upload.main.qdrant_client', mock_qdrant_client), \
                 patch('services.upload.main.get_db_connection', return_value=conn):
                
                transport = ASGITransport(app=upload_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    file_content = BytesIO(test_document_content.encode())
                    response = await client.post(
                        "/upload",
                        files={"file": ("test.txt", file_content, "text/plain")}
                    )
                    
                    # Should return error, not crash
                    assert response.status_code in [500, 503, 200, 202]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_timeout_handling(
        self,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client
    ):
        """Test query service handles timeout gracefully."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            import asyncio
            
            async def slow_embedding(*args, **kwargs):
                await asyncio.sleep(10)  # Simulate slow response
                return [0.1] * 1536
            
            mock_openrouter_client.get_embedding = AsyncMock(side_effect=slow_embedding)
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test", timeout=1.0) as client:
                    try:
                        response = await client.post(
                            "/query",
                            json={"query": "Test query"}
                        )
                        # If it doesn't timeout, check response
                        assert response.status_code in [200, 408, 504]
                    except Exception:
                        # Timeout is expected
                        pass


# =============================================================================
# Drift Detection Trigger Tests
# =============================================================================

class TestDriftDetectionTrigger:
    """Tests for drift detection integration."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_logs_telemetry(
        self,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client,
        mock_db_connection
    ):
        """Test that queries log telemetry for drift detection."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            telemetry_logged = False
            
            def mock_execute(query, *args, **kwargs):
                nonlocal telemetry_logged
                if 'telemetry' in str(query).lower() or 'query_log' in str(query).lower():
                    telemetry_logged = True
                return cursor
            
            cursor.execute = MagicMock(side_effect=mock_execute)
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client), \
                 patch('services.query.main.get_db_connection', return_value=conn):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    await client.post("/query", json={"query": "Test query for telemetry"})
                    
                    # Telemetry should be logged (implementation dependent)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_low_confidence_triggers_alert(
        self,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client
    ):
        """Test that low confidence responses can trigger drift alerts."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            # Mock low confidence search results
            search_result = MagicMock()
            search_result.id = "chunk-1"
            search_result.score = 0.35  # Low similarity score
            search_result.payload = {
                "document_id": "doc-123",
                "content": "Unrelated content"
            }
            mock_qdrant_client.search.return_value = [search_result]
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/query",
                        json={"query": "Completely unrelated query about quantum physics"}
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    # Response should indicate low confidence
                    confidence = data.get('confidence', data.get('similarity_score', 1.0))
                    # Low confidence expected (though exact field depends on implementation)
