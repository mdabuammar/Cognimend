"""
Locust Load Test for Cognimend RAG System

This test file implements comprehensive load testing using Locust framework.
It includes weighted tasks for query, upload, and metrics operations.

Usage:
    # Web UI mode (recommended for interactive testing)
    locust -f locustfile.py --host=http://localhost:8002

    # Headless mode (CI/CD)
    locust -f locustfile.py --headless -u 100 -r 10 --run-time 5m --host=http://localhost:8002

    # With HTML report
    locust -f locustfile.py --headless -u 100 -r 10 --run-time 5m --host=http://localhost:8002 --html=report.html
"""

import os
import json
import time
import random
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from statistics import mean, median, stdev

from locust import HttpUser, task, between, events, tag
from locust.runners import MasterRunner, WorkerRunner
from locust.env import Environment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class Config:
    """Load test configuration"""
    api_key: str = os.getenv("API_KEY", "test-api-key")
    upload_host: str = os.getenv("UPLOAD_URL", "http://localhost:8001")
    max_users: int = int(os.getenv("MAX_USERS", "500"))
    spawn_rate: int = int(os.getenv("SPAWN_RATE", "10"))
    
    # Thresholds
    query_latency_p95_threshold_ms: int = 3000
    query_latency_p99_threshold_ms: int = 5000
    upload_latency_p95_threshold_ms: int = 10000
    error_rate_threshold: float = 0.05
    min_confidence_threshold: float = 0.5


config = Config()


# =============================================================================
# Test Data
# =============================================================================

TEST_QUERIES = [
    "What is machine learning and how does it work?",
    "Explain the concept of neural networks in simple terms",
    "How does RAG (Retrieval Augmented Generation) improve LLM responses?",
    "What are transformer models and why are they important?",
    "Describe the attention mechanism in deep learning",
    "What is natural language processing and its applications?",
    "How do word embeddings capture semantic meaning?",
    "Explain the difference between supervised and unsupervised learning",
    "What are vector databases and why are they used with LLMs?",
    "How does fine-tuning work for language models?",
]

ADVANCED_QUERIES = [
    "Compare the performance of BERT vs GPT models for text classification",
    "What are the best practices for chunking documents in RAG systems?",
    "How can I optimize embedding model inference latency?",
    "Explain the trade-offs between different retrieval strategies",
    "What metrics should I use to evaluate RAG system quality?",
]

SAMPLE_DOCUMENTS = [
    {
        "name": "machine_learning_basics.txt",
        "content": """
Machine Learning Fundamentals

Machine learning is a subset of artificial intelligence (AI) that enables systems 
to learn and improve from experience without being explicitly programmed. It focuses 
on developing algorithms that can access data, learn from it, and make predictions 
or decisions based on that learning.

Key Concepts:
1. Supervised Learning: Training models with labeled data
2. Unsupervised Learning: Finding patterns in unlabeled data
3. Reinforcement Learning: Learning through trial and error with rewards
4. Deep Learning: Neural networks with multiple layers
"""
    },
    {
        "name": "neural_networks.txt",
        "content": """
Neural Networks Explained

A neural network is a computational model inspired by the structure and function 
of the human brain. It consists of interconnected nodes (neurons) organized in layers.

Architecture:
- Input Layer: Receives raw data
- Hidden Layers: Process and transform data
- Output Layer: Produces final predictions

Training involves adjusting weights through backpropagation to minimize error.
"""
    },
    {
        "name": "rag_systems.txt",
        "content": """
Retrieval Augmented Generation (RAG)

RAG combines retrieval-based and generation-based approaches for improved 
language model performance. It retrieves relevant context from a knowledge 
base and uses it to generate more accurate, grounded responses.

Benefits:
- Reduced hallucination
- Up-to-date information
- Domain-specific knowledge
- Traceable sources
"""
    },
    {
        "name": "transformers.txt",
        "content": """
Transformer Architecture

Transformers revolutionized NLP with their attention mechanism, enabling 
parallel processing and capturing long-range dependencies in text.

Key Components:
1. Self-Attention: Weighs importance of different input positions
2. Multi-Head Attention: Multiple attention layers in parallel
3. Positional Encoding: Maintains sequence order information
4. Feed-Forward Networks: Process attention outputs
"""
    },
    {
        "name": "embeddings.txt",
        "content": """
Word and Sentence Embeddings

Embeddings are dense vector representations of text that capture semantic meaning.
Similar texts have similar embedding vectors, enabling semantic search.

Embedding Types:
1. Word Embeddings: Word2Vec, GloVe, FastText
2. Sentence Embeddings: BERT, Sentence-BERT
3. Document Embeddings: Doc2Vec, paragraph vectors

Popular embedding models: OpenAI Ada, Cohere Embed, all-MiniLM-L6-v2
"""
    },
]


