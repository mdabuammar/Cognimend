"""
Production metrics collection for DriftGuard
Prometheus-compatible metrics with custom business metrics
"""
import os
import time
from typing import Dict, Any, Optional, Callable
from functools import wraps
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# Try to import prometheus_client, provide fallback if not available
try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Info, Summary,
        generate_latest, CONTENT_TYPE_LATEST, REGISTRY,
        CollectorRegistry, multiprocess, make_wsgi_app,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed, metrics will be no-op")


# ============================================================
# Metric Definitions
# ============================================================

if PROMETHEUS_AVAILABLE:
    # Request Metrics
    REQUEST_COUNT = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )
    
    REQUEST_LATENCY = Histogram(
        'http_request_duration_seconds',
        'HTTP request latency',
        ['method', 'endpoint'],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
    )
    
    REQUEST_IN_PROGRESS = Gauge(
        'http_requests_in_progress',
        'HTTP requests currently being processed',
        ['method', 'endpoint']
    )
    
    # Search Metrics
    SEARCH_COUNT = Counter(
        'search_requests_total',
        'Total search requests',
        ['status', 'cache_status']
    )
    
    SEARCH_LATENCY = Histogram(
        'search_duration_seconds',
        'Search request latency',
        ['cache_status'],
        buckets=[0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30]
    )
    
    SEARCH_CONFIDENCE = Histogram(
        'search_confidence_score',
        'Search result confidence scores',
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    )
    
    SEARCH_RESULTS_COUNT = Histogram(
        'search_results_count',
        'Number of search results returned',
        buckets=[0, 1, 5, 10, 20, 50, 100]
    )
    
    # Vector DB Metrics
    QDRANT_QUERY_COUNT = Counter(
        'qdrant_queries_total',
        'Total Qdrant queries',
        ['operation', 'status']
    )
    
    QDRANT_QUERY_LATENCY = Histogram(
        'qdrant_query_duration_seconds',
        'Qdrant query latency',
        ['operation'],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5]
    )
    
    QDRANT_VECTORS = Gauge(
        'qdrant_vectors_total',
        'Total vectors in Qdrant',
        ['collection']
    )
    
    # LLM/OpenRouter Metrics
    LLM_REQUEST_COUNT = Counter(
        'llm_requests_total',
        'Total LLM API requests',
        ['model', 'status']
    )
    
    LLM_REQUEST_LATENCY = Histogram(
        'llm_request_duration_seconds',
        'LLM API request latency',
        ['model'],
        buckets=[0.5, 1, 2, 5, 10, 30, 60, 120]
    )
    
    LLM_TOKENS_USED = Counter(
        'llm_tokens_total',
        'Total LLM tokens used',
        ['model', 'type']
    )
    
    OPENROUTER_QUOTA_REMAINING = Gauge(
        'openrouter_quota_remaining',
        'OpenRouter quota remaining for today'
    )
    
    OPENROUTER_QUOTA_USED = Gauge(
        'openrouter_quota_used',
        'OpenRouter quota used today'
    )
    
    # Cache Metrics
    CACHE_OPERATIONS = Counter(
        'cache_operations_total',
        'Total cache operations',
        ['operation', 'status']
    )
    
    CACHE_LATENCY = Histogram(
        'cache_operation_duration_seconds',
        'Cache operation latency',
        ['operation'],
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
    )
    
    CACHE_SIZE = Gauge(
        'cache_entries_total',
        'Number of entries in cache',
        ['cache_type']
    )
    
    CACHE_HIT_RATE = Gauge(
        'cache_hit_rate',
        'Cache hit rate percentage'
    )
    
    # Database Metrics
    DB_QUERY_COUNT = Counter(
        'db_queries_total',
        'Total database queries',
        ['operation', 'status']
    )
    
    DB_QUERY_LATENCY = Histogram(
        'db_query_duration_seconds',
        'Database query latency',
        ['operation'],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5]
    )
    
    DB_CONNECTIONS_ACTIVE = Gauge(
        'db_connections_active',
        'Active database connections'
    )
    
    DB_CONNECTIONS_IDLE = Gauge(
        'db_connections_idle',
        'Idle database connections'
    )
    
    DB_POOL_SIZE = Gauge(
        'db_pool_size',
        'Total database connection pool size'
    )
    
    # Rate Limiting Metrics
    RATE_LIMIT_HITS = Counter(
        'rate_limit_hits_total',
        'Total rate limit hits',
        ['action', 'tier']
    )
    
    RATE_LIMIT_REMAINING = Gauge(
        'rate_limit_remaining',
        'Remaining requests in rate limit window',
        ['action', 'identifier']
    )
    
    # Circuit Breaker Metrics
    CIRCUIT_BREAKER_STATE = Gauge(
        'circuit_breaker_state',
        'Circuit breaker state (0=closed, 1=half-open, 2=open)',
        ['service']
    )
    
    CIRCUIT_BREAKER_FAILURES = Counter(
        'circuit_breaker_failures_total',
        'Total circuit breaker failures',
        ['service']
    )
    
    # Document Metrics
    DOCUMENTS_UPLOADED = Counter(
        'documents_uploaded_total',
        'Total documents uploaded',
        ['file_type', 'status']
    )
    
    DOCUMENTS_TOTAL = Gauge(
        'documents_total',
        'Total documents in system',
        ['status']
    )
    
    DOCUMENT_SIZE = Histogram(
        'document_size_bytes',
        'Document size in bytes',
        buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600]
    )
    
    CHUNKS_TOTAL = Gauge(
        'chunks_total',
        'Total document chunks'
    )
    
    # User Metrics
    USERS_ACTIVE = Gauge(
        'users_active',
        'Active users in last hour'
    )
    
    USER_ACTIONS = Counter(
        'user_actions_total',
        'User actions',
        ['action']
    )
    
    # System Metrics
    APP_INFO = Info(
        'driftguard_app',
        'Application information'
    )
    
    STARTUP_TIME = Gauge(
        'app_startup_timestamp_seconds',
        'Application startup timestamp'
    )


