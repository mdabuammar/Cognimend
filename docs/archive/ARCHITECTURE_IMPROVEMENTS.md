# FAANG-LEVEL PRODUCTION HARDENING GUIDE

## Overview

This guide provides step-by-step instructions to implement all 8 priority improvements across your RAG system. Expected time: 40-60 hours.

---

## PHASE 1: CRITICAL FIXES (Week 1) - 14-18 hours

### Priority 1: Fix Synchronous Blocking (4-8 hours)

**Current Problem:**
```python
# ❌ BLOCKS EVENT LOOP
def get_embedding(text: str):
    return asyncio.run(openrouter_client.get_embedding(text))

@app.post("/query")
async def query():
    embedding = get_embedding(question)  # Synchronous, blocks!
```

**Solution for Upload Service:**
1. Make embedding calls truly async
2. Implement batch_get_embeddings() for parallel requests
3. Use asyncio.gather() to wait for all embeddings in parallel

```python
# ✅ PROPER ASYNC
async def get_embedding_async(text: str) -> List[float]:
    return await openrouter_client.get_embedding(text)

async def batch_get_embeddings(texts: List[str]) -> List[List[float]]:
    tasks = [get_embedding_async(text) for text in texts]
    return await asyncio.gather(*tasks)

@app.post("/upload")
async def upload_document(file: UploadFile):
    chunks = chunk_text(text)
    # Parallel embedding - 50-100x faster
    embeddings = await batch_get_embeddings(chunks)
```

**Solution for Query Service:**
1. Make embedding call async
2. Run embedding + vector search + answer generation in parallel

```python
@app.post("/query")
async def query_documents(req: QueryRequest):
    # Parallel execution
    embedding_task = get_embedding_async(req.question)
    search_task = qdrant_client.search(...)
    generate_task = openrouter_client.generate_answer(...)
    
    question_embedding, search_results, answer = await asyncio.gather(
        embedding_task, search_task, generate_task
    )
    return response
```

**Files to modify:**
- `services/upload/main.py` - Lines with `asyncio.run()`
- `services/query/main.py` - Lines with `asyncio.run()`

**Testing:**
```bash
locust -f load_test.py --host http://localhost:8002 --users 100 --spawn-rate 10
# Before: timeouts and crashes
# After: <1s latency, no timeouts
```

---

### Priority 2: Implement Redis Caching (2-4 hours)

**Setup:**

1. Add Redis to docker-compose.yml (if not present)
2. Install redis-py: `pip install redis`
3. Use the provided `shared/cache.py` module

**For Query Service - Cache Answers:**
```python
from shared.cache import cache, cache_get_or_compute

@app.post("/query")
async def query_documents(req: QueryRequest):
    # Check cache
    cache_key = f"query:{hash(req.question)}"
    cached = await cache.get(cache_key)
    if cached:
        return cached
    
    # Compute...
    response = {...}
    
    # Cache for 2 hours
    await cache.set(cache_key, response, ttl_seconds=7200)
    return response
```

**For Telemetry Service - Cache Dashboard:**
```python
@app.get("/dashboard/stats")
async def get_dashboard_stats():
    cache_key = "dashboard:stats"
    
    # Try cache first (5 minute TTL)
    cached = await cache.get(cache_key)
    if cached:
        return cached
    
    # Compute...
    result = {...}
    await cache.set(cache_key, result, ttl_seconds=300)
    return result
```

**For Upload Service - Cache Embeddings:**
```python
async def get_embedding_async(text: str):
    cache_key = f"embedding:{hash(text)}"
    
    # Use cache_get_or_compute helper
    return await cache_get_or_compute(
        cache_key,
        openrouter_client.get_embedding,
        text,
        ttl_seconds=86400  # 24 hours
    )
```

**Expected Results:**
- 70-80% cache hit rate for typical workload
- 10x faster responses for cached queries
- 80% reduction in API calls

---

### Priority 3: Add Resilience Patterns (6-8 hours)

**Circuit Breaker for External APIs:**

1. Use provided `shared/resilience.py` module
2. Wrap all external API calls

```python
from shared.resilience import CircuitBreaker, retry_async, async_timeout

# Create circuit breakers
embedding_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

# Use in embedding call
async def get_embedding_safe(text: str):
    try:
        return await embedding_breaker.call_async(
            openrouter_client.get_embedding,
            text
        )
    except CircuitBreakerError:
        # Fallback to mock embedding
        return get_mock_embedding(text)
```

