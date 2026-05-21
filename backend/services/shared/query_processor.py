"""
Query Processing Module
Breaks down the long query_documents function into smaller, testable components.
"""
import hashlib
import time
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """Citation information for a retrieved document."""
    document_id: int
    title: str
    snippet: str
    similarity: float
    version: int
    chunk_index: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "document_id": self.document_id,
            "title": self.title,
            "snippet": self.snippet,
            "similarity": self.similarity,
            "version": self.version,
            "chunk_index": self.chunk_index
        }


@dataclass
class RetrievalResult:
    """Result of document retrieval."""
    success: bool
    context: str = ""
    citations: List[Citation] = field(default_factory=list)
    similarities: List[float] = field(default_factory=list)
    doc_ids: List[int] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class GenerationResult:
    """Result of answer generation."""
    success: bool
    answer: str = ""
    model: str = "unknown"
    tokens_used: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None


@dataclass
class QueryResult:
    """Complete query result."""
    answer: str
    confidence: float
    citations: List[Citation]
    latency_ms: int
    retrieved_count: int
    cache_hit: bool
    model_used: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "answer": self.answer,
            "confidence": self.confidence,
            "citations": [c.to_dict() for c in self.citations],
            "latency_ms": self.latency_ms,
            "retrieved_count": self.retrieved_count,
            "cache_hit": self.cache_hit,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd
        }


class CacheKeyGenerator:
    """Generates cache keys for queries."""
    
    @staticmethod
    def generate(question: str, top_k: int, workspace_id: str = "default", algorithm: str = "md5") -> str:
        """
        Generate cache key for a query.
        
        Args:
            question: The question text
            top_k: Number of results
            workspace_id: The workspace ID
            algorithm: Hash algorithm to use
            
        Returns:
            Cache key string
        """
        normalized = question.lower().strip()
        key_data = f"{workspace_id}:{normalized}:{top_k}"
        
        if algorithm == "md5":
            hash_hex = hashlib.md5(key_data.encode()).hexdigest()
        else:
            hash_hex = hashlib.sha256(key_data.encode()).hexdigest()
        
        return f"query:{workspace_id}:{hash_hex}"


class ConfidenceCalculator:
    """
    Calculates confidence scores for query answers.
    Implements multiple strategies for confidence calculation.
    """
    
    def __init__(
        self,
        retrieval_weight: float = 0.4,
        groundedness_weight: float = 0.3,
        completeness_weight: float = 0.3
    ):
        """
        Initialize calculator with weights.
        
        Args:
            retrieval_weight: Weight for retrieval similarity (0-1)
            groundedness_weight: Weight for answer groundedness (0-1)
            completeness_weight: Weight for answer completeness (0-1)
        """
        total = retrieval_weight + groundedness_weight + completeness_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        
        self.retrieval_weight = retrieval_weight
        self.groundedness_weight = groundedness_weight
        self.completeness_weight = completeness_weight
    
    def calculate(
        self,
        similarities: List[float],
        answer: str,
        context: str
    ) -> float:
        """
        Calculate confidence score.
        
        Args:
            similarities: List of similarity scores (0-1)
            answer: Generated answer text
            context: Source context text
            
        Returns:
            Confidence score as percentage (0-100)
        """
        retrieval_score = self._calculate_retrieval_score(similarities)
        groundedness_score = self._calculate_groundedness(answer, context)
        completeness_score = self._calculate_completeness(answer)
        
        confidence = (
            self.retrieval_weight * retrieval_score +
            self.groundedness_weight * groundedness_score +
            self.completeness_weight * completeness_score
        )
        
        return round(confidence * 100, 1)
    
    def _calculate_retrieval_score(self, similarities: List[float]) -> float:
        """Calculate retrieval quality score."""
        if not similarities:
            return 0.0
        return sum(similarities) / len(similarities)
    
    def _calculate_groundedness(self, answer: str, context: str) -> float:
        """Calculate how well the answer is grounded in the context."""
        if not answer or not context:
            return 0.0
        
        answer_words = set(answer.lower().split())
        context_words = set(context.lower().split())
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 
                      'been', 'being', 'have', 'has', 'had', 'do', 'does', 
                      'did', 'will', 'would', 'could', 'should', 'may', 
                      'might', 'must', 'shall', 'can', 'of', 'to', 'in', 
                      'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                      'through', 'during', 'before', 'after', 'above', 'below',
                      'and', 'but', 'or', 'nor', 'so', 'yet', 'both', 'either',
                      'neither', 'not', 'only', 'own', 'same', 'than', 'too',
                      'very', 'just', 'that', 'this', 'these', 'those', 'i',
                      'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which',
                      'who', 'whom', 'whose', 'when', 'where', 'why', 'how'}
        
        answer_words = answer_words - stop_words
        context_words = context_words - stop_words
        
        if not answer_words:
            return 0.5  # Neutral if no meaningful words
        
        overlap = len(answer_words & context_words)
        return min(overlap / len(answer_words), 1.0)
    
    def _calculate_completeness(self, answer: str) -> float:
        """Calculate answer completeness score."""
        if not answer:
            return 0.0
        
        # Phrases indicating uncertainty
        uncertainty_phrases = [
            "i don't know",
            "don't have",
            "insufficient",
            "cannot answer",
            "no information",
            "not mentioned",
            "not specified",
            "unable to"
        ]
        
        answer_lower = answer.lower()
        
        # Check for uncertainty
        for phrase in uncertainty_phrases:
            if phrase in answer_lower:
                return 0.0
        
        # Check minimum length (at least 20 chars for a complete answer)
        if len(answer) < 20:
            return 0.3
        
        return 1.0