# ============================================================
# Metric Helpers
# ============================================================

class MetricsRecorder:
    """Helper class for recording metrics"""
    
    def __init__(self):
        self._start_time = time.time()
        if PROMETHEUS_AVAILABLE:
            STARTUP_TIME.set(self._start_time)
            APP_INFO.info({
                'version': os.environ.get('APP_VERSION', 'unknown'),
                'environment': os.environ.get('ENVIRONMENT', 'development'),
            })
    
    @contextmanager
    def track_request(self, method: str, endpoint: str):
        """Context manager to track HTTP request metrics"""
        if not PROMETHEUS_AVAILABLE:
            yield
            return
        
        REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
        start_time = time.perf_counter()
        status = "500"
        
        try:
            yield
            status = "200"
        except Exception as e:
            status = getattr(e, 'status_code', 500)
            raise
        finally:
            duration = time.perf_counter() - start_time
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
            REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()
    
    @contextmanager
    def track_search(self, cache_status: str = "miss"):
        """Context manager to track search metrics"""
        if not PROMETHEUS_AVAILABLE:
            yield {}
            return
        
        start_time = time.perf_counter()
        result_data = {"cache_status": cache_status}
        
        try:
            yield result_data
            SEARCH_COUNT.labels(status="success", cache_status=result_data.get("cache_status", cache_status)).inc()
        except Exception:
            SEARCH_COUNT.labels(status="error", cache_status=cache_status).inc()
            raise
        finally:
            duration = time.perf_counter() - start_time
            SEARCH_LATENCY.labels(cache_status=result_data.get("cache_status", cache_status)).observe(duration)
    
    @contextmanager
    def track_qdrant(self, operation: str):
        """Context manager to track Qdrant metrics"""
        if not PROMETHEUS_AVAILABLE:
            yield
            return
        
        start_time = time.perf_counter()
        
        try:
            yield
            QDRANT_QUERY_COUNT.labels(operation=operation, status="success").inc()
        except Exception:
            QDRANT_QUERY_COUNT.labels(operation=operation, status="error").inc()
            raise
        finally:
            duration = time.perf_counter() - start_time
            QDRANT_QUERY_LATENCY.labels(operation=operation).observe(duration)
    
    @contextmanager
    def track_llm(self, model: str):
        """Context manager to track LLM metrics"""
        if not PROMETHEUS_AVAILABLE:
            yield {}
            return
        
        start_time = time.perf_counter()
        usage_data = {}
        
        try:
            yield usage_data
            LLM_REQUEST_COUNT.labels(model=model, status="success").inc()
            
            if "prompt_tokens" in usage_data:
                LLM_TOKENS_USED.labels(model=model, type="prompt").inc(usage_data["prompt_tokens"])
            if "completion_tokens" in usage_data:
                LLM_TOKENS_USED.labels(model=model, type="completion").inc(usage_data["completion_tokens"])
        except Exception:
            LLM_REQUEST_COUNT.labels(model=model, status="error").inc()
            raise
        finally:
            duration = time.perf_counter() - start_time
            LLM_REQUEST_LATENCY.labels(model=model).observe(duration)
    
    @contextmanager
    def track_cache(self, operation: str):
        """Context manager to track cache metrics"""
        if not PROMETHEUS_AVAILABLE:
            yield
            return
        
        start_time = time.perf_counter()
        
        try:
            yield
            CACHE_OPERATIONS.labels(operation=operation, status="success").inc()
        except Exception:
            CACHE_OPERATIONS.labels(operation=operation, status="error").inc()
            raise
        finally:
            duration = time.perf_counter() - start_time
            CACHE_LATENCY.labels(operation=operation).observe(duration)
    
    @contextmanager
    def track_db(self, operation: str):
        """Context manager to track database metrics"""
        if not PROMETHEUS_AVAILABLE:
            yield
            return
        
        start_time = time.perf_counter()
        
        try:
            yield
            DB_QUERY_COUNT.labels(operation=operation, status="success").inc()
        except Exception:
            DB_QUERY_COUNT.labels(operation=operation, status="error").inc()
            raise
        finally:
            duration = time.perf_counter() - start_time
            DB_QUERY_LATENCY.labels(operation=operation).observe(duration)
    
    def record_search_confidence(self, confidence: float):
        """Record search confidence score"""
        if PROMETHEUS_AVAILABLE:
            SEARCH_CONFIDENCE.observe(confidence)
    
    def record_search_results(self, count: int):
        """Record number of search results"""
        if PROMETHEUS_AVAILABLE:
            SEARCH_RESULTS_COUNT.observe(count)
    
    def record_document_upload(self, file_type: str, status: str = "success"):
        """Record document upload"""
        if PROMETHEUS_AVAILABLE:
            DOCUMENTS_UPLOADED.labels(file_type=file_type, status=status).inc()
    
    def record_document_size(self, size_bytes: int):
        """Record document size"""
        if PROMETHEUS_AVAILABLE:
            DOCUMENT_SIZE.observe(size_bytes)
    
    def set_documents_count(self, status: str, count: int):
        """Set total documents count"""
        if PROMETHEUS_AVAILABLE:
            DOCUMENTS_TOTAL.labels(status=status).set(count)
    
    def set_vectors_count(self, collection: str, count: int):
        """Set total vectors count"""
        if PROMETHEUS_AVAILABLE:
            QDRANT_VECTORS.labels(collection=collection).set(count)
    
    def set_cache_hit_rate(self, rate: float):
        """Set cache hit rate"""
        if PROMETHEUS_AVAILABLE:
            CACHE_HIT_RATE.set(rate)
    
    def set_cache_size(self, cache_type: str, size: int):
        """Set cache size"""
        if PROMETHEUS_AVAILABLE:
            CACHE_SIZE.labels(cache_type=cache_type).set(size)
    
    def set_db_pool_stats(self, active: int, idle: int, total: int):
        """Set database pool statistics"""
        if PROMETHEUS_AVAILABLE:
            DB_CONNECTIONS_ACTIVE.set(active)
            DB_CONNECTIONS_IDLE.set(idle)
            DB_POOL_SIZE.set(total)
    
    def set_quota_remaining(self, remaining: int):
        """Set OpenRouter quota remaining"""
        if PROMETHEUS_AVAILABLE:
            OPENROUTER_QUOTA_REMAINING.set(remaining)
    
    def set_quota_used(self, used: int):
        """Set OpenRouter quota used"""
        if PROMETHEUS_AVAILABLE:
            OPENROUTER_QUOTA_USED.set(used)
    
    def record_rate_limit_hit(self, action: str, tier: str):
        """Record rate limit hit"""
        if PROMETHEUS_AVAILABLE:
            RATE_LIMIT_HITS.labels(action=action, tier=tier).inc()
    
    def set_circuit_breaker_state(self, service: str, state: str):
        """Set circuit breaker state"""
        if PROMETHEUS_AVAILABLE:
            state_value = {"closed": 0, "half-open": 1, "open": 2}.get(state, 0)
            CIRCUIT_BREAKER_STATE.labels(service=service).set(state_value)
    
    def record_circuit_breaker_failure(self, service: str):
        """Record circuit breaker failure"""
        if PROMETHEUS_AVAILABLE:
            CIRCUIT_BREAKER_FAILURES.labels(service=service).inc()
    
    def set_active_users(self, count: int):
        """Set active users count"""
        if PROMETHEUS_AVAILABLE:
            USERS_ACTIVE.set(count)
    
    def record_user_action(self, action: str):
        """Record user action"""
        if PROMETHEUS_AVAILABLE:
            USER_ACTIONS.labels(action=action).inc()


