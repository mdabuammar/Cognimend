"""
Reliability Integration Module
Provides easy integration of all reliability features into FastAPI services.

Usage:
    from services.shared.reliability import setup_reliability
    
    # In your main.py
    setup_reliability(
        app,
        service_name="query-service",
        enable_chaos=True,  # Non-production only
        enable_failover=True
    )
"""

import os
import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import hashlib
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling idempotent requests.
    
    Tracks requests by idempotency key and returns cached responses
    for duplicate requests.
    """
    
    def __init__(
        self,
        app,
        redis_client=None,
        ttl_seconds: int = 86400,  # 24 hours
        methods: List[str] = None
    ):
        super().__init__(app)
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self.methods = methods or ["POST", "PUT", "PATCH"]
        self._memory_cache: Dict[str, Dict] = {}
    
    async def dispatch(self, request: Request, call_next):
        # Only apply to specified methods
        if request.method not in self.methods:
            return await call_next(request)
        
        # Get idempotency key from header
        idempotency_key = request.headers.get("X-Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)
        
        # Generate storage key
        storage_key = f"idempotency:{request.method}:{request.url.path}:{idempotency_key}"
        
        # Check for cached response
        cached = await self._get_cached(storage_key)
        if cached:
            logger.debug(f"Returning cached response for idempotency key: {idempotency_key}")
            return Response(
                content=cached["body"],
                status_code=cached["status_code"],
                headers=cached.get("headers", {}),
                media_type=cached.get("media_type", "application/json")
            )
        
        # Execute request
        response = await call_next(request)
        
        # Cache successful responses (2xx)
        if 200 <= response.status_code < 300:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # Cache the response
            cache_data = {
                "body": body.decode(),
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
                "cached_at": datetime.now().isoformat()
            }
            await self._set_cached(storage_key, cache_data)
            
            # Return new response with body
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        
        return response
    
    async def _get_cached(self, key: str) -> Optional[Dict]:
        """Get cached response."""
        if self.redis:
            try:
                data = await self.redis.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        
        return self._memory_cache.get(key)
    
    async def _set_cached(self, key: str, data: Dict):
        """Cache a response."""
        if self.redis:
            try:
                await self.redis.setex(key, self.ttl_seconds, json.dumps(data))
                return
            except Exception as e:
                logger.error(f"Redis set error: {e}")
        
        # Fallback to memory cache
        self._memory_cache[key] = data
        
        # Cleanup old entries (simple LRU)
        if len(self._memory_cache) > 1000:
            oldest = sorted(self._memory_cache.items(), 
                          key=lambda x: x[1].get("cached_at", ""))[:500]
            for k, _ in oldest:
                del self._memory_cache[k]


class RequestFingerprintMiddleware(BaseHTTPMiddleware):
    """
    Generates request fingerprints for deduplication and tracing.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Generate fingerprint
        fingerprint_data = f"{request.method}:{request.url}:{request.headers.get('user-agent', '')}"
        fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]
        
        # Add to request state
        request.state.fingerprint = fingerprint
        
        response = await call_next(request)
        
        # Add fingerprint to response headers
        response.headers["X-Request-Fingerprint"] = fingerprint
        
        return response


