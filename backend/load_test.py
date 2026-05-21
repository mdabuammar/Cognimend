"""Load testing script using Locust"""
from locust import HttpUser, task, between
import random
import json

class RAGSystemUser(HttpUser):
    """Simulates realistic RAG system usage"""
    wait_time = between(1, 3)
    
    # Sample questions for testing
    QUESTIONS = [
        "What is machine learning?",
        "How does neural networks work?",
        "Explain deep learning",
        "What is transformer architecture?",
        "How to implement RAG?",
        "Difference between LLM and NLP?",
        "What is vector database?",
        "Explain semantic search",
        "How does embeddings work?",
        "What is prompt engineering?",
    ]
    
    def on_start(self):
        """Called when a user starts"""
        self.client.headers.update({"Content-Type": "application/json"})
    
    @task(70)
    def query_documents(self):
        """Query endpoint (70% of traffic) - most common"""
        question = random.choice(self.QUESTIONS)
        self.client.post(
            "/query",
            json={"question": question},
            name="/query"
        )
    
    @task(20)
    def list_documents(self):
        """List documents (20% of traffic)"""
        self.client.get("/documents?limit=50", name="/documents")
    
    @task(10)
    def get_metrics(self):
        """Get metrics (10% of traffic)"""
        self.client.get("/metrics", name="/metrics")
    
    @task(5)
    def health_check(self):
        """Health check (5% of traffic)"""
        self.client.get("/health", name="/health")


class RAGUploadUser(HttpUser):
    """Simulates document upload"""
    wait_time = between(10, 30)
    
    @task
    def upload_document(self):
        """Upload a test document"""
        sample_text = """
        Machine learning is a subset of artificial intelligence that focuses on
        learning from data without being explicitly programmed. It uses algorithms
        and statistical models to analyze patterns in data and make predictions.
        """ * 100  # Repeat to make it larger
        
        files = {'file': ('test.txt', sample_text.encode())}
        self.client.post(
            "/upload",
            files=files,
            data={'title': 'Test Document'},
            name="/upload"
        )


if __name__ == "__main__":
    # Run: locust -f load_test.py --host http://localhost:8002 --users 100 --spawn-rate 10
    print("""
    Load Testing RAG System
    
    Run with:
        locust -f load_test.py --host http://localhost:8002 --users 100 --spawn-rate 10
    
    Expected Results (After production improvements):
    - 100 users: <2s latency, 0 errors
    - 500 users: <500ms latency, 0 errors  
    - 1000 users: <500ms latency, 0 errors
    
    Monitoring:
    - Jaeger: http://localhost:16686
    - Prometheus: http://localhost:9090
    - Grafana: http://localhost:3000
    """)