class ContextBuilder:
    """Builds context from retrieved documents."""
    
    def __init__(self, max_context_length: int = 4000):
        """
        Initialize context builder.
        
        Args:
            max_context_length: Maximum context length in characters
        """
        self.max_context_length = max_context_length
    
    def build(
        self,
        search_results: List[Any],
        include_source_markers: bool = True
    ) -> Tuple[str, List[Citation]]:
        """
        Build context and citations from search results.
        
        Args:
            search_results: Results from vector search
            include_source_markers: Whether to include source markers
            
        Returns:
            Tuple of (context_string, list_of_citations)
        """
        context_parts: List[str] = []
        citations: List[Citation] = []
        current_length = 0
        
        for idx, result in enumerate(search_results, 1):
            payload = result.payload
            text = payload.get('text', '')
            
            # Check if adding this would exceed limit
            marker = f"[Source {idx}: {payload.get('title', 'Unknown')}]\n" if include_source_markers else ""
            entry = f"{marker}{text}\n"
            
            if current_length + len(entry) > self.max_context_length:
                # Truncate if necessary
                available = self.max_context_length - current_length - len(marker) - 10
                if available > 100:  # Only add if we have at least 100 chars
                    text = text[:available] + "..."
                    entry = f"{marker}{text}\n"
                else:
                    break
            
            context_parts.append(entry)
            current_length += len(entry)
            
            # Create citation
            snippet = text[:200] + "..." if len(text) > 200 else text
            citations.append(Citation(
                document_id=payload.get('document_id', 0),
                title=payload.get('title', 'Unknown'),
                snippet=snippet,
                similarity=round(result.score * 100, 1),
                version=payload.get('version', 1),
                chunk_index=payload.get('chunk_index', 0)
            ))
        
        return "\n".join(context_parts), citations