def setup_reliability(
    app: FastAPI,
    service_name: str,
    redis_client=None,
    db_pool=None,
    qdrant_client=None,
    enable_chaos: bool = False,
    enable_failover: bool = False,
    enable_idempotency: bool = True,
    environment: str = None
):
    """
    Set up all reliability features for a FastAPI app.
    
    Args:
        app: FastAPI application
        service_name: Name of the service
        redis_client: Redis client for distributed features
        db_pool: Database pool for health checks
        qdrant_client: Qdrant client for health checks
        enable_chaos: Enable chaos engineering (non-production only)
        enable_failover: Enable automated failover
        enable_idempotency: Enable idempotency middleware
        environment: Current environment (development/staging/production)
    """
    env = environment or os.getenv("ENVIRONMENT", "development")
    
    logger.info(f"Setting up reliability for {service_name} in {env}")
    
    # Add request fingerprinting
    app.add_middleware(RequestFingerprintMiddleware)
    
    # Add idempotency middleware
    if enable_idempotency:
        app.add_middleware(
            IdempotencyMiddleware,
            redis_client=redis_client,
            ttl_seconds=86400
        )
        logger.info("✅ Idempotency middleware enabled")
    
    # Setup chaos engineering (non-production only)
    if enable_chaos and env != "production":
        try:
            from services.shared.chaos import (
                ChaosEngine, ChaosConfig, create_standard_experiments,
                setup_chaos_routes
            )
            
            chaos_engine = ChaosEngine(ChaosConfig(
                enabled=False,  # Start disabled, enable via API
                dry_run=True,
                probability=0.1,
                allowed_environments={"development", "staging", "test"}
            ))
            chaos_engine.set_environment(env)
            
            # Register standard experiments
            for name, exp in create_standard_experiments().items():
                chaos_engine.register_experiment(name, exp)
            
            # Add chaos routes
            setup_chaos_routes(app, chaos_engine)
            
            # Store in app state for access
            app.state.chaos_engine = chaos_engine
            
            logger.info("✅ Chaos engineering enabled (dry-run mode)")
        except ImportError as e:
            logger.warning(f"Chaos module not available: {e}")
    
    # Setup failover management
    if enable_failover:
        try:
            from services.shared.failover import (
                FailoverManager, FailoverConfig, setup_failover_routes
            )
            
            failover_manager = FailoverManager(FailoverConfig(
                health_check_interval_seconds=10.0,
                failure_threshold=3,
                auto_failback=True
            ))
            
            # Add failover routes
            setup_failover_routes(app, failover_manager)
            
            # Store in app state
            app.state.failover_manager = failover_manager
            
            logger.info("✅ Failover management enabled")
        except ImportError as e:
            logger.warning(f"Failover module not available: {e}")
    
    # Setup enhanced circuit breakers
    try:
        from services.shared.circuit_breaker import (
            CircuitBreakerRegistry, setup_circuit_breaker_routes
        )
        
        # Add circuit breaker routes
        setup_circuit_breaker_routes(app)
        
        logger.info("✅ Circuit breaker management enabled")
    except ImportError as e:
        logger.debug(f"Circuit breaker module not available: {e}")
    
    # Setup consistency routes
    try:
        from services.shared.consistency import (
            DistributedLock, LockConfig, setup_consistency_routes
        )
        
        if redis_client:
            lock = DistributedLock(redis_client, LockConfig())
            setup_consistency_routes(app, lock)
            app.state.distributed_lock = lock
            logger.info("✅ Consistency features enabled")
    except ImportError as e:
        logger.debug(f"Consistency module not available: {e}")
    
    # Add reliability status endpoint
    @app.get("/reliability/status", tags=["reliability"])
    async def get_reliability_status():
        """Get overall reliability status."""
        status = {
            "service": service_name,
            "environment": env,
            "features": {
                "idempotency": enable_idempotency,
                "chaos_engineering": enable_chaos and env != "production",
                "failover": enable_failover
            }
        }
        
        # Add chaos status
        if hasattr(app.state, "chaos_engine"):
            status["chaos"] = app.state.chaos_engine.get_statistics()
        
        # Add failover status
        if hasattr(app.state, "failover_manager"):
            status["failover"] = app.state.failover_manager.get_status()
        
        return status
    
    logger.info(f"✅ Reliability setup complete for {service_name}")
    
    return {
        "chaos_engine": getattr(app.state, "chaos_engine", None),
        "failover_manager": getattr(app.state, "failover_manager", None),
        "distributed_lock": getattr(app.state, "distributed_lock", None)
    }


def get_reliability_score(
    has_health_checks: bool = False,
    has_graceful_shutdown: bool = False,
    has_circuit_breakers: bool = False,
    has_retry_logic: bool = False,
    has_idempotency: bool = False,
    has_distributed_locks: bool = False,
    has_failover: bool = False,
    has_chaos_testing: bool = False,
    has_backups: bool = False,
    has_dr_plan: bool = False
) -> Dict[str, Any]:
    """
    Calculate reliability score based on implemented features.
    
    Returns score breakdown and overall rating.
    """
    scores = {
        "Health Checks": 10 if has_health_checks else 0,
        "Graceful Shutdown": 10 if has_graceful_shutdown else 0,
        "Circuit Breakers": 10 if has_circuit_breakers else 0,
        "Retry Logic": 10 if has_retry_logic else 0,
        "Idempotency": 10 if has_idempotency else 0,
        "Distributed Locks": 10 if has_distributed_locks else 0,
        "Failover": 10 if has_failover else 0,
        "Chaos Testing": 10 if has_chaos_testing else 0,
        "Backups": 10 if has_backups else 0,
        "DR Plan": 10 if has_dr_plan else 0
    }
    
    total = sum(scores.values())
    max_score = len(scores) * 10
    percentage = (total / max_score) * 100
    
    if percentage >= 90:
        rating = "Excellent"
    elif percentage >= 70:
        rating = "Good"
    elif percentage >= 50:
        rating = "Fair"
    else:
        rating = "Needs Improvement"
    
    return {
        "scores": scores,
        "total": total,
        "max_score": max_score,
        "percentage": percentage,
        "rating": rating,
        "recommendations": [
            name for name, score in scores.items() if score == 0
        ]
    }
