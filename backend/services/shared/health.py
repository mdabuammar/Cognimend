"""
Comprehensive Health Check System

Provides:
- Liveness probes (is the service running?)
- Readiness probes (can the service accept traffic?)
- Deep health checks (all dependencies working?)
- Startup probes (is the service fully initialized?)
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Awaitable
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


class ProbeType(str, Enum):
    """Kubernetes probe types."""
    LIVENESS = "liveness"
    READINESS = "readiness"
    STARTUP = "startup"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus
    latency_ms: float = 0.0
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    last_checked: Optional[datetime] = None
    consecutive_failures: int = 0


@dataclass
class HealthCheckResult:
    """Overall health check result."""
    status: HealthStatus
    service: str
    version: str
    timestamp: datetime
    uptime_seconds: float
    components: Dict[str, ComponentHealth]
    checks: Dict[ProbeType, bool]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "status": self.status.value,
            "service": self.service,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "uptime_seconds": round(self.uptime_seconds, 2),
            "components": {
                name: {
                    "status": comp.status.value,
                    "latency_ms": round(comp.latency_ms, 2),
                    "message": comp.message,
                    "details": comp.details,
                    "consecutive_failures": comp.consecutive_failures,
                }
                for name, comp in self.components.items()
            },
            "checks": {
                probe.value: status for probe, status in self.checks.items()
            }
        }


class HealthChecker:
    """
    Centralized health check manager.
    
    Supports:
    - Multiple check types (liveness, readiness, startup)
    - Async health checks with timeout
    - Failure counting and degradation
    - Caching of health results
    """
    
    def __init__(
        self,
        service_name: str,
        version: str = "2.0.0",
        check_timeout: float = 5.0,
        cache_ttl: float = 5.0,
        failure_threshold: int = 3
    ):
        self.service_name = service_name
        self.version = version
        self.check_timeout = check_timeout
        self.cache_ttl = cache_ttl
        self.failure_threshold = failure_threshold
        
        self.start_time = time.time()
        self._is_ready = False
        self._is_shutting_down = False
        
        # Registered checks: name -> (check_fn, required_for_readiness)
        self._checks: Dict[str, tuple] = {}
        self._component_health: Dict[str, ComponentHealth] = {}
        self._last_full_check: Optional[float] = None
        self._cached_result: Optional[HealthCheckResult] = None
    
    def register_check(
        self,
        name: str,
        check_fn: Callable[[], Awaitable[tuple]],
        required_for_readiness: bool = True,
        required_for_liveness: bool = False
    ) -> None:
        """
        Register a health check function.
        
        Args:
            name: Component name
            check_fn: Async function returning (healthy: bool, message: str, details: dict)
            required_for_readiness: If False, degraded status allowed
            required_for_liveness: If True, failure means service is dead
        """
        self._checks[name] = (check_fn, required_for_readiness, required_for_liveness)
        self._component_health[name] = ComponentHealth(
            name=name,
            status=HealthStatus.UNKNOWN
        )
        logger.info(f"Registered health check: {name}")
    
    def set_ready(self, ready: bool = True) -> None:
        """Mark service as ready to accept traffic."""
        self._is_ready = ready
        logger.info(f"Service ready state: {ready}")
    
    def set_shutting_down(self) -> None:
        """Mark service as shutting down (not ready for new traffic)."""
        self._is_shutting_down = True
        self._is_ready = False
    
    def update_component_status(self, component_name: str, healthy: bool | HealthStatus, message: str = "") -> None:
        """Update the health status of a component.
        
        Args:
            component_name: Name of the component
            healthy: Whether the component is healthy (bool or HealthStatus enum)
            message: Optional status message
        """
        # Convert bool or HealthStatus to HealthStatus
        if isinstance(healthy, bool):
            status = HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY
        elif isinstance(healthy, HealthStatus):
            status = healthy
        else:
            status = HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY
        
        if component_name not in self._component_health:
            self._component_health[component_name] = ComponentHealth(
                name=component_name,
                status=status,
                message=message,
                last_checked=datetime.now()
            )
        else:
            self._component_health[component_name].status = status
            self._component_health[component_name].message = message
            self._component_health[component_name].last_checked = datetime.now()
        
        logger.debug(f"Updated component {component_name}: {status.value}")
    
    def get_overall_status(self) -> HealthStatus:
        """Get overall health status based on component health.
        
        Returns:
            HEALTHY if all components healthy
            DEGRADED if some components unhealthy or degraded but service can function
            UNHEALTHY if critical components unhealthy
        """
        if not self._component_health:
            return HealthStatus.HEALTHY
        
        statuses = [comp.status for comp in self._component_health.values()]
        
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    async def check_component(
        self,
        name: str,
        check_fn: Callable[[], Awaitable[tuple]]
    ) -> ComponentHealth:
        """Run a single component health check with timeout."""
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(
                check_fn(),
                timeout=self.check_timeout
            )
            
            if isinstance(result, tuple):
                healthy, message, details = result[0], result[1] if len(result) > 1 else None, result[2] if len(result) > 2 else {}
            else:
                healthy, message, details = result, None, {}
            
            latency_ms = (time.time() - start_time) * 1000
            
            if healthy:
                self._component_health[name] = ComponentHealth(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency_ms,
                    message=message,
                    details=details or {},
                    last_checked=datetime.now(),
                    consecutive_failures=0
                )
            else:
                prev_failures = self._component_health[name].consecutive_failures
                self._component_health[name] = ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=latency_ms,
                    message=message or "Check failed",
                    details=details or {},
                    last_checked=datetime.now(),
                    consecutive_failures=prev_failures + 1
                )
        
        except asyncio.TimeoutError:
            prev_failures = self._component_health[name].consecutive_failures
            self._component_health[name] = ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=self.check_timeout * 1000,
                message=f"Check timed out after {self.check_timeout}s",
                last_checked=datetime.now(),
                consecutive_failures=prev_failures + 1
            )
        
        except Exception as e:
            prev_failures = self._component_health[name].consecutive_failures
            self._component_health[name] = ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.time() - start_time) * 1000,
                message=str(e)[:100],
                last_checked=datetime.now(),
                consecutive_failures=prev_failures + 1
            )
        
        return self._component_health[name]
    
    async def check_all(self, use_cache: bool = True) -> HealthCheckResult:
        """
        Run all health checks.
        
        Args:
            use_cache: Use cached result if within TTL
        """
        now = time.time()
        
        # Return cached result if valid
        if (
            use_cache and
            self._cached_result and
            self._last_full_check and
            (now - self._last_full_check) < self.cache_ttl
        ):
            return self._cached_result
        
        # Run all checks in parallel
        tasks = []
        for name, (check_fn, _, _) in self._checks.items():
            tasks.append(self.check_component(name, check_fn))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Determine overall status
        overall_status = self._calculate_overall_status()
        
        # Determine probe statuses
        checks = {
            ProbeType.LIVENESS: self._check_liveness(),
            ProbeType.READINESS: self._check_readiness(),
            ProbeType.STARTUP: self._is_ready,
        }
        
        result = HealthCheckResult(
            status=overall_status,
            service=self.service_name,
            version=self.version,
            timestamp=datetime.now(),
            uptime_seconds=now - self.start_time,
            components=self._component_health.copy(),
            checks=checks
        )
        
        self._cached_result = result
        self._last_full_check = now
        
        return result
    
    def _calculate_overall_status(self) -> HealthStatus:
        """Calculate overall health status from components."""
        if self._is_shutting_down:
            return HealthStatus.UNHEALTHY
        
        statuses = [c.status for c in self._component_health.values()]
        
        if not statuses:
            return HealthStatus.HEALTHY
        
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            # Check if any unhealthy component is required
            for name, (_, required, _) in self._checks.items():
                if required and self._component_health[name].status == HealthStatus.UNHEALTHY:
                    return HealthStatus.UNHEALTHY
            return HealthStatus.DEGRADED
        
        if any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    def _check_liveness(self) -> bool:
        """
        Check if service is alive.
        
        Returns False only if a critical component has failed
        beyond the failure threshold.
        """
        if self._is_shutting_down:
            return True  # Still alive, just shutting down
        
        for name, (_, _, required_for_liveness) in self._checks.items():
            if required_for_liveness:
                component = self._component_health.get(name)
                if component and component.consecutive_failures >= self.failure_threshold:
                    return False
        
        return True
    
    def _check_readiness(self) -> bool:
        """
        Check if service is ready to accept traffic.
        
        Returns False if:
        - Service hasn't completed startup
        - Service is shutting down
        - Any required component is unhealthy
        """
        if not self._is_ready or self._is_shutting_down:
            return False
        
        for name, (_, required, _) in self._checks.items():
            if required:
                component = self._component_health.get(name)
                if component and component.status == HealthStatus.UNHEALTHY:
                    return False
        
        return True
    
    async def liveness(self) -> Dict[str, Any]:
        """Fast liveness probe response."""
        is_live = self._check_liveness()
        return {
            "status": "ok" if is_live else "error",
            "service": self.service_name,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": round(time.time() - self.start_time, 2)
        }
    
    async def readiness(self) -> Dict[str, Any]:
        """Fast readiness probe response."""
        is_ready = self._check_readiness()
        return {
            "status": "ok" if is_ready else "error",
            "service": self.service_name,
            "ready": is_ready,
            "shutting_down": self._is_shutting_down,
            "timestamp": datetime.now().isoformat()
        }
    
    async def startup(self) -> Dict[str, Any]:
        """Startup probe response."""
        return {
            "status": "ok" if self._is_ready else "starting",
            "service": self.service_name,
            "started": self._is_ready,
            "timestamp": datetime.now().isoformat()
        }


# ============================================================
# PRE-BUILT HEALTH CHECK FUNCTIONS
# ============================================================

def create_database_check(db_manager) -> Callable[[], Awaitable[tuple]]:
    """Create a database health check function."""
    async def check() -> tuple:
        try:
            conn = db_manager.get_connection()
            cur = conn.cursor()
            
            start = time.time()
            cur.execute("SELECT 1")
            latency = (time.time() - start) * 1000
            
            cur.close()
            db_manager.return_connection(conn)
            
            return True, None, {"latency_ms": round(latency, 2)}
        except Exception as e:
            return False, str(e)[:100], {}
    
    return check


def create_redis_check(cache) -> Callable[[], Awaitable[tuple]]:
    """Create a Redis health check function."""
    async def check() -> tuple:
        if cache is None:
            return True, "Cache disabled", {"enabled": False}
        
        try:
            is_available = cache.is_available()
            if is_available:
                stats = await cache.get_stats() if hasattr(cache, 'get_stats') else {}
                return True, None, stats
            return False, "Redis unavailable", {}
        except Exception as e:
            return False, str(e)[:100], {}
    
    return check


def create_qdrant_check(qdrant_client) -> Callable[[], Awaitable[tuple]]:
    """Create a Qdrant health check function."""
    async def check() -> tuple:
        if qdrant_client is None:
            return True, "Qdrant disabled", {"enabled": False}
        
        try:
            start = time.time()
            collections = qdrant_client.get_collections()
            latency = (time.time() - start) * 1000
            
            return True, None, {
                "latency_ms": round(latency, 2),
                "collections": len(collections.collections)
            }
        except Exception as e:
            return False, str(e)[:100], {}
    
    return check


def create_openrouter_check(client) -> Callable[[], Awaitable[tuple]]:
    """Create an OpenRouter health check function."""
    async def check() -> tuple:
        if client is None:
            return True, "OpenRouter disabled", {"enabled": False}
        
        # Just check if client exists - actual API check would be expensive
        return True, None, {"enabled": True}
    
    return check


def create_circuit_breaker_check(circuit_breakers: Dict[str, Any]) -> Callable[[], Awaitable[tuple]]:
    """Create a circuit breaker health check function."""
    async def check() -> tuple:
        if not circuit_breakers:
            return True, "No circuit breakers", {}
        
        states = {}
        any_open = False
        
        for name, breaker in circuit_breakers.items():
            if breaker:
                state = breaker.get_state() if hasattr(breaker, 'get_state') else "unknown"
                states[name] = state
                if state == "open":
                    any_open = True
        
        if any_open:
            return True, "Some circuits open", {"states": states, "degraded": True}
        
        return True, None, {"states": states}
    
    return check


# ============================================================
# FASTAPI INTEGRATION
# ============================================================

def setup_health_routes(app, health_checker: HealthChecker):
    """
    Add health check routes to a FastAPI app.
    
    Adds:
    - /health - Full health check
    - /health/live - Liveness probe
    - /health/ready - Readiness probe
    - /health/startup - Startup probe
    """
    from fastapi import Response
    
    @app.get("/health")
    async def health_check():
        """Comprehensive health check."""
        result = await health_checker.check_all()
        return result.to_dict()
    
    @app.get("/health/live")
    async def liveness_probe(response: Response):
        """Kubernetes liveness probe."""
        result = await health_checker.liveness()
        if result["status"] != "ok":
            response.status_code = 503
        return result
    
    @app.get("/health/ready")
    async def readiness_probe(response: Response):
        """Kubernetes readiness probe."""
        result = await health_checker.readiness()
        if result["status"] != "ok":
            response.status_code = 503
        return result
    
    @app.get("/health/startup")
    async def startup_probe(response: Response):
        """Kubernetes startup probe."""
        result = await health_checker.startup()
        if result["status"] != "ok":
            response.status_code = 503
        return result
    
    return app
