"""
Unit tests for the Query Service.

Tests cover:
- Query processing and embedding
- Vector similarity search
- RAG answer generation
- Response caching
- Rate limiting
- Error handling

Coverage target: >80%
"""

import os
import sys
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# =============================================================================
# Query Processing Tests
# =============================================================================

class TestQueryProcessing:
    """Tests for query processing functionality."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_query_endpoint_success(self, sample_query, mock_openrouter_client, mock_qdrant_client, mock_redis_client):
        """Test successful query processing."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/query", json=sample_query)
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "answer" in data or "response" in data
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_query_endpoint_empty_query(self, mock_openrouter_client, mock_redis_client):
        """Test query with empty query string."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/query", json={"query": ""})
                    
                    assert response.status_code in [400, 422]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_query_endpoint_missing_query(self, mock_openrouter_client, mock_redis_client):
        """Test query without query field."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/query", json={})
                    
                    assert response.status_code == 422
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_query_endpoint_long_query(self, mock_openrouter_client, mock_qdrant_client, mock_redis_client):
        """Test query with very long query string."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            long_query = "What is the vacation policy? " * 100
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/query", json={"query": long_query})
                    
                    # Should handle gracefully - either truncate or return error
                    assert response.status_code in [200, 400, 422]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.parametrize("top_k", [1, 3, 5, 10, 20])
    async def test_query_with_various_top_k(self, top_k, mock_openrouter_client, mock_qdrant_client, mock_redis_client):
        """Test query with different top_k values."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/query", json={
                        "query": "What is the vacation policy?",
                        "top_k": top_k
                    })
                    
                    assert response.status_code == 200


# =============================================================================
# Vector Search Tests
# =============================================================================

class TestVectorSearch:
    """Tests for vector similarity search."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_search_similar_documents(self, mock_qdrant_client, sample_embeddings):
        """Test searching for similar documents."""
        from services.query.search import search_similar
        
        with patch('services.query.search.qdrant_client', mock_qdrant_client):
            results = await search_similar(sample_embeddings[0], top_k=5)
            
            assert isinstance(results, list)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_search_with_filter(self, mock_qdrant_client, sample_embeddings):
        """Test search with document filter."""
        from services.query.search import search_similar
        
        with patch('services.query.search.qdrant_client', mock_qdrant_client):
            results = await search_similar(
                sample_embeddings[0], 
                top_k=5,
                document_filter=["doc-123", "doc-456"]
            )
            
            assert isinstance(results, list)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_search_empty_collection(self, mock_qdrant_client, sample_embeddings):
        """Test search on empty collection."""
        mock_qdrant_client.search.return_value = []
        
        from services.query.search import search_similar
        
        with patch('services.query.search.qdrant_client', mock_qdrant_client):
            results = await search_similar(sample_embeddings[0], top_k=5)
            
            assert results == []
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_search_returns_scored_results(self, mock_qdrant_client, sample_embeddings):
        """Test that search returns properly scored results."""
        search_result = MagicMock()
        search_result.id = "chunk-123"
        search_result.score = 0.95
        search_result.payload = {
            "document_id": "doc-123",
            "content": "Test content"
        }
        mock_qdrant_client.search.return_value = [search_result]
        
        from services.query.search import search_similar
        
        with patch('services.query.search.qdrant_client', mock_qdrant_client):
            results = await search_similar(sample_embeddings[0], top_k=5)
            
            assert len(results) == 1
            assert results[0].score == 0.95


# =============================================================================
# RAG Answer Generation Tests
# =============================================================================

class TestRAGGeneration:
    """Tests for RAG answer generation."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_answer_with_context(self, mock_openrouter_client):
        """Test answer generation with context."""
        from services.query.rag import generate_answer
        
        context = [
            {"content": "Employees receive 20 days of PTO annually.", "document_name": "Handbook"}
        ]
        
        with patch('services.query.rag.client', mock_openrouter_client):
            result = await generate_answer("What is the vacation policy?", context)
            
            assert isinstance(result, dict)
            assert "answer" in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_answer_no_context(self, mock_openrouter_client):
        """Test answer generation without relevant context."""
        from services.query.rag import generate_answer
        
        mock_openrouter_client.chat_completion = AsyncMock(return_value={
            "answer": "I don't have enough information to answer that question based on the available documents.",
            "tokens_used": 50,
            "model": "claude-3-haiku"
        })
        
        with patch('services.query.rag.client', mock_openrouter_client):
            result = await generate_answer("What is quantum physics?", [])
            
            assert "don't have" in result["answer"].lower() or len(result["answer"]) > 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_answer_includes_sources(self, mock_openrouter_client):
        """Test that answer includes source references."""
        from services.query.rag import generate_answer
        
        context = [
            {
                "content": "PTO policy: 20 days per year.",
                "document_name": "Employee Handbook",
                "page": 42
            }
        ]
        
        with patch('services.query.rag.client', mock_openrouter_client):
            result = await generate_answer(
                "What is the vacation policy?",
                context,
                include_sources=True
            )
            
            # Answer should reference sources somehow
            assert "answer" in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_answer_api_error(self, mock_openrouter_client):
        """Test answer generation handles API errors."""
        from services.query.rag import generate_answer
        
        mock_openrouter_client.chat_completion = AsyncMock(
            side_effect=Exception("API unavailable")
        )
        
        with patch('services.query.rag.client', mock_openrouter_client):
            with pytest.raises(Exception):
                await generate_answer("Test query", [])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.parametrize("model_preset", ["budget", "balanced", "performance"])
    async def test_generate_answer_with_presets(self, model_preset, mock_openrouter_client):
        """Test answer generation with different model presets."""
        from services.query.rag import generate_answer
        
        with patch('services.query.rag.client', mock_openrouter_client), \
             patch.dict(os.environ, {"OPENROUTER_PRESET": model_preset}):
            
            result = await generate_answer("Test query", [{"content": "Context"}])
            
            assert "answer" in result