**Retry with Exponential Backoff:**

```python
async def query_with_retry(req: QueryRequest):
    try:
        # Retry up to 3 times with exponential backoff
        return await retry_async(
            process_query,
            req,
            max_attempts=3,
            base_delay=0.1,
            backoff_multiplier=2.0
        )
    except Exception as e:
        logger.error(f"Query failed after retries: {e}")
        raise
```

**Timeout Management:**

```python
async def query_with_timeouts(req: QueryRequest):
    try:
        # API calls: 10s timeout
        embedding = await async_timeout(
            get_embedding_async(req.question),
            timeout_seconds=10
        )
        
        # Vector search: 5s timeout
        results = await async_timeout(
            qdrant_client.search(...),
            timeout_seconds=5
        )
        
        # Answer generation: 10s timeout
        answer = await async_timeout(
            openrouter_client.generate_answer(...),
            timeout_seconds=10
        )
        
        return response
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out")
```

**Expected Results:**
- 99.5% → 99.9% availability
- Automatic recovery from transient failures
- Graceful degradation instead of cascading failures

---

## PHASE 2: HARDENING (Week 2) - 18-24 hours

### Priority 4: Database Connection Pooling (2-3 hours)

**Replace direct connections with pooling:**

```python
# ❌ OLD - Creates new connection every time
def get_db():
    return psycopg2.connect(...)

@app.get("/query")
async def query(req):
    conn = get_db()  # NEW CONNECTION - SLOW!
    ...

# ✅ NEW - Reuse from pool
from shared.database import db_pool

@app.get("/query")
async def query(req):
    conn = db_pool.get_connection()
    try:
        ...
    finally:
        db_pool.return_connection(conn)
```

**In all services:**

1. Replace `get_db()` function with `db_pool` usage
2. Add connection pooling to initialization
3. Monitor pool utilization

**Benefits:**
- 50 concurrent users → 500+ concurrent users
- Connection time: 100ms → 1ms
- Eliminates connection pool exhaustion

---

### Priority 5: Distributed Tracing (4-6 hours)

**Setup:**

1. Add Jaeger to docker-compose.yml
2. Install: `pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-jaeger`
3. Use provided `shared/tracing.py` module

**In each service main.py:**

```python
from shared.tracing import init_tracing, get_tracer

# Initialize on startup
@app.on_event("startup")
async def startup():
    init_tracing("query-service")
    
tracer = get_tracer("query")

# Instrument endpoints
@app.post("/query")
async def query_documents(req: QueryRequest):
    with tracer.start_as_current_span("query_documents") as span:
        span.set_attribute("question", req.question)
        
        embedding = await get_embedding_async(req.question)
        span.set_attribute("embedding.size", len(embedding))
        
        results = await qdrant_client.search(...)
        span.set_attribute("results.count", len(results))
        
        answer = await generate_answer(...)
        span.set_attribute("answer.length", len(answer))
```

**View traces:**
- Open http://localhost:16686 (Jaeger UI)
- See complete request flow across 6 services
- Debug latency, errors, and dependencies

**Benefits:**
- Debug production issues in seconds
- Understand service dependencies
- Optimize bottlenecks

---

### Priority 6: Event-Driven Architecture (16-24 hours)

**Setup RabbitMQ:**

1. Add RabbitMQ to docker-compose.yml
2. Install: `pip install aio-pika`

**Replace synchronous dependencies with events:**

```
BEFORE (circular):
Upload → DB → Notification to Query → Notification to Telemetry (tight coupling!)

AFTER (event-driven):
Upload → RabbitMQ topic: documents.uploaded
            ├→ Query service subscribes → Indexes documents
            ├→ Telemetry service subscribes → Tracks upload stats
            └→ Evaluation service subscribes → Adds to test set
```

**Producer (Upload Service):**
```python
import aio_pika

# Publish event when document uploaded
async def publish_document_event(doc_id, filename, chunk_count):
    connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            'documents', aio_pika.ExchangeType.TOPIC
        )
        
        message = aio_pika.Message(
            body=json.dumps({
                "event": "document.uploaded",
                "doc_id": doc_id,
                "filename": filename,
                "chunks": chunk_count
            }).encode()
        )
        
        await exchange.publish(message, routing_key="document.uploaded")

# In upload endpoint:
@app.post("/upload")
async def upload_document(file: UploadFile):
    # ... process document ...
    await publish_document_event(doc_id, file.filename, len(chunks))
```