# =============================================================================
# Custom Metrics Collection
# =============================================================================

@dataclass
class CustomMetrics:
    """Custom metrics collector for detailed analysis"""
    confidence_scores: List[float] = field(default_factory=list)
    tokens_used: List[int] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
    query_latencies: List[float] = field(default_factory=list)
    upload_latencies: List[float] = field(default_factory=list)
    successful_queries: int = 0
    failed_queries: int = 0
    successful_uploads: int = 0
    failed_uploads: int = 0

    def add_query_result(
        self,
        success: bool,
        latency_ms: float,
        confidence: Optional[float] = None,
        tokens: Optional[int] = None,
        cached: bool = False
    ):
        """Record query result metrics"""
        self.query_latencies.append(latency_ms)
        
        if success:
            self.successful_queries += 1
            if confidence is not None:
                self.confidence_scores.append(confidence)
            if tokens is not None:
                self.tokens_used.append(tokens)
            if cached:
                self.cache_hits += 1
            else:
                self.cache_misses += 1
        else:
            self.failed_queries += 1

    def add_upload_result(self, success: bool, latency_ms: float):
        """Record upload result metrics"""
        self.upload_latencies.append(latency_ms)
        if success:
            self.successful_uploads += 1
        else:
            self.failed_uploads += 1

    def get_percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile from data list"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def get_summary(self) -> Dict[str, Any]:
        """Generate metrics summary"""
        total_queries = self.successful_queries + self.failed_queries
        total_uploads = self.successful_uploads + self.failed_uploads
        
        return {
            "queries": {
                "total": total_queries,
                "successful": self.successful_queries,
                "failed": self.failed_queries,
                "success_rate": self.successful_queries / total_queries if total_queries > 0 else 0,
                "latency_p50_ms": self.get_percentile(self.query_latencies, 50),
                "latency_p95_ms": self.get_percentile(self.query_latencies, 95),
                "latency_p99_ms": self.get_percentile(self.query_latencies, 99),
                "latency_avg_ms": mean(self.query_latencies) if self.query_latencies else 0,
            },
            "uploads": {
                "total": total_uploads,
                "successful": self.successful_uploads,
                "failed": self.failed_uploads,
                "success_rate": self.successful_uploads / total_uploads if total_uploads > 0 else 0,
                "latency_p50_ms": self.get_percentile(self.upload_latencies, 50),
                "latency_p95_ms": self.get_percentile(self.upload_latencies, 95),
                "latency_p99_ms": self.get_percentile(self.upload_latencies, 99),
            },
            "confidence": {
                "avg": mean(self.confidence_scores) if self.confidence_scores else 0,
                "min": min(self.confidence_scores) if self.confidence_scores else 0,
                "max": max(self.confidence_scores) if self.confidence_scores else 0,
            },
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": self.cache_hits / (self.cache_hits + self.cache_misses) 
                           if (self.cache_hits + self.cache_misses) > 0 else 0,
            },
            "tokens": {
                "total": sum(self.tokens_used),
                "avg_per_query": mean(self.tokens_used) if self.tokens_used else 0,
            },
        }


