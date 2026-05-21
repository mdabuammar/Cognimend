"""
Graceful Shutdown Manager

Provides:
- Signal handling (SIGTERM, SIGINT)
- In-flight request tracking
- Connection draining
- Resource cleanup
- Shutdown hooks
"""
import asyncio
import signal
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set, Awaitable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ShutdownPhase(str, Enum):
    """Shutdown phases."""
    RUNNING = "running"
    DRAINING = "draining"       # Stop accepting new requests
    COMPLETING = "completing"   # Wait for in-flight requests
    CLEANUP = "cleanup"         # Run shutdown hooks
    TERMINATED = "terminated"


@dataclass
class ShutdownConfig:
    """Configuration for graceful shutdown."""
    drain_timeout: float = 5.0      # Time to drain new requests
    complete_timeout: float = 30.0  # Time to complete in-flight requests
    cleanup_timeout: float = 10.0   # Time for cleanup hooks
    force_exit_timeout: float = 45.0  # Total max shutdown time


@dataclass
class ShutdownState:
    """Current shutdown state."""
    phase: ShutdownPhase = ShutdownPhase.RUNNING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    in_flight_count: int = 0
    shutdown_reason: Optional[str] = None
    errors: List[str] = field(default_factory=list)


class GracefulShutdownManager:
    """
    Manages graceful shutdown of a service.
    
    Features:
    - Signal handling for SIGTERM/SIGINT
    - Request tracking and draining
    - Ordered shutdown hooks
    - Timeout enforcement
    """
    
    def __init__(self, config: Optional[ShutdownConfig] = None):
        self.config = config or ShutdownConfig()
        self.state = ShutdownState()
        self._shutdown_hooks: List[tuple] = []  # (priority, name, fn)
        self._in_flight: Set[str] = set()
        self._shutdown_event = asyncio.Event()
        self._health_checker = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def register_health_checker(self, health_checker) -> None:
        """Register health checker to update ready state on shutdown."""
        self._health_checker = health_checker
    
    def register_shutdown_hook(
        self,
        name: str,
        hook: Callable[[], Awaitable[None]],
        priority: int = 50
    ) -> None:
        """
        Register a shutdown hook.
        
        Args:
            name: Name for logging
            hook: Async function to call on shutdown
            priority: Lower = earlier (0-100)
        """
        self._shutdown_hooks.append((priority, name, hook))
        self._shutdown_hooks.sort(key=lambda x: x[0])
        logger.debug(f"Registered shutdown hook: {name} (priority: {priority})")
    
    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        try:
            self._loop = asyncio.get_running_loop()
            
            for sig in (signal.SIGTERM, signal.SIGINT):
                self._loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(
                        self._handle_signal(s)
                    )
                )
            
            logger.info("Signal handlers registered for SIGTERM, SIGINT")
        except (ValueError, RuntimeError) as e:
            # Windows doesn't support add_signal_handler for all signals
            logger.warning(f"Could not set up signal handlers: {e}")
            # Fallback to signal.signal
            try:
                signal.signal(signal.SIGTERM, self._sync_signal_handler)
                signal.signal(signal.SIGINT, self._sync_signal_handler)
                logger.info("Fallback signal handlers registered")
            except Exception as e2:
                logger.warning(f"Fallback signal handlers failed: {e2}")
    
    def _sync_signal_handler(self, signum, frame):
        """Synchronous signal handler for Windows."""
        logger.info(f"Received signal {signum}")
        if self._loop:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(
                    self._handle_signal(signum)
                )
            )
    
    async def _handle_signal(self, sig: int) -> None:
        """Handle shutdown signal."""
        sig_name = signal.Signals(sig).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown")
        await self.shutdown(reason=f"Signal: {sig_name}")
    
    @asynccontextmanager
    async def track_request(self, request_id: str = None):
        """
        Context manager to track in-flight requests.
        
        Usage:
            async with shutdown_manager.track_request("req-123"):
                # Handle request
                pass
        """
        if request_id is None:
            request_id = f"req-{id(asyncio.current_task())}"
        
        self._in_flight.add(request_id)
        self.state.in_flight_count = len(self._in_flight)
        
        try:
            yield
        finally:
            self._in_flight.discard(request_id)
            self.state.in_flight_count = len(self._in_flight)
    
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self.state.phase != ShutdownPhase.RUNNING
    
    def is_accepting_requests(self) -> bool:
        """Check if service should accept new requests."""
        return self.state.phase == ShutdownPhase.RUNNING
    
    def get_in_flight_count(self) -> int:
        """Get number of in-flight requests."""
        return len(self._in_flight)
    
    async def shutdown(self, reason: str = "Shutdown requested") -> None:
        """
        Initiate graceful shutdown.
        
        Phases:
        1. DRAINING - Stop accepting new requests
        2. COMPLETING - Wait for in-flight requests
        3. CLEANUP - Run shutdown hooks
        4. TERMINATED - Exit
        """
        if self.state.phase != ShutdownPhase.RUNNING:
            logger.warning(f"Shutdown already in progress: {self.state.phase}")
            return
        
        self.state.started_at = time.time()
        self.state.shutdown_reason = reason
        logger.info(f"Starting graceful shutdown: {reason}")
        
        try:
            # Phase 1: Draining
            await self._phase_draining()
            
            # Phase 2: Completing
            await self._phase_completing()
            
            # Phase 3: Cleanup
            await self._phase_cleanup()
            
        except asyncio.TimeoutError:
            logger.error("Shutdown timeout - forcing exit")
            self.state.errors.append("Shutdown timeout")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
            self.state.errors.append(str(e))
        finally:
            self.state.phase = ShutdownPhase.TERMINATED
            self.state.completed_at = time.time()
            self._shutdown_event.set()
        
        duration = self.state.completed_at - self.state.started_at
        logger.info(f"Graceful shutdown completed in {duration:.2f}s")
    
    async def _phase_draining(self) -> None:
        """Phase 1: Stop accepting new requests."""
        self.state.phase = ShutdownPhase.DRAINING
        logger.info("Shutdown phase: DRAINING")
        
        # Mark as not ready for traffic
        if self._health_checker:
            self._health_checker.set_shutting_down()
        
        # Brief wait to allow load balancer to stop sending requests
        await asyncio.sleep(min(self.config.drain_timeout, 2.0))
    
    async def _phase_completing(self) -> None:
        """Phase 2: Wait for in-flight requests to complete."""
        self.state.phase = ShutdownPhase.COMPLETING
        logger.info(f"Shutdown phase: COMPLETING ({len(self._in_flight)} in-flight)")
        
        start_time = time.time()
        
        while self._in_flight:
            elapsed = time.time() - start_time
            
            if elapsed >= self.config.complete_timeout:
                remaining = len(self._in_flight)
                logger.warning(f"Complete timeout, {remaining} requests still in-flight")
                break
            
            remaining_time = self.config.complete_timeout - elapsed
            logger.debug(f"Waiting for {len(self._in_flight)} requests ({remaining_time:.1f}s remaining)")
            
            await asyncio.sleep(0.5)
        
        if not self._in_flight:
            logger.info("All in-flight requests completed")
    
    async def _phase_cleanup(self) -> None:
        """Phase 3: Run shutdown hooks."""
        self.state.phase = ShutdownPhase.CLEANUP
        logger.info(f"Shutdown phase: CLEANUP ({len(self._shutdown_hooks)} hooks)")
        
        for priority, name, hook in self._shutdown_hooks:
            try:
                logger.debug(f"Running shutdown hook: {name}")
                await asyncio.wait_for(
                    hook(),
                    timeout=self.config.cleanup_timeout / len(self._shutdown_hooks)
                    if self._shutdown_hooks else self.config.cleanup_timeout
                )
                logger.debug(f"Shutdown hook completed: {name}")
            except asyncio.TimeoutError:
                msg = f"Shutdown hook timeout: {name}"
                logger.error(msg)
                self.state.errors.append(msg)
            except Exception as e:
                msg = f"Shutdown hook error ({name}): {e}"
                logger.error(msg)
                self.state.errors.append(msg)
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown to complete."""
        await self._shutdown_event.wait()
    
    def get_state(self) -> Dict[str, Any]:
        """Get current shutdown state."""
        return {
            "phase": self.state.phase.value,
            "in_flight_count": self.state.in_flight_count,
            "shutdown_reason": self.state.shutdown_reason,
            "errors": self.state.errors,
            "duration_seconds": (
                time.time() - self.state.started_at
                if self.state.started_at else None
            )
        }


# ============================================================
# COMMON SHUTDOWN HOOKS
# ============================================================

def create_database_pool_hook(db_pool) -> Callable[[], Awaitable[None]]:
    """Create a shutdown hook to close database pool."""
    async def hook():
        if db_pool:
            logger.info("Closing database pool...")
            db_pool.close_all()
            logger.info("Database pool closed")
    return hook


def create_redis_hook(cache) -> Callable[[], Awaitable[None]]:
    """Create a shutdown hook to close Redis connections."""
    async def hook():
        if cache and hasattr(cache, 'close'):
            logger.info("Closing Redis connection...")
            await cache.close() if asyncio.iscoroutinefunction(cache.close) else cache.close()
            logger.info("Redis connection closed")
    return hook


def create_qdrant_hook(qdrant_client) -> Callable[[], Awaitable[None]]:
    """Create a shutdown hook to close Qdrant client."""
    async def hook():
        if qdrant_client and hasattr(qdrant_client, 'close'):
            logger.info("Closing Qdrant client...")
            qdrant_client.close()
            logger.info("Qdrant client closed")
    return hook


def create_flush_metrics_hook(metrics_client) -> Callable[[], Awaitable[None]]:
    """Create a shutdown hook to flush metrics."""
    async def hook():
        if metrics_client and hasattr(metrics_client, 'flush'):
            logger.info("Flushing metrics...")
            await metrics_client.flush() if asyncio.iscoroutinefunction(metrics_client.flush) else metrics_client.flush()
            logger.info("Metrics flushed")
    return hook


# ============================================================
# FASTAPI INTEGRATION
# ============================================================

def create_lifespan_manager(
    service_name: str,
    health_checker,
    shutdown_manager: GracefulShutdownManager,
    startup_fn: Optional[Callable[[], Awaitable[None]]] = None,
    shutdown_fn: Optional[Callable[[], Awaitable[None]]] = None
):
    """
    Create a FastAPI lifespan context manager with graceful shutdown.
    
    Usage:
        health_checker = HealthChecker("my-service")
        shutdown_manager = GracefulShutdownManager()
        
        app = FastAPI(lifespan=create_lifespan_manager(
            "my-service",
            health_checker,
            shutdown_manager
        ))
    """
    @asynccontextmanager
    async def lifespan(app):
        logger.info(f"🚀 {service_name} starting...")
        
        # Register health checker with shutdown manager
        shutdown_manager.register_health_checker(health_checker)
        
        # Set up signal handlers
        shutdown_manager.setup_signal_handlers()
        
        # Run custom startup
        if startup_fn:
            await startup_fn()
        
        # Mark as ready
        health_checker.set_ready(True)
        logger.info(f"✅ {service_name} ready")
        
        yield
        
        logger.info(f"🛑 {service_name} shutting down...")
        
        # Run graceful shutdown if not already triggered by signal
        if not shutdown_manager.is_shutting_down():
            await shutdown_manager.shutdown(reason="Lifespan ended")
        
        # Run custom shutdown
        if shutdown_fn:
            await shutdown_fn()
        
        logger.info(f"👋 {service_name} shutdown complete")
    
    return lifespan


# ============================================================
# REQUEST TRACKING MIDDLEWARE
# ============================================================

class ShutdownMiddleware:
    """
    ASGI middleware for request tracking and shutdown rejection.
    
    - Tracks all in-flight requests
    - Returns 503 during shutdown
    """
    
    def __init__(self, app, shutdown_manager: GracefulShutdownManager):
        self.app = app
        self.shutdown_manager = shutdown_manager
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Reject new requests during shutdown
        if not self.shutdown_manager.is_accepting_requests():
            # Allow health checks
            path = scope.get("path", "")
            if not path.startswith("/health"):
                response = {
                    "status": 503,
                    "body": b'{"error": "Service is shutting down"}',
                    "headers": [(b"content-type", b"application/json")]
                }
                await send({
                    "type": "http.response.start",
                    "status": 503,
                    "headers": [(b"content-type", b"application/json")],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"error": "Service is shutting down"}',
                })
                return
        
        # Track the request
        request_id = f"req-{id(asyncio.current_task())}"
        
        async with self.shutdown_manager.track_request(request_id):
            await self.app(scope, receive, send)


def add_shutdown_middleware(app, shutdown_manager: GracefulShutdownManager):
    """Add shutdown middleware to FastAPI app."""
    app.add_middleware(ShutdownMiddleware, shutdown_manager=shutdown_manager)
    return app
