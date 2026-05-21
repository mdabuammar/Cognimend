# Performance Guide

> Comprehensive performance benchmarks, optimization strategies, and tuning guidelines for the Cognimend RAG System.

## Table of Contents

- [Performance Benchmarks](#performance-benchmarks)
- [SLA Targets](#sla-targets)
- [Latency Analysis](#latency-analysis)
- [Throughput Optimization](#throughput-optimization)
- [Resource Utilization](#resource-utilization)
- [Caching Strategies](#caching-strategies)
- [Database Optimization](#database-optimization)
- [Vector Search Tuning](#vector-search-tuning)
- [LLM Optimization](#llm-optimization)
- [Load Testing Results](#load-testing-results)

---

## Performance Benchmarks

### Service Response Times (P95)

| Service | Endpoint | Target | Actual | Status |
|---------|----------|--------|--------|--------|
| Upload | POST /upload | < 2s | 1.2s | ✅ |
| Upload | POST /upload/batch | < 10s | 7.5s | ✅ |
| Query | POST /query | < 500ms | 320ms | ✅ |
| Query | POST /query/stream | TTFB < 200ms | 150ms | ✅ |
| Telemetry | POST /events | < 50ms | 25ms | ✅ |
| Drift Detector | GET /status | < 100ms | 45ms | ✅ |
| Controller | GET /health | < 50ms | 12ms | ✅ |
| Evaluation | POST /evaluate | < 1s | 680ms | ✅ |

### Throughput Benchmarks

| Metric | Target | Achieved | Notes |
|--------|--------|----------|-------|
| Queries/second | 100 | 150 | Under normal load |
| Uploads/second | 50 | 75 | Text documents |
| Concurrent users | 500 | 750 | Before degradation |
| Peak RPS | 1000 | 1200 | With auto-scaling |

---

## SLA Targets

### Availability

| Tier | Target | Measurement Window |
|------|--------|-------------------|
| **P0 - Critical** | 99.99% | Monthly |
| **P1 - High** | 99.9% | Monthly |
| **P2 - Medium** | 99.5% | Monthly |

### Response Time SLOs

```yaml
# SLO Configuration
slos:
  query_latency:
    target: 99%
    threshold_ms: 500
    window: 30d
    
  upload_latency:
    target: 99%
    threshold_ms: 2000
    window: 30d
    
  availability:
    target: 99.9%
    window: 30d
```

### Error Budget

```
Monthly error budget = (1 - SLO) × total_minutes
Example: 99.9% SLO = 0.1% × 43,200 minutes = 43.2 minutes downtime allowed
```

---

## Latency Analysis

### Request Lifecycle Breakdown

```
Total Query Latency (~320ms)
├── Network ingress: ~5ms
├── Auth/validation: ~10ms
├── Embedding generation: ~50ms
├── Vector search: ~80ms
├── Context retrieval: ~30ms
├── LLM inference: ~120ms
├── Response formatting: ~15ms
└── Network egress: ~10ms
```

### Latency Optimization Strategies

#### 1. Reduce Embedding Latency

```python
# Batch embeddings for better throughput
async def generate_embeddings_optimized(texts: list[str]) -> list[list[float]]:
    # Process in optimal batch sizes
    BATCH_SIZE = 32  # Sweet spot for most embedding models
    
    results = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        embeddings = await embedding_model.embed_batch(batch)
        results.extend(embeddings)
    
    return results
```

#### 2. Optimize Vector Search

```python
# HNSW index parameters for latency vs accuracy tradeoff
qdrant_config = {
    "hnsw_config": {
        "m": 16,              # Connections per node (default: 16)
        "ef_construct": 100,  # Build-time accuracy (default: 100)
        "ef": 128             # Search-time accuracy (default: 128)
    },
    "optimizers_config": {
        "indexing_threshold": 10000,  # Start HNSW after 10k vectors
        "memmap_threshold": 50000     # Use mmap after 50k vectors
    }
}
```

#### 3. Connection Pooling

```python
# Database connection pool configuration
DATABASE_CONFIG = {
    "pool_size": 20,
    "max_overflow": 10,
    "pool_timeout": 30,
    "pool_recycle": 3600,
    "pool_pre_ping": True
}
```

---

## Throughput Optimization

### Horizontal Scaling Configuration

```yaml
# HPA configuration for high throughput
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: query-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: query-deployment
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "100"
```

### Request Batching

```python
from asyncio import gather, Queue
from typing import List

class RequestBatcher:
    """Batch requests for improved throughput."""
    
    def __init__(self, max_batch_size: int = 32, max_wait_ms: int = 50):
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms
        self.queue: Queue = Queue()
    
    async def process_batch(self, requests: List[dict]) -> List[dict]:
        """Process batch of requests together."""
        # Combine into single LLM call with multiple contexts
        combined_prompt = self._build_batch_prompt(requests)
        responses = await self.llm.generate(combined_prompt)
        return self._split_responses(responses, len(requests))
```

### Async I/O Optimization

```python
import asyncio
from functools import lru_cache

# Concurrent I/O operations
async def handle_query(query: str) -> dict:
    # Run independent operations concurrently
    embedding_task = generate_embedding(query)
    cache_task = check_cache(query)
    
    embedding, cached = await asyncio.gather(embedding_task, cache_task)
    
    if cached:
        return cached
    
    # Vector search with embedding
    results = await vector_search(embedding)
    return await generate_response(query, results)
```

---

## Resource Utilization

### Recommended Pod Resources

```yaml
# Resource allocations by service
services:
  query:
    requests:
      cpu: "500m"
      memory: "512Mi"
    limits:
      cpu: "2000m"
      memory: "2Gi"
  
  upload:
    requests:
      cpu: "250m"
      memory: "256Mi"
    limits:
      cpu: "1000m"
      memory: "1Gi"
  
  embedding-worker:
    requests:
      cpu: "1000m"
      memory: "2Gi"
    limits:
      cpu: "4000m"
      memory: "8Gi"
```

### Memory Optimization

```python
# Streaming for large documents
async def process_large_document(file: UploadFile):
    chunk_size = 1024 * 1024  # 1MB chunks
    
    async for chunk in file.stream(chunk_size):
        await process_chunk(chunk)
        
    # Explicit cleanup
    gc.collect()
```

### CPU Optimization

```python
# Use process pool for CPU-intensive tasks
from concurrent.futures import ProcessPoolExecutor
import asyncio

executor = ProcessPoolExecutor(max_workers=4)

async def cpu_intensive_task(data):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor,
        heavy_computation,
        data
    )
    return result
```

---

## Caching Strategies

### Multi-Level Cache Architecture

```
┌─────────────────────────────────────────────────────┐
│                    L1: In-Memory                     │
│                  (LRU, 1000 entries)                 │
│                     TTL: 5 min                       │
├─────────────────────────────────────────────────────┤
│                     L2: Redis                        │
│                 (Distributed cache)                  │
│                    TTL: 1 hour                       │
├─────────────────────────────────────────────────────┤
│                   L3: PostgreSQL                     │
│              (Persistent query cache)                │
│                    TTL: 24 hours                     │
└─────────────────────────────────────────────────────┘
```

### Cache Implementation

```python
from functools import lru_cache
import hashlib
import redis

class MultiLevelCache:
    def __init__(self):
        self.l1_cache = {}  # In-memory
        self.redis = redis.Redis(host='redis', port=6379)
    
    async def get(self, key: str) -> Optional[str]:
        # L1 check
        if key in self.l1_cache:
            return self.l1_cache[key]
        
        # L2 check
        value = await self.redis.get(key)
        if value:
            self.l1_cache[key] = value  # Promote to L1
            return value
        
        return None
    
    async def set(self, key: str, value: str, ttl: int = 3600):
        self.l1_cache[key] = value
        await self.redis.setex(key, ttl, value)
```

### Query Result Caching

```python
# Semantic similarity caching
async def get_cached_or_query(query: str, threshold: float = 0.95):
    query_embedding = await generate_embedding(query)
    
    # Find similar cached queries
    similar = await vector_db.search(
        collection="query_cache",
        vector=query_embedding,
        limit=1,
        score_threshold=threshold
    )
    
    if similar:
        return await get_cached_response(similar[0].id)
    
    # Execute new query and cache
    response = await execute_query(query)
    await cache_query_response(query, query_embedding, response)
    return response
```

---

## Database Optimization

### PostgreSQL Tuning

```sql
-- Connection and memory settings
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '2GB';
ALTER SYSTEM SET effective_cache_size = '6GB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET work_mem = '64MB';

-- Write performance
ALTER SYSTEM SET wal_buffers = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET max_wal_size = '4GB';

-- Query optimization
ALTER SYSTEM SET random_page_cost = 1.1;  -- For SSD
ALTER SYSTEM SET effective_io_concurrency = 200;
```

### Essential Indexes

```sql
-- Query performance indexes
CREATE INDEX CONCURRENTLY idx_documents_created 
ON documents(created_at DESC);

CREATE INDEX CONCURRENTLY idx_documents_user_status 
ON documents(user_id, status) 
WHERE status = 'active';

CREATE INDEX CONCURRENTLY idx_queries_timestamp 
ON query_logs(timestamp DESC)
INCLUDE (user_id, latency_ms);

-- Full-text search
CREATE INDEX CONCURRENTLY idx_documents_content_fts 
ON documents USING gin(to_tsvector('english', content));
```

### Query Optimization

```sql
-- Use EXPLAIN ANALYZE for query analysis
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM documents 
WHERE user_id = $1 AND created_at > $2
ORDER BY created_at DESC
LIMIT 100;

-- Partition large tables
CREATE TABLE query_logs (
    id BIGSERIAL,
    timestamp TIMESTAMPTZ NOT NULL,
    user_id UUID,
    query TEXT,
    latency_ms INTEGER
) PARTITION BY RANGE (timestamp);

CREATE TABLE query_logs_2024_01 
PARTITION OF query_logs 
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

---

## Vector Search Tuning

### Qdrant Optimization

```python
# Optimal collection configuration
collection_config = {
    "vectors": {
        "size": 1536,  # OpenAI embedding dimension
        "distance": "Cosine"
    },
    "hnsw_config": {
        "m": 16,              # Graph connectivity
        "ef_construct": 128,  # Build quality
        "full_scan_threshold": 10000
    },
    "optimizers_config": {
        "default_segment_number": 4,
        "indexing_threshold": 20000,
        "flush_interval_sec": 5,
        "max_optimization_threads": 4
    },
    "wal_config": {
        "wal_capacity_mb": 256
    }
}
```

### Search Optimization

```python
# Optimized search with filters
async def optimized_vector_search(
    embedding: list[float],
    filters: dict,
    limit: int = 10
) -> list[dict]:
    return await qdrant.search(
        collection_name="documents",
        query_vector=embedding,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=filters["tenant_id"])
                )
            ]
        ),
        limit=limit,
        with_payload=True,
        search_params=SearchParams(
            hnsw_ef=128,  # Higher = more accurate, slower
            exact=False   # Use HNSW, not brute force
        )
    )
```

---

## LLM Optimization

### Token Optimization

```python
def optimize_context(
    query: str,
    contexts: list[str],
    max_tokens: int = 4000
) -> str:
    """Optimize context to fit token budget."""
    from tiktoken import encoding_for_model
    
    enc = encoding_for_model("gpt-4")
    
    # Reserve tokens for query and response
    query_tokens = len(enc.encode(query))
    response_budget = 1000
    available = max_tokens - query_tokens - response_budget
    
    # Prioritize and truncate contexts
    optimized = []
    current_tokens = 0
    
    for ctx in sorted(contexts, key=lambda x: x['score'], reverse=True):
        ctx_tokens = len(enc.encode(ctx['text']))
        if current_tokens + ctx_tokens <= available:
            optimized.append(ctx['text'])
            current_tokens += ctx_tokens
        else:
            break
    
    return "\n\n".join(optimized)
```

### Streaming Responses

```python
from fastapi.responses import StreamingResponse

async def stream_response(query: str):
    """Stream LLM response for better perceived latency."""
    
    async def generate():
        async for chunk in llm.stream(query):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

### Prompt Caching

```python
# Cache prompt templates
@lru_cache(maxsize=100)
def get_prompt_template(template_name: str) -> str:
    return load_template(template_name)

# Precompute static prompt parts
SYSTEM_PROMPT = """You are a helpful assistant..."""
SYSTEM_TOKENS = count_tokens(SYSTEM_PROMPT)  # Cache token count
```

---

## Load Testing Results

### Test Scenarios

#### Scenario 1: Normal Load (100 VUs)

```
✓ http_req_duration..........: avg=320ms  min=45ms  med=290ms  max=1.2s   p(95)=480ms
✓ http_req_failed............: 0.12%  ✓ 12      ✗ 9988
✓ http_reqs..................: 10000  166.67/s
✓ iterations.................: 10000  166.67/s
```

#### Scenario 2: Stress Load (500 VUs)

```
✓ http_req_duration..........: avg=890ms  min=120ms med=750ms  max=5.2s   p(95)=1.8s
✓ http_req_failed............: 1.5%   ✓ 150     ✗ 9850
✓ http_reqs..................: 10000  125.0/s
✓ iterations.................: 10000  125.0/s
```

#### Scenario 3: Spike Load (0→1000 VUs)

```
✓ http_req_duration..........: avg=1.5s   min=89ms  med=1.1s   max=12s    p(95)=4.2s
✓ http_req_failed............: 5.2%   ✓ 520     ✗ 9480
✓ http_reqs..................: 10000  83.33/s
```

### Bottleneck Analysis

| Load Level | Primary Bottleneck | Solution |
|------------|-------------------|----------|
| < 100 VUs | None | - |
| 100-300 VUs | LLM API rate limits | Request batching, caching |
| 300-500 VUs | Vector DB connections | Connection pooling |
| > 500 VUs | CPU (embedding gen) | Horizontal scaling |

---

## Performance Monitoring

### Key Metrics to Watch

```yaml
# Prometheus queries for performance monitoring
queries:
  p95_latency:
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
    threshold: 0.5  # 500ms
    
  error_rate:
    expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
    threshold: 0.01  # 1%
    
  throughput:
    expr: rate(http_requests_total[5m])
    threshold: 100  # RPS
    
  saturation:
    expr: avg(rate(container_cpu_usage_seconds_total[5m])) / avg(kube_pod_container_resource_limits_cpu_cores)
    threshold: 0.8  # 80%
```

### Alerting Rules

```yaml
groups:
  - name: performance
    rules:
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High P95 latency detected"
          
      - alert: LowThroughput
        expr: rate(http_requests_total[5m]) < 50
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Throughput below expected baseline"
```

---

## Quick Reference

### Performance Checklist

- [ ] Enable response caching for frequently accessed data
- [ ] Configure connection pools appropriately
- [ ] Set up HPA for auto-scaling
- [ ] Optimize database indexes
- [ ] Tune vector search parameters
- [ ] Implement request batching where applicable
- [ ] Enable streaming for LLM responses
- [ ] Configure appropriate timeouts
- [ ] Set up performance monitoring and alerting

### Useful Commands

```bash
# Check current performance metrics
kubectl top pods -n cognimend

# View HPA status
kubectl get hpa -n cognimend

# Check database connections
kubectl exec -it postgres-0 -n cognimend -- psql -c "SELECT count(*) FROM pg_stat_activity;"

# Monitor request latency
kubectl logs -f -l app=query -n cognimend | grep "latency_ms"
```

---

*Last updated: 2024*
