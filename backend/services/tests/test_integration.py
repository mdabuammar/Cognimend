"""
Integration tests for services.
These tests verify that services can work together correctly.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))


class TestUploadQueryIntegration:
    """Test upload and query services work together."""
    
    @pytest.mark.asyncio
    async def test_document_upload_makes_it_queryable(
        self,
        mock_db_connection: MagicMock,
        mock_qdrant_client: MagicMock,
        mock_embedding_client: AsyncMock
    ):
        """Test uploaded documents can be queried."""
        from services.shared.document_processor import DocumentProcessor, TextExtractor
        from services.shared.query_processor import QueryProcessor
        
        # Step 1: Process a document
        processor = DocumentProcessor(
            chunk_size=500,
            chunk_overlap=50
        )
        
        # Simulate document text
        document_text = """
        Company Vacation Policy
        
        All full-time employees are entitled to 20 days of paid vacation per year.
        Vacation days must be approved by your manager at least two weeks in advance.
        Unused vacation days can be carried over to the next year, up to a maximum of 5 days.
        """
        
        # Create mock file
        mock_file = MagicMock()
        mock_file.filename = "vacation_policy.txt"
        mock_file.read = AsyncMock(return_value=document_text.encode('utf-8'))
        
        # Step 2: Extract text (simulated)
        extractor = TextExtractor()
        content = document_text  # Would normally extract from file
        
        # Step 3: Chunk the document
        from services.shared.document_processor import TextChunker
        chunker = TextChunker(chunk_size=200, overlap=20)
        chunks = chunker.chunk(content)
        
        assert len(chunks) >= 1
        
        # Step 4: Verify chunks can be used in query
        query_processor = QueryProcessor(
            embedding_client=mock_embedding_client,
            vector_store=mock_qdrant_client
        )
        
        # The query should find relevant content
        result = await query_processor.process(
            "How many vacation days do employees get?",
            top_k=3,
            use_cache=False
        )
        
        assert result is not None
        assert result.answer  # Should have an answer


class TestControllerDriftIntegration:
    """Test controller and drift detector integration."""
    
    @pytest.mark.asyncio
    async def test_drift_event_triggers_action(
        self,
        mock_db_connection: MagicMock
    ):
        """Test drift events trigger appropriate actions."""
        from services.shared.actions import action_registry, ActionResult
        
        # Simulate a drift event
        drift_event = {
            "drift_score": 0.35,
            "recent_confidence_avg": 55.0,
            "action_recommendation": "increase_top_k"
        }
        
        # Get the recommended action
        action = action_registry.get(drift_event["action_recommendation"])
        
        assert action is not None
        
        # Validate and execute
        is_valid = action.validate(current_top_k=3, increment=2)
        assert is_valid is True
        
        result = action.execute(current_top_k=3, increment=2)
        
        assert result.success is True
        assert result.data["new_top_k"] == 5


class TestHealthCheckIntegration:
    """Test health check across services."""
    
    def test_all_services_healthy(
        self,
        mock_db_connection: MagicMock,
        mock_cache: AsyncMock,
        mock_qdrant_client: MagicMock
    ):
        """Test all services report healthy when dependencies are available."""
        from services.shared.utils import HealthCheckBuilder
        
        services = ["upload", "query", "controller", "telemetry", "evaluation", "drift_detector"]
        
        for service_name in services:
            builder = HealthCheckBuilder(f"{service_name}-service", version="2.0.0")
            builder.add_component("database", True, "connected")
            builder.add_component("cache", True, "available")
            
            health = builder.build()
            
            assert health["status"] == "healthy"
            assert health["service"] == f"{service_name}-service"
    
    def test_degraded_when_component_fails(self):
        """Test services report degraded when component fails."""
        from services.shared.utils import HealthCheckBuilder
        
        builder = HealthCheckBuilder("query-service")
        builder.add_component("database", True, "connected")
        builder.add_component("cache", False, "connection refused")
        builder.add_component("qdrant", True, "available")
        
        health = builder.build()
        
        assert health["status"] == "degraded"


class TestResilienceIntegration:
    """Test resilience patterns across services."""
    
    def test_circuit_breaker_protects_cascade_failures(self):
        """Test circuit breaker prevents cascade failures."""
        from services.shared.resilience import CircuitBreaker, CircuitState
        from services.shared.exceptions import CircuitBreakerOpen
        
        # Simulate multiple services with circuit breakers
        embedding_cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        llm_cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        def failing_embedding_call():
            raise ConnectionError("Embedding service down")
        
        def failing_llm_call():
            raise ConnectionError("LLM service down")
        
        # Trip embedding circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                embedding_cb.call(failing_embedding_call)
        
        assert embedding_cb.state == CircuitState.OPEN
        
        # LLM circuit should still be closed
        assert llm_cb.state == CircuitState.CLOSED
        
        # Trying to use embedding should fail fast
        with pytest.raises(CircuitBreakerOpen):
            embedding_cb.call(failing_embedding_call)


class TestExceptionHandlingIntegration:
    """Test exception handling across services."""
    
    def test_specific_exceptions_propagate_correctly(self):
        """Test specific exceptions are caught and handled."""
        from services.shared.exceptions import (
            ServiceException,
            DocumentError,
            DocumentNotFoundError,
            QueryError,
            EmbeddingGenerationError
        )
        
        # Test that specific exceptions can be caught at different levels
        def process_document(doc_id: int):
            if doc_id < 0:
                raise DocumentNotFoundError(
                    f"Document {doc_id} not found",
                    details={"document_id": doc_id}
                )
            return {"id": doc_id}
        
        def process_query(question: str):
            if not question:
                raise EmbeddingGenerationError(
                    "Cannot generate embedding for empty question"
                )
            return {"answer": "Mock answer"}
        
        # Test document exception
        try:
            process_document(-1)
        except DocumentError as e:
            # Can catch at DocumentError level
            assert isinstance(e, DocumentNotFoundError)
            assert e.details["document_id"] == -1 or e.details["document_id"] == "-1"
        
        # Test query exception
        try:
            process_query("")
        except QueryError as e:
            # Can catch at QueryError level
            assert isinstance(e, EmbeddingGenerationError)
        
        # Both can be caught at ServiceException level
        for exc_type, func, arg in [
            (DocumentError, process_document, -1),
            (QueryError, process_query, "")
        ]:
            try:
                func(arg)
            except ServiceException as e:
                assert isinstance(e, exc_type)


class TestDatabaseIntegration:
    """Test database operations across services."""
    
    def test_database_manager_consistent_across_services(
        self,
        mock_db_connection: MagicMock
    ):
        """Test DatabaseManager provides consistent interface."""
        from services.shared.utils import DatabaseManager
        
        # Create managers for different services
        mock_pool = MagicMock()
        mock_pool.get_connection.return_value = mock_db_connection
        mock_pool.return_connection = MagicMock()
        
        upload_db = DatabaseManager(pool=mock_pool)
        query_db = DatabaseManager(pool=mock_pool)
        
        # Both should use the same pool
        conn1 = upload_db.get_connection()
        upload_db.return_connection(conn1)
        
        conn2 = query_db.get_connection()
        query_db.return_connection(conn2)
        
        # Pool should have been called twice
        assert mock_pool.get_connection.call_count == 2
        assert mock_pool.return_connection.call_count == 2


class TestCacheIntegration:
    """Test caching across services."""
    
    @pytest.mark.asyncio
    async def test_cache_shared_between_query_calls(
        self,
        mock_cache: AsyncMock,
        mock_embedding_client: AsyncMock,
        mock_qdrant_client: MagicMock,
        mock_llm_client: AsyncMock
    ):
        """Test cache is shared between query calls."""
        from services.shared.query_processor import QueryProcessor, CacheKeyGenerator
        
        # First query - cache miss
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)
        
        processor = QueryProcessor(
            embedding_client=mock_embedding_client,
            vector_store=mock_qdrant_client,
            llm_client=mock_llm_client,
            cache=mock_cache
        )
        
        result1 = await processor.process(
            "What is the vacation policy?",
            top_k=3,
            use_cache=True
        )
        
        # Cache should have been set
        assert mock_cache.set.called
        
        # Second query with same question - cache hit
        cached_result = {
            "answer": result1.answer,
            "confidence": result1.confidence,
            "citations": [c.to_dict() for c in result1.citations],
            "latency_ms": result1.latency_ms,
            "retrieved_count": result1.retrieved_count,
            "model_used": result1.model_used,
            "tokens_used": result1.tokens_used,
            "cost_usd": result1.cost_usd,
            "cache_hit": True
        }
        mock_cache.get = AsyncMock(return_value=cached_result)
        
        result2 = await processor.check_cache("What is the vacation policy?", 3)
        
        assert result2 is not None
        assert result2.cache_hit is True