# Global metrics instance
custom_metrics = CustomMetrics()


# =============================================================================
# Event Handlers
# =============================================================================

@events.test_start.add_listener
def on_test_start(environment: Environment, **kwargs):
    """Handler called when test starts"""
    logger.info("=" * 60)
    logger.info("Starting RAG System Load Test")
    logger.info("=" * 60)
    logger.info(f"Host: {environment.host}")
    logger.info(f"Upload Host: {config.upload_host}")
    logger.info(f"Max Users: {config.max_users}")
    logger.info(f"Spawn Rate: {config.spawn_rate}/s")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **kwargs):
    """Handler called when test stops"""
    logger.info("=" * 60)
    logger.info("Load Test Complete")
    logger.info("=" * 60)
    
    # Print custom metrics summary
    summary = custom_metrics.get_summary()
    logger.info(f"Custom Metrics Summary:")
    logger.info(json.dumps(summary, indent=2))
    
    # Threshold validation
    passed = True
    issues = []
    
    if summary["queries"]["latency_p95_ms"] > config.query_latency_p95_threshold_ms:
        passed = False
        issues.append(f"Query P95 latency ({summary['queries']['latency_p95_ms']:.0f}ms) "
                     f"exceeds threshold ({config.query_latency_p95_threshold_ms}ms)")
    
    if summary["queries"]["success_rate"] < (1 - config.error_rate_threshold):
        passed = False
        issues.append(f"Query success rate ({summary['queries']['success_rate']:.2%}) "
                     f"below threshold ({(1 - config.error_rate_threshold):.2%})")
    
    if summary["confidence"]["avg"] < config.min_confidence_threshold:
        passed = False
        issues.append(f"Average confidence ({summary['confidence']['avg']:.2f}) "
                     f"below threshold ({config.min_confidence_threshold})")
    
    if passed:
        logger.info("✅ All thresholds PASSED")
    else:
        logger.warning("❌ Threshold violations:")
        for issue in issues:
            logger.warning(f"  - {issue}")
    
    # Save metrics to file
    try:
        os.makedirs("results", exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        with open(f"results/custom-metrics-{timestamp}.json", "w") as f:
            json.dump({
                "timestamp": timestamp,
                "thresholds_passed": passed,
                "issues": issues,
                "metrics": summary,
            }, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save metrics: {e}")


@events.request.add_listener
def on_request(
    request_type: str,
    name: str,
    response_time: float,
    response_length: int,
    response,
    exception,
    **kwargs
):
    """Handler for individual request completion"""
    success = exception is None and response.status_code < 400
    
    if "query" in name.lower():
        confidence = None
        tokens = None
        cached = False
        
        if success and response.content:
            try:
                data = response.json()
                confidence = data.get("confidence", data.get("score"))
                tokens = data.get("tokens_used", data.get("usage", {}).get("total_tokens"))
                cached = data.get("cached", data.get("cache_hit", False))
            except Exception:
                pass
        
        custom_metrics.add_query_result(
            success=success,
            latency_ms=response_time,
            confidence=confidence,
            tokens=tokens,
            cached=cached,
        )
    
    elif "upload" in name.lower():
        custom_metrics.add_upload_result(
            success=success,
            latency_ms=response_time,
        )


# =============================================================================
# User Classes
# =============================================================================

class RAGUser(HttpUser):
    """
    Simulates a user interacting with the RAG system.
    
    Task weights:
    - query: 8 (80% of traffic)
    - upload: 1 (10% of traffic)
    - metrics: 1 (10% of traffic)
    """
    
    # Wait 1-3 seconds between tasks
    wait_time = between(1, 3)
    
    # Limit max users
    abstract = False
    
    def on_start(self):
        """Called when a simulated user starts"""
        self.request_count = 0
        self.session_start = time.time()
        logger.debug(f"User {id(self)} started")

    def on_stop(self):
        """Called when a simulated user stops"""
        duration = time.time() - self.session_start
        logger.debug(f"User {id(self)} stopped after {duration:.1f}s, "
                    f"{self.request_count} requests")

    def _get_headers(self) -> Dict[str, str]:
        """Get common request headers"""
        return {
            "Content-Type": "application/json",
            "X-API-Key": config.api_key,
            "X-Request-ID": f"locust-{id(self)}-{self.request_count}-{int(time.time()*1000)}",
        }

    def _get_form_headers(self) -> Dict[str, str]:
        """Get headers for form data uploads"""
        return {
            "X-API-Key": config.api_key,
            "X-Request-ID": f"locust-{id(self)}-{self.request_count}-{int(time.time()*1000)}",
        }

    @task(8)
    @tag("query", "core")
    def perform_query(self):
        """
        Perform a query against the RAG system.
        Weight: 8 (highest priority)
        """
        self.request_count += 1
        
        # Select random query
        query = random.choice(TEST_QUERIES + ADVANCED_QUERIES)
        top_k = random.randint(3, 10)
        
        payload = {
            "query": query,
            "top_k": top_k,
            "include_sources": True,
        }
        
        with self.client.post(
            "/query",
            json=payload,
            headers=self._get_headers(),
            name="POST /query",
            catch_response=True,
        ) as response:
            try:
                if response.status_code == 200:
                    data = response.json()
                    
                    # Validate response structure
                    if "answer" not in data and "response" not in data:
                        response.failure("Missing answer field in response")
                    elif data.get("error"):
                        response.failure(f"Error in response: {data['error']}")
                    else:
                        response.success()
                        
                elif response.status_code == 429:
                    response.failure("Rate limited")
                elif response.status_code >= 500:
                    response.failure(f"Server error: {response.status_code}")
                else:
                    response.failure(f"Unexpected status: {response.status_code}")
                    
            except json.JSONDecodeError:
                response.failure("Invalid JSON response")
            except Exception as e:
                response.failure(f"Exception: {str(e)}")

    @task(1)
    @tag("upload", "core")
    def perform_upload(self):
        """
        Upload a document to the RAG system.
        Weight: 1 (lower priority)
        """
        self.request_count += 1
        
        # Select random document
        doc = random.choice(SAMPLE_DOCUMENTS)
        unique_content = (
            f"{doc['content']}\n\n"
            f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"User: {id(self)}, Request: {self.request_count}"
        )
        
        files = {
            "file": (doc["name"], unique_content.encode(), "text/plain"),
        }
        
        # Use upload host for upload operations
        upload_url = f"{config.upload_host}/upload"
        
        with self.client.post(
            upload_url,
            files=files,
            headers=self._get_form_headers(),
            name="POST /upload",
            catch_response=True,
        ) as response:
            try:
                if response.status_code in (200, 201):
                    data = response.json()
                    
                    if data.get("document_id") or data.get("id") or data.get("status"):
                        response.success()
                    else:
                        response.failure("Missing document_id in response")
                        
                elif response.status_code == 413:
                    response.failure("File too large")
                elif response.status_code == 429:
                    response.failure("Rate limited")
                elif response.status_code >= 500:
                    response.failure(f"Server error: {response.status_code}")
                else:
                    response.failure(f"Unexpected status: {response.status_code}")
                    
            except json.JSONDecodeError:
                response.failure("Invalid JSON response")
            except Exception as e:
                response.failure(f"Exception: {str(e)}")

    @task(1)
    @tag("metrics", "monitoring")
    def check_metrics(self):
        """
        Check Prometheus metrics endpoint.
        Weight: 1 (background task)
        """
        self.request_count += 1
        
        with self.client.get(
            "/metrics/prometheus",
            headers=self._get_headers(),
            name="GET /metrics",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Metrics check failed: {response.status_code}")

    @task(1)
    @tag("health", "monitoring")
    def check_health(self):
        """
        Check health endpoint.
        Weight: 1 (background task)
        """
        self.request_count += 1
        
        with self.client.get(
            "/health",
            name="GET /health",
            catch_response=True,
        ) as response:
            try:
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") in ("healthy", "ok", "up"):
                        response.success()
                    else:
                        response.failure(f"Unhealthy status: {data.get('status')}")
                else:
                    response.failure(f"Health check failed: {response.status_code}")
            except Exception as e:
                response.failure(f"Health check error: {str(e)}")


class QueryOnlyUser(HttpUser):
    """
    User that only performs query operations.
    Useful for isolated query load testing.
    """
    
    wait_time = between(0.5, 2)
    weight = 1  # Lower weight than RAGUser
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-API-Key": config.api_key,
        }
    
    @task
    @tag("query")
    def query_only(self):
        """Perform only query operations"""
        query = random.choice(TEST_QUERIES)
        
        self.client.post(
            "/query",
            json={"query": query, "top_k": 5},
            headers=self._get_headers(),
            name="POST /query (query-only)",
        )


class HeavyUploadUser(HttpUser):
    """
    User that performs heavy upload operations.
    Useful for testing upload capacity.
    """
    
    wait_time = between(2, 5)
    weight = 1
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": config.api_key,
        }
    
    @task
    @tag("upload")
    def heavy_upload(self):
        """Upload larger documents"""
        # Create larger document
        content = "\n\n".join([
            doc["content"] * 5  # 5x content size
            for doc in SAMPLE_DOCUMENTS
        ])
        
        files = {
            "file": ("large_document.txt", content.encode(), "text/plain"),
        }
        
        upload_url = f"{config.upload_host}/upload"
        
        self.client.post(
            upload_url,
            files=files,
            headers=self._get_headers(),
            name="POST /upload (heavy)",
        )


# =============================================================================
# Step Load Shape (Optional)
# =============================================================================

from locust import LoadTestShape

class StagesShape(LoadTestShape):
    """
    Custom load shape with multiple stages.
    
    Stages:
    1. Ramp up to 50 users (2 min)
    2. Hold at 50 users (3 min)
    3. Ramp up to 200 users (3 min)
    4. Hold at 200 users (5 min)
    5. Spike to 500 users (1 min)
    6. Return to 200 users (2 min)
    7. Ramp down (2 min)
    """
    
    stages = [
        {"duration": 120, "users": 50, "spawn_rate": 1},      # Stage 1: 2 min
        {"duration": 300, "users": 50, "spawn_rate": 1},      # Stage 2: 5 min total
        {"duration": 480, "users": 200, "spawn_rate": 2},     # Stage 3: 8 min total
        {"duration": 780, "users": 200, "spawn_rate": 2},     # Stage 4: 13 min total
        {"duration": 840, "users": 500, "spawn_rate": 10},    # Stage 5: 14 min total (spike)
        {"duration": 960, "users": 200, "spawn_rate": 5},     # Stage 6: 16 min total
        {"duration": 1080, "users": 0, "spawn_rate": 5},      # Stage 7: 18 min total
    ]
    
    def tick(self):
        run_time = self.get_run_time()
        
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        
        return None  # Stop test


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import locust
    
    print("RAG System Load Test")
    print("=" * 40)
    print("Available user classes:")
    print("  - RAGUser: Full system test (query 80%, upload 10%, metrics 10%)")
    print("  - QueryOnlyUser: Query-focused testing")
    print("  - HeavyUploadUser: Upload stress testing")
    print()
    print("Run with: locust -f locustfile.py --host=http://localhost:8002")
    print()
    print("Or headless:")
    print("  locust -f locustfile.py --headless -u 100 -r 10 --run-time 5m --host=http://localhost:8002")