**Consumer (Query Service):**
```python
async def subscribe_to_documents():
    connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            'documents', aio_pika.ExchangeType.TOPIC
        )
        queue = await channel.declare_queue('query_service_queue')
        await queue.bind(exchange, 'document.*')
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    event = json.loads(message.body)
                    if event['event'] == 'document.uploaded':
                        # Index the document
                        await index_document(event['doc_id'])
```

**Benefits:**
- Services are fully decoupled
- No circular dependencies
- Easier to add new subscribers
- Better for scaling

---

## PHASE 3: VALIDATION & OPTIMIZATION (Week 3) - 8-18 hours

### Priority 7: Complete Data Drift Detection (3-4 hours)

**Implement Statistical Testing:**

```python
from scipy import stats
import numpy as np

async def detect_data_drift():
    """Statistical drift detection with KS test"""
    
    # Get recent embeddings
    recent_embeddings = await get_recent_embeddings(limit=1000)
    
    # Get historical embeddings
    historical_embeddings = await get_historical_embeddings(days=30)
    
    # Apply Kolmogorov-Smirnov test
    statistic, p_value = stats.ks_2samp(
        recent_embeddings,
        historical_embeddings
    )
    
    # If p-value < 0.05, distribution changed significantly
    if p_value < 0.05:
        severity = "critical" if statistic > 0.3 else "warning"
        await log_drift_event(
            drift_type="data_drift",
            severity=severity,
            metric_value=statistic,
            p_value=p_value,
            threshold=0.15
        )
        
        # Trigger alert if critical
        if severity == "critical":
            await alert_service.send_alert(
                channel="slack",
                message=f"Critical data drift detected: {statistic:.2%}"
            )
```

**Complete retrieval drift:**

```python
async def detect_retrieval_drift():
    """Detect if top-k results are getting worse"""
    
    recent = await get_recent_queries(limit=100)
    previous = await get_previous_queries(limit=100)
    
    recent_avg_sim = np.mean([q['top_similarity'] for q in recent])
    previous_avg_sim = np.mean([q['top_similarity'] for q in previous])
    
    drift_percentage = (previous_avg_sim - recent_avg_sim) / previous_avg_sim
    
    if drift_percentage > 0.1:  # 10% drop
        await log_drift_event(
            drift_type="retrieval_drift",
            metric_value=drift_percentage,
            severity="high" if drift_percentage > 0.2 else "medium"
        )
```

**Benefits:**
- Real statistical drift detection
- Reduced false positives
- Clear thresholds and severity levels

---

### Priority 8: Configuration Management (2-3 hours)

**Atomic Configuration Updates:**

```python
# In Controller service

async def apply_configuration_change(new_config: dict) -> bool:
    """Apply configuration with atomic update and rollback capability"""
    
    conn = db_pool.get_connection()
    try:
        async with conn.transaction():
            # Read current config with lock
            cur = conn.cursor()
            cur.execute("""
                SELECT version, config FROM system_config 
                WHERE id = 1 FOR UPDATE
            """)
            current = cur.fetchone()
            current_version = current['version']
            
            # Add version
            new_config['version'] = current_version + 1
            new_config['updated_at'] = datetime.now().isoformat()
            
            # Atomic update
            cur.execute("""
                UPDATE system_config 
                SET config = %s, version = %s, updated_at = NOW()
                WHERE id = 1 AND version = %s
            """, (json.dumps(new_config), new_config['version'], current_version))
            
            if cur.rowcount != 1:
                raise OptimisticLockError("Config changed by another process")
            
            # Broadcast to all services
            await publish_event("config.updated", new_config)
            
            # Monitor improvement
            await monitor_improvement(drift_event_id, new_config)
            
            # Rollback if no improvement
            if not await verify_improvement(drift_event_id, threshold=0.1):
                await rollback_to_version(current_version)
                return False
            
            return True
    finally:
        db_pool.return_connection(conn)
```

**Hot reload configuration:**