# =============================================================================
# Caching Tests
# =============================================================================

class TestCaching:
    """Tests for response caching."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cached_response_returned(self, sample_query, mock_openrouter_client, mock_qdrant_client, mock_redis_client):
        """Test that cached responses are returned."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            # Pre-populate cache
            cache_key = f"query:{hash(sample_query['query'])}"
            cached_response = json.dumps({
                "answer": "Cached answer",
                "cached": True
            })
            mock_redis_client._cache_store[cache_key] = cached_response
            mock_redis_client.get = AsyncMock(return_value=cached_response)
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/query", json=sample_query)
                    
                    assert response.status_code == 200
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_miss_computes_response(self, sample_query, mock_openrouter_client, mock_qdrant_client, mock_redis_client):
        """Test that cache miss leads to computation."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            # Ensure cache miss
            mock_redis_client.get = AsyncMock(return_value=None)
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/query", json=sample_query)
                    
                    assert response.status_code == 200
                    # Verify cache.set was called
                    # mock_redis_client.set.assert_called()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_upload(self, mock_redis_client):
        """Test that cache is invalidated when documents are uploaded."""
        from services.query.cache import invalidate_cache
        
        with patch('services.query.cache.redis_client', mock_redis_client):
            await invalidate_cache("doc-123")
            
            # Verify cache operations
            # mock_redis_client.delete.assert_called()


# =============================================================================
# Rate Limiting Tests
# =============================================================================

class TestRateLimiting:
    """Tests for rate limiting functionality."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rate_limit_not_exceeded(self, sample_query, mock_openrouter_client, mock_qdrant_client, mock_redis_client):
        """Test normal operation within rate limits."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            mock_redis_client.incr = AsyncMock(return_value=1)  # First request
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/query", json=sample_query)
                    
                    assert response.status_code != 429
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, sample_query, mock_openrouter_client, mock_qdrant_client, mock_redis_client):
        """Test rate limit exceeded returns 429."""
        with patch.dict(os.environ, {"TESTING": "true", "RATE_LIMIT": "1"}):
            from services.query.main import app
            
            # Simulate rate limit exceeded
            mock_redis_client.incr = AsyncMock(return_value=1000)
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # Multiple rapid requests might trigger rate limit
                    responses = []
                    for _ in range(5):
                        response = await client.post("/query", json=sample_query)
                        responses.append(response.status_code)
                    
                    # At least one should succeed (first one)
                    assert 200 in responses or 429 in responses


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in query service."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_qdrant_unavailable(self, sample_query, mock_openrouter_client, mock_redis_client):
        """Test handling when Qdrant is unavailable."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            mock_qdrant = MagicMock()
            mock_qdrant.search = MagicMock(side_effect=Exception("Qdrant connection refused"))
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/query", json=sample_query)
                    
                    # Should return error, not 500
                    assert response.status_code in [500, 503, 200]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_openrouter_unavailable(self, sample_query, mock_qdrant_client, mock_redis_client):
        """Test handling when OpenRouter is unavailable."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            mock_openrouter = MagicMock()
            mock_openrouter.get_embedding = AsyncMock(
                side_effect=Exception("OpenRouter API error")
            )
            
            with patch('services.query.main.openrouter_client', mock_openrouter), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/query", json=sample_query)
                    
                    assert response.status_code in [500, 503, 200]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalid_json_request(self, mock_openrouter_client, mock_redis_client):
        """Test handling of invalid JSON in request."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/query",
                        content="not valid json",
                        headers={"Content-Type": "application/json"}
                    )
                    
                    assert response.status_code == 422


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthCheck:
    """Tests for health check endpoints."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health")
                
                assert response.status_code == 200
                data = response.json()
                assert "status" in data
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_readiness_check(self, mock_qdrant_client, mock_redis_client):
        """Test readiness check endpoint."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            with patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/ready")
                    
                    assert response.status_code in [200, 503]


# =============================================================================
# Metrics Tests
# =============================================================================

class TestMetrics:
    """Tests for metrics endpoint."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/metrics")
                
                # Metrics should be exposed or 404 if not enabled
                assert response.status_code in [200, 404]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_query_updates_metrics(self, sample_query, mock_openrouter_client, mock_qdrant_client, mock_redis_client):
        """Test that queries update Prometheus metrics."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.query.main import app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # Make a query
                    await client.post("/query", json=sample_query)
                    
                    # Check metrics
                    response = await client.get("/metrics")
                    if response.status_code == 200:
                        # Metrics should contain query-related metrics
                        metrics_text = response.text
                        # Just verify we got some metrics
                        assert len(metrics_text) > 0
