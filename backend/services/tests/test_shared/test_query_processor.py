"""
Tests for query processor module.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from services.shared.query_processor import (
    CacheKeyGenerator,
    ConfidenceCalculator,
    ContextBuilder,
    QueryProcessor,
    Citation,
    QueryResult,
    RetrievalResult,
    GenerationResult
)


class TestCacheKeyGenerator:
    """Tests for CacheKeyGenerator class."""
    
    def test_generate_deterministic(self):
        """Test cache key generation is deterministic."""
        key1 = CacheKeyGenerator.generate("test question", 3)
        key2 = CacheKeyGenerator.generate("test question", 3)
        
        assert key1 == key2
    
    def test_generate_different_questions(self):
        """Test different questions produce different keys."""
        key1 = CacheKeyGenerator.generate("question 1", 3)
        key2 = CacheKeyGenerator.generate("question 2", 3)
        
        assert key1 != key2
    
    def test_generate_different_top_k(self):
        """Test different top_k produces different keys."""
        key1 = CacheKeyGenerator.generate("test question", 3)
        key2 = CacheKeyGenerator.generate("test question", 5)
        
        assert key1 != key2
    
    def test_generate_case_insensitive(self):
        """Test cache key is case insensitive."""
        key1 = CacheKeyGenerator.generate("Test Question", 3)
        key2 = CacheKeyGenerator.generate("test question", 3)
        
        assert key1 == key2
    
    def test_generate_whitespace_normalized(self):
        """Test cache key normalizes whitespace."""
        key1 = CacheKeyGenerator.generate("  test question  ", 3)
        key2 = CacheKeyGenerator.generate("test question", 3)
        
        assert key1 == key2
    
    def test_generate_prefix(self):
        """Test cache key has correct prefix."""
        key = CacheKeyGenerator.generate("test", 3)
        
        assert key.startswith("query:")


class TestConfidenceCalculator:
    """Tests for ConfidenceCalculator class."""
    
    def test_init_valid_weights(self):
        """Test initialization with valid weights."""
        calc = ConfidenceCalculator(0.4, 0.3, 0.3)
        
        assert calc.retrieval_weight == 0.4
        assert calc.groundedness_weight == 0.3
        assert calc.completeness_weight == 0.3
    
    def test_init_invalid_weights(self):
        """Test initialization with invalid weights."""
        with pytest.raises(ValueError) as exc_info:
            ConfidenceCalculator(0.5, 0.5, 0.5)  # Sum = 1.5
        
        assert "must sum to 1.0" in str(exc_info.value)
    
    def test_calculate_high_confidence(self):
        """Test calculating high confidence."""
        calc = ConfidenceCalculator()
        
        confidence = calc.calculate(
            similarities=[0.9, 0.85, 0.8],
            answer="The vacation policy allows employees to take 20 days per year.",
            context="The vacation policy allows employees to take up to 20 days per year."
        )
        
        assert confidence >= 70  # Should be high confidence
    
    def test_calculate_low_similarity(self):
        """Test calculating with low similarities."""
        calc = ConfidenceCalculator()
        
        confidence = calc.calculate(
            similarities=[0.3, 0.25, 0.2],
            answer="Some answer",
            context="Some context"
        )
        
        assert confidence < 50  # Should be lower
    
    def test_calculate_uncertain_answer(self):
        """Test calculating with uncertain answer."""
        calc = ConfidenceCalculator()
        
        confidence = calc.calculate(
            similarities=[0.9, 0.85],
            answer="I don't know the answer to that question.",
            context="The vacation policy allows 20 days."
        )
        
        # Completeness should be 0 due to uncertainty phrase
        assert confidence < 70
    
    def test_calculate_empty_similarities(self):
        """Test calculating with empty similarities."""
        calc = ConfidenceCalculator()
        
        confidence = calc.calculate(
            similarities=[],
            answer="Test answer",
            context="Test context"
        )
        
        assert confidence >= 0  # Should not crash
    
    def test_calculate_empty_answer(self):
        """Test calculating with empty answer."""
        calc = ConfidenceCalculator()
        
        confidence = calc.calculate(
            similarities=[0.9],
            answer="",
            context="Test context"
        )
        
        assert confidence >= 0  # Should not crash


class TestContextBuilder:
    """Tests for ContextBuilder class."""
    
    def test_build_basic(self, mock_qdrant_client: MagicMock):
        """Test basic context building."""
        builder = ContextBuilder()
        
        # Create mock search results
        mock_result = MagicMock()
        mock_result.score = 0.85
        mock_result.payload = {
            'document_id': 1,
            'title': 'Test Doc',
            'text': 'This is the document content.',
            'version': 1,
            'chunk_index': 0
        }
        
        context, citations = builder.build([mock_result])
        
        assert "Test Doc" in context
        assert "This is the document content" in context
        assert len(citations) == 1
        assert citations[0].document_id == 1
    
    def test_build_multiple_results(self):
        """Test building context from multiple results."""
        builder = ContextBuilder()
        
        results = []
        for i in range(3):
            mock_result = MagicMock()
            mock_result.score = 0.9 - i * 0.1
            mock_result.payload = {
                'document_id': i + 1,
                'title': f'Document {i + 1}',
                'text': f'Content for document {i + 1}',
                'version': 1,
                'chunk_index': 0
            }
            results.append(mock_result)
        
        context, citations = builder.build(results)
        
        assert len(citations) == 3
        assert "[Source 1:" in context
        assert "[Source 2:" in context
        assert "[Source 3:" in context
    
    def test_build_without_markers(self):
        """Test building context without source markers."""
        builder = ContextBuilder()
        
        mock_result = MagicMock()
        mock_result.score = 0.85
        mock_result.payload = {
            'document_id': 1,
            'title': 'Test Doc',
            'text': 'Content here',
            'version': 1
        }
        
        context, citations = builder.build([mock_result], include_source_markers=False)
        
        assert "[Source" not in context
        assert "Content here" in context
    
    def test_build_truncates_long_content(self):
        """Test context is truncated when too long."""
        builder = ContextBuilder(max_context_length=100)
        
        mock_result = MagicMock()
        mock_result.score = 0.85
        mock_result.payload = {
            'document_id': 1,
            'title': 'Test',
            'text': 'x' * 500,  # Very long content
            'version': 1
        }
        
        context, citations = builder.build([mock_result])
        
        assert len(context) <= 150  # Some buffer for markers
    
    def test_citation_snippet_truncation(self):
        """Test citation snippets are truncated."""
        builder = ContextBuilder()
        
        long_text = "x" * 500
        mock_result = MagicMock()
        mock_result.score = 0.85
        mock_result.payload = {
            'document_id': 1,
            'title': 'Test',
            'text': long_text,
            'version': 1
        }
        
        _, citations = builder.build([mock_result])
        
        assert len(citations[0].snippet) <= 203  # 200 + "..."


class TestQueryProcessor:
    """Tests for QueryProcessor class."""
    
    @pytest.mark.asyncio
    async def test_check_cache_miss(self, mock_cache: AsyncMock):
        """Test cache miss."""
        mock_cache.get = AsyncMock(return_value=None)
        
        processor = QueryProcessor(cache=mock_cache)
        result = await processor.check_cache("test question", 3)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_check_cache_hit(self, mock_cache: AsyncMock, sample_query_result: dict):
        """Test cache hit."""
        mock_cache.get = AsyncMock(return_value=sample_query_result)
        
        processor = QueryProcessor(cache=mock_cache)
        result = await processor.check_cache("test question", 3)
        
        assert result is not None
        assert result.cache_hit is True
    
    @pytest.mark.asyncio
    async def test_get_embedding_with_client(self, mock_embedding_client: AsyncMock):
        """Test getting embedding with client."""
        processor = QueryProcessor(embedding_client=mock_embedding_client)
        
        embedding = await processor.get_embedding("test question")
        
        assert len(embedding) == 1536
    
    @pytest.mark.asyncio
    async def test_get_embedding_fallback_mock(self):
        """Test mock embedding when no client."""
        processor = QueryProcessor()
        
        embedding = await processor.get_embedding("test question")
        
        assert len(embedding) == 1536
    
    @pytest.mark.asyncio
    async def test_retrieve_documents_success(self, mock_qdrant_client: MagicMock):
        """Test successful document retrieval."""
        processor = QueryProcessor(vector_store=mock_qdrant_client)
        
        result = await processor.retrieve_documents([0.1] * 1536)
        
        assert result.success is True
        assert len(result.citations) > 0
        assert len(result.context) > 0
    
    @pytest.mark.asyncio
    async def test_retrieve_documents_no_store(self):
        """Test retrieval with no vector store."""
        processor = QueryProcessor()
        
        result = await processor.retrieve_documents([0.1] * 1536)
        
        assert result.success is False
        assert "not available" in result.error
    
    @pytest.mark.asyncio
    async def test_generate_answer_with_client(self, mock_llm_client: AsyncMock):
        """Test answer generation with client."""
        processor = QueryProcessor(llm_client=mock_llm_client)
        
        result = await processor.generate_answer(
            "What is the vacation policy?",
            "The vacation policy allows 20 days per year."
        )
        
        assert result.success is True
        assert len(result.answer) > 0
    
    @pytest.mark.asyncio
    async def test_generate_answer_mock(self):
        """Test mock answer when no client."""
        processor = QueryProcessor()
        
        result = await processor.generate_answer(
            "Test question?",
            "Test context"
        )
        
        assert result.success is True
        assert "[Mock]" in result.answer
    
    @pytest.mark.asyncio
    async def test_process_full_query(
        self,
        mock_embedding_client: AsyncMock,
        mock_qdrant_client: MagicMock,
        mock_llm_client: AsyncMock
    ):
        """Test full query processing."""
        processor = QueryProcessor(
            embedding_client=mock_embedding_client,
            vector_store=mock_qdrant_client,
            llm_client=mock_llm_client
        )
        
        result = await processor.process(
            "What is the vacation policy?",
            top_k=3,
            use_cache=False
        )
        
        assert isinstance(result, QueryResult)
        assert len(result.answer) > 0
        assert result.confidence >= 0
        assert result.latency_ms >= 0
    
    @pytest.mark.asyncio
    async def test_process_with_cache(
        self,
        mock_cache: AsyncMock,
        mock_embedding_client: AsyncMock,
        mock_qdrant_client: MagicMock,
        mock_llm_client: AsyncMock,
        sample_query_result: dict
    ):
        """Test query processing uses cache."""
        mock_cache.get = AsyncMock(return_value=sample_query_result)
        
        processor = QueryProcessor(
            embedding_client=mock_embedding_client,
            vector_store=mock_qdrant_client,
            llm_client=mock_llm_client,
            cache=mock_cache
        )
        
        result = await processor.process("test question", use_cache=True)
        
        assert result.cache_hit is True
        # Should not call embedding client when using cache
        mock_embedding_client.get_embedding.assert_not_called()


class TestCitation:
    """Tests for Citation dataclass."""
    
    def test_to_dict(self):
        """Test citation to dictionary conversion."""
        citation = Citation(
            document_id=1,
            title="Test Doc",
            snippet="Test snippet",
            similarity=85.5,
            version=1,
            chunk_index=0
        )
        
        result = citation.to_dict()
        
        assert result["document_id"] == 1
        assert result["title"] == "Test Doc"
        assert result["similarity"] == 85.5


class TestQueryResult:
    """Tests for QueryResult dataclass."""
    
    def test_to_dict(self):
        """Test query result to dictionary conversion."""
        citation = Citation(
            document_id=1,
            title="Test",
            snippet="Snippet",
            similarity=90.0,
            version=1
        )
        
        result = QueryResult(
            answer="Test answer",
            confidence=85.0,
            citations=[citation],
            latency_ms=150,
            retrieved_count=1,
            cache_hit=False,
            model_used="gpt-4",
            tokens_used=100,
            cost_usd=0.01
        )
        
        data = result.to_dict()
        
        assert data["answer"] == "Test answer"
        assert data["confidence"] == 85.0
        assert len(data["citations"]) == 1
        assert data["latency_ms"] == 150