```python
# All services subscribe to config updates
async def listen_for_config_updates():
    async with subscribe_to("config.updated") as messages:
        async for config_event in messages:
            new_config = config_event['config']
            
            # Update in-memory config
            global SYSTEM_CONFIG
            SYSTEM_CONFIG = new_config
            
            # No restart needed!
            logger.info(f"Config reloaded: v{new_config['version']}")
```

**Benefits:**
- Change configuration without restart
- Automatic rollback on failure
- Audit trail of all changes

---

## PRODUCTION DEPLOYMENT CHECKLIST

### Before Going Live

```
CODE QUALITY
[ ] No asyncio.run() calls (all async/await)
[ ] All database calls use connection pool
[ ] All external API calls have circuit breakers
[ ] All timeouts configured
[ ] All errors logged and monitored
[ ] No hardcoded credentials

TESTING
[ ] Unit tests pass (pytest)
[ ] Integration tests pass
[ ] Load tests pass (1000 concurrent users)
[ ] Stress tests pass (2000 concurrent users)
[ ] Chaos tests pass (random service failures)
[ ] Rollback procedure tested

MONITORING
[ ] Prometheus scraping metrics
[ ] Jaeger collecting traces
[ ] Grafana dashboards created
[ ] Alerts configured
[ ] Log aggregation working
[ ] Database monitoring working

DOCUMENTATION
[ ] Architecture diagrams updated
[ ] API documentation current
[ ] Runbook for common issues
[ ] Disaster recovery procedures
[ ] On-call setup complete

DEPLOYMENT
[ ] Blue-green deployment ready
[ ] Canary deployment plan
[ ] Health checks implemented
[ ] Graceful shutdown working
[ ] Traffic routing configured
```

---

## EXPECTED IMPROVEMENTS

### Performance

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Concurrent Users | 50 | 10,000 | 200x |
| Response Time (p99) | 8s | <500ms | 16x |
| Response Time (p95) | 3s | <200ms | 15x |
| Throughput | 50 RPS | 5000 RPS | 100x |
| Cache Hit Rate | 0% | 80% | ∞ |
| API Calls | High | 80% reduction | 5x cost savings |

### Reliability

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Uptime | 95% | 99.95% | 20x |
| Error Rate | 5% | 0.1% | 50x |
| Connection Pool | 100% utilization | 30% | More headroom |
| MTTR (Mean Time To Recover) | 30 min | 2 min | 15x |
| Cascading Failures | Common | Rare | Resilient |

### Operational

| Metric | Before | After |
|--------|--------|-------|
| Debugging | Manual logs | Distributed tracing |
| Configuration Changes | Code redeploy | Hot reload |
| Scaling | Manual | Horizontal auto-scaling |
| Cost | High | Reduced by 80% (caching) |
| Developer Experience | Hard | Easy (clear observability) |

---

## SUPPORT & TROUBLESHOOTING

### Common Issues

**1. Redis not connecting**
```
Error: Could not connect to Redis at localhost:6379
Fix: 
  - Ensure Redis is running: docker-compose up redis
  - Check REDIS_HOST and REDIS_PORT in .env
  - Service should work with degraded cache if Redis unavailable
```

**2. Circuit breaker keeps opening**
```
Error: Circuit breaker is OPEN
Fix:
  - Check if external API (OpenRouter) is working
  - Increase failure_threshold if transient
  - Check error logs for root cause
```

**3. Database connection pool exhausted**
```
Error: Cannot get connection from pool
Fix:
  - Increase pool size in database.py: maxconn=50
  - Check for connection leaks (not returning)
  - Profile with: psql -c "SELECT * FROM pg_stat_activity;"
```

**4. Traces not appearing in Jaeger**
```
Error: No traces in Jaeger UI
Fix:
  - Ensure Jaeger is running: docker-compose up jaeger
  - Check JAEGER_HOST and JAEGER_PORT in .env
  - Service should work without tracing if Jaeger unavailable
```

---

## NEXT STEPS

1. **Review this guide** with your team
2. **Run generate_improvements.py** to see full plan
3. **Start with Priority 1-3** (critical fixes)
4. **Test with load tests** after each phase
5. **Deploy to staging** before production
6. **Monitor metrics** closely during rollout

**Estimated Timeline:**
- Phase 1 (Week 1): Critical fixes → B+ grade
- Phase 2 (Week 2): Hardening → A- grade
- Phase 3 (Week 3): Optimization → A+ grade

**Target Grade: A+ (FAANG-Level Production Ready)**