# Global metrics recorder
metrics = MetricsRecorder()


# ============================================================
# Decorators
# ============================================================

def track_request(endpoint: str):
    """Decorator to track request metrics"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            method = kwargs.get('method', 'GET')
            with metrics.track_request(method, endpoint):
                return await func(*args, **kwargs)
        return wrapper
    return decorator


def track_search():
    """Decorator to track search metrics"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with metrics.track_search() as data:
                result = await func(*args, **kwargs)
                if hasattr(result, 'from_cache'):
                    data["cache_status"] = "hit" if result.from_cache else "miss"
                if hasattr(result, 'confidence'):
                    metrics.record_search_confidence(result.confidence)
                return result
        return wrapper
    return decorator


def track_llm_call(model: str):
    """Decorator to track LLM API calls"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with metrics.track_llm(model) as usage:
                result = await func(*args, **kwargs)
                if hasattr(result, 'usage'):
                    usage["prompt_tokens"] = getattr(result.usage, 'prompt_tokens', 0)
                    usage["completion_tokens"] = getattr(result.usage, 'completion_tokens', 0)
                return result
        return wrapper
    return decorator


# ============================================================
# FastAPI Integration
# ============================================================

def get_metrics_response():
    """Generate Prometheus metrics response"""
    if not PROMETHEUS_AVAILABLE:
        return "prometheus_client not installed", 500, {"Content-Type": "text/plain"}
    
    metrics_output = generate_latest(REGISTRY)
    return metrics_output.decode('utf-8'), 200, {"Content-Type": CONTENT_TYPE_LATEST}


def setup_metrics_endpoint(app):
    """Setup /metrics endpoint for FastAPI app"""
    from fastapi import Response
    
    @app.get("/metrics")
    async def metrics_endpoint():
        content, status, headers = get_metrics_response()
        return Response(content=content, status_code=status, headers=headers)


# ============================================================
# Background Metrics Collector
# ============================================================

class MetricsCollector:
    """Background task to collect periodic metrics"""
    
    def __init__(self, interval: float = 60.0):
        self.interval = interval
        self._running = False
        self._task = None
    
    async def start(self):
        """Start metrics collection"""
        self._running = True
        self._task = asyncio.create_task(self._collect_loop())
        logger.info("Metrics collector started")
    
    async def stop(self):
        """Stop metrics collection"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Metrics collector stopped")
    
    async def _collect_loop(self):
        """Main collection loop"""
        while self._running:
            try:
                await self._collect_metrics()
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
            
            await asyncio.sleep(self.interval)
    
    async def _collect_metrics(self):
        """Collect all periodic metrics"""
        # Cache stats
        try:
            from .cache_service import get_cache_service
            cache = await get_cache_service()
            stats = cache.get_stats()
            metrics.set_cache_hit_rate(float(stats.get("hit_rate", "0").rstrip("%")))
            metrics.set_cache_size("local", stats.get("local_cache_size", 0))
        except Exception:
            pass
        
        # Database pool stats
        try:
            from .database_scaling import get_database
            db = await get_database()
            if hasattr(db._backend, 'get_stats'):
                stats = db._backend.get_stats()
                metrics.set_db_pool_stats(
                    active=stats.get("active_connections", 0),
                    idle=stats.get("free_size", 0),
                    total=stats.get("size", 0),
                )
        except Exception:
            pass
        
        # Quota stats
        try:
            from .rate_limiting import get_quota_manager
            quota = await get_quota_manager()
            stats = await quota.get_usage_stats()
            if "error" not in stats:
                metrics.set_quota_used(stats.get("global_used", 0))
                metrics.set_quota_remaining(stats.get("global_remaining", 0))
        except Exception:
            pass


# Need asyncio for the collector
import asyncio

# Global collector instance
_metrics_collector: Optional[MetricsCollector] = None


async def start_metrics_collector(interval: float = 60.0):
    """Start global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(interval)
        await _metrics_collector.start()


async def stop_metrics_collector():
    """Stop global metrics collector"""
    global _metrics_collector
    if _metrics_collector:
        await _metrics_collector.stop()
        _metrics_collector = None