class QueryProcessor:
    """
    Main query processing orchestrator.
    Coordinates embedding, retrieval, and generation.
    """
    
    def __init__(
        self,
        embedding_client: Optional[Any] = None,
        vector_store: Optional[Any] = None,
        llm_client: Optional[Any] = None,
        cache: Optional[Any] = None,
        confidence_calculator: Optional[ConfidenceCalculator] = None,
        context_builder: Optional[ContextBuilder] = None
    ):
        """
        Initialize query processor.
        
        Args:
            embedding_client: Client for generating embeddings
            vector_store: Qdrant client for vector search
            llm_client: OpenRouter/OpenAI client for generation
            cache: Redis cache
            confidence_calculator: Optional custom confidence calculator
            context_builder: Optional custom context builder
        """
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.cache = cache
        self.confidence_calculator = confidence_calculator or ConfidenceCalculator()
        self.context_builder = context_builder or ContextBuilder()
        self.cache_key_generator = CacheKeyGenerator()
    
    async def check_cache(
        self,
        question: str,
        top_k: int,
        workspace_id: str = "default"
    ) -> Optional[QueryResult]:
        """
        Check if result is cached.
        
        Args:
            question: Query question
            top_k: Number of results
            workspace_id: Workspace ID
            
        Returns:
            Cached QueryResult or None
        """
        if not self.cache:
            return None
        
        cache_key = self.cache_key_generator.generate(question, top_k, workspace_id)
        cached = await self.cache.get(cache_key)
        
        if cached:
            logger.info(f"⚡ Cache HIT: {cache_key[:20]}...")
            cached['cache_hit'] = True
            return QueryResult(**cached)
        
        logger.info(f"❌ Cache MISS: {cache_key[:20]}...")
        return None
    
    async def cache_result(
        self,
        question: str,
        top_k: int,
        result: QueryResult,
        workspace_id: str = "default",
        ttl_seconds: int = 7200
    ) -> None:
        """
        Cache a query result.
        
        Args:
            question: Query question
            top_k: Number of results
            workspace_id: Workspace ID
            result: Result to cache
            ttl_seconds: Cache TTL
        """
        if not self.cache:
            return
        
        cache_key = self.cache_key_generator.generate(question, top_k, workspace_id)
        await self.cache.set(cache_key, result.to_dict(), ttl_seconds=ttl_seconds)
        logger.info(f"💾 Cached result: {cache_key[:20]}...")
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        if not self.embedding_client:
            return self._mock_embedding(text)
        
        try:
            return await self.embedding_client.get_embedding(text)
        except Exception as e:
            logger.warning(f"Embedding error: {e}, using mock")
            return self._mock_embedding(text)
    
    async def retrieve_documents(
        self,
        embedding: List[float],
        top_k: int = 3,
        min_similarity: float = 0.0
    ) -> RetrievalResult:
        """
        Retrieve relevant documents.
        
        Args:
            embedding: Query embedding
            top_k: Number of results
            min_similarity: Minimum similarity threshold
            
        Returns:
            RetrievalResult with context and citations
        """
        if not self.vector_store:
            return RetrievalResult(
                success=False,
                error="Vector store not available"
            )
        
        try:
            search_results = self.vector_store.search(
                collection_name="documents",
                query_vector=embedding,
                limit=top_k,
                score_threshold=min_similarity
            )
            
            if not search_results:
                return RetrievalResult(
                    success=False,
                    error="No relevant documents found"
                )
            
            context, citations = self.context_builder.build(search_results)
            
            return RetrievalResult(
                success=True,
                context=context,
                citations=citations,
                similarities=[r.score for r in search_results],
                doc_ids=[r.payload.get('document_id', 0) for r in search_results]
            )
            
        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return RetrievalResult(
                success=False,
                error=str(e)
            )
    
    async def generate_answer(
        self,
        question: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> GenerationResult:
        """
        Generate answer using LLM.
        
        Args:
            question: User question
            context: Retrieved context
            system_prompt: Optional system prompt
            
        Returns:
            GenerationResult with answer
        """
        if not self.llm_client:
            return GenerationResult(
                success=True,
                answer=f"[Mock] Based on the context, here's an answer to: {question}",
                model="mock"
            )
        
        default_prompt = """You are a helpful assistant that answers questions based ONLY on the provided context.
If the context doesn't contain enough information to answer the question, say "I don't have enough information to answer that question."
Always cite which document you're referencing."""
        
        try:
            result = await self.llm_client.generate_answer(
                question=question,
                context=context,
                system_prompt=system_prompt or default_prompt
            )
            
            return GenerationResult(
                success=True,
                answer=result.get('answer', ''),
                model=result.get('model', 'unknown'),
                tokens_used=result.get('total_tokens', 0),
                cost_usd=result.get('cost_usd', 0.0)
            )
            
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return GenerationResult(
                success=False,
                error=str(e)
            )
    
    async def process(
        self,
        question: str,
        workspace_id: str = "default",
        top_k: int = 3,
        use_cache: bool = True,
        min_similarity: float = 0.0
    ) -> QueryResult:
        """
        Process a complete query.
        
        Args:
            question: User question
            workspace_id: Workspace ID
            top_k: Number of documents to retrieve
            use_cache: Whether to use cache
            min_similarity: Minimum similarity threshold
            
        Returns:
            QueryResult with answer and metadata
        """
        start_time = time.time()
        
        # Check cache
        if use_cache:
            cached = await self.check_cache(question, top_k, workspace_id)
            if cached:
                cached.latency_ms = int((time.time() - start_time) * 1000)
                return cached
        
        # Get embedding
        embedding = await self.get_embedding(question)
        
        # Retrieve documents
        retrieval = await self.retrieve_documents(embedding, top_k, min_similarity)
        
        if not retrieval.success:
            raise ValueError(retrieval.error)
        
        # Generate answer
        generation = await self.generate_answer(question, retrieval.context)
        
        if not generation.success:
            raise ValueError(generation.error)
        
        # Calculate confidence
        confidence = self.confidence_calculator.calculate(
            retrieval.similarities,
            generation.answer,
            retrieval.context
        )
        
        # Build result
        latency_ms = int((time.time() - start_time) * 1000)
        
        result = QueryResult(
            answer=generation.answer,
            confidence=confidence,
            citations=retrieval.citations,
            latency_ms=latency_ms,
            retrieved_count=len(retrieval.citations),
            cache_hit=False,
            model_used=generation.model,
            tokens_used=generation.tokens_used,
            cost_usd=generation.cost_usd
        )
        
        # Cache result
        if use_cache:
            await self.cache_result(question, top_k, result, workspace_id)
        
        return result
    
    def _mock_embedding(self, text: str) -> List[float]:
        """Generate deterministic mock embedding."""
        import random
        hash_obj = hashlib.md5(text.encode())
        seed = int(hash_obj.hexdigest(), 16)
        random.seed(seed)
        return [random.random() for _ in range(1536)]
