"""
Chaos Engineering Framework
Provides tools for testing system resilience through controlled failure injection.

Features:
- Network latency injection
- Service failure simulation
- Database connection drops
- Resource exhaustion testing
- Random failure injection

Usage:
    from services.shared.chaos import ChaosEngine, ChaosConfig
    
    chaos = ChaosEngine(ChaosConfig(enabled=True))
    chaos.register_experiment("latency", LatencyExperiment(min_ms=100, max_ms=500))
    
    # In your code
    async with chaos.inject("latency"):
        await some_operation()
"""

import asyncio
import random
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Set
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import functools

logger = logging.getLogger(__name__)


class ExperimentType(str, Enum):
    """Types of chaos experiments."""
    LATENCY = "latency"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    NETWORK = "network"
    DATA = "data"


class ExperimentStatus(str, Enum):
    """Status of an experiment."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class ChaosConfig:
    """Configuration for chaos engineering."""
    enabled: bool = False  # Must be explicitly enabled
    probability: float = 0.1  # 10% chance of injection by default
    dry_run: bool = True  # Log but don't inject by default
    allowed_environments: Set[str] = field(default_factory=lambda: {"development", "staging"})
    max_concurrent_experiments: int = 3
    circuit_breaker_threshold: int = 5  # Stop after 5 consecutive failures
    cooldown_seconds: int = 60  # Cooldown between experiments


@dataclass
class ExperimentResult:
    """Result of a chaos experiment."""
    experiment_id: str
    experiment_type: ExperimentType
    status: ExperimentStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: float = 0
    injected: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ChaosExperiment(ABC):
    """Base class for chaos experiments."""
    
    def __init__(self, experiment_type: ExperimentType):
        self.experiment_type = experiment_type
        self.execution_count = 0
        self.failure_count = 0
    
    @abstractmethod
    async def inject(self) -> None:
        """Inject the chaos."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up after experiment."""
        pass
    
    def should_inject(self, probability: float) -> bool:
        """Determine if chaos should be injected based on probability."""
        return random.random() < probability


class LatencyExperiment(ChaosExperiment):
    """Inject artificial latency into operations."""
    
    def __init__(
        self,
        min_ms: int = 100,
        max_ms: int = 1000,
        distribution: str = "uniform"  # uniform, gaussian, exponential
    ):
        super().__init__(ExperimentType.LATENCY)
        self.min_ms = min_ms
        self.max_ms = max_ms
        self.distribution = distribution
    
    def _calculate_delay(self) -> float:
        """Calculate delay based on distribution."""
        if self.distribution == "uniform":
            return random.uniform(self.min_ms, self.max_ms) / 1000
        elif self.distribution == "gaussian":
            mean = (self.min_ms + self.max_ms) / 2
            std = (self.max_ms - self.min_ms) / 4
            delay = random.gauss(mean, std)
            return max(self.min_ms, min(self.max_ms, delay)) / 1000
        elif self.distribution == "exponential":
            scale = (self.max_ms - self.min_ms) / 3
            delay = self.min_ms + random.expovariate(1 / scale)
            return min(self.max_ms, delay) / 1000
        return self.min_ms / 1000
    
    async def inject(self) -> None:
        """Inject latency by sleeping."""
        delay = self._calculate_delay()
        logger.info(f"Injecting latency: {delay*1000:.0f}ms")
        await asyncio.sleep(delay)
        self.execution_count += 1
    
    async def cleanup(self) -> None:
        """No cleanup needed for latency."""
        pass


class FailureExperiment(ChaosExperiment):
    """Inject failures (exceptions) into operations."""
    
    def __init__(
        self,
        exception_class: type = Exception,
        message: str = "Chaos-injected failure",
        failure_rate: float = 1.0  # Always fail when selected
    ):
        super().__init__(ExperimentType.FAILURE)
        self.exception_class = exception_class
        self.message = message
        self.failure_rate = failure_rate
    
    async def inject(self) -> None:
        """Inject failure by raising exception."""
        if random.random() < self.failure_rate:
            logger.warning(f"Injecting failure: {self.exception_class.__name__}")
            self.execution_count += 1
            raise self.exception_class(self.message)
    
    async def cleanup(self) -> None:
        """No cleanup needed for failures."""
        pass


class TimeoutExperiment(ChaosExperiment):
    """Inject timeouts by delaying beyond expected thresholds."""
    
    def __init__(
        self,
        timeout_seconds: float = 30,
        partial_timeout: bool = False  # If True, delay just under timeout
    ):
        super().__init__(ExperimentType.TIMEOUT)
        self.timeout_seconds = timeout_seconds
        self.partial_timeout = partial_timeout
    
    async def inject(self) -> None:
        """Inject timeout by sleeping beyond threshold."""
        if self.partial_timeout:
            delay = self.timeout_seconds * 0.95
        else:
            delay = self.timeout_seconds * 1.5
        
        logger.warning(f"Injecting timeout: {delay:.1f}s delay")
        await asyncio.sleep(delay)
        self.execution_count += 1
    
    async def cleanup(self) -> None:
        """No cleanup needed."""
        pass


class ResourceExhaustionExperiment(ChaosExperiment):
    """Simulate resource exhaustion (memory, CPU, connections)."""
    
    def __init__(
        self,
        resource_type: str = "memory",  # memory, cpu, connections
        intensity: float = 0.5,  # 0-1 scale
        duration_seconds: float = 5
    ):
        super().__init__(ExperimentType.RESOURCE)
        self.resource_type = resource_type
        self.intensity = intensity
        self.duration_seconds = duration_seconds
        self._allocated: List[Any] = []
    
    async def inject(self) -> None:
        """Inject resource exhaustion."""
        logger.warning(f"Injecting {self.resource_type} exhaustion at {self.intensity*100}% intensity")
        
        if self.resource_type == "memory":
            # Allocate memory blocks
            block_size = int(1024 * 1024 * 10 * self.intensity)  # Up to 10MB per block
            num_blocks = int(10 * self.intensity)
            for _ in range(num_blocks):
                self._allocated.append(bytearray(block_size))
            await asyncio.sleep(self.duration_seconds)
        
        elif self.resource_type == "cpu":
            # CPU-intensive operation
            end_time = time.time() + self.duration_seconds
            iterations = int(1000000 * self.intensity)
            while time.time() < end_time:
                _ = sum(i * i for i in range(iterations))
                await asyncio.sleep(0.01)  # Yield to event loop
        
        self.execution_count += 1
    
    async def cleanup(self) -> None:
        """Release allocated resources."""
        self._allocated.clear()


class NetworkPartitionExperiment(ChaosExperiment):
    """Simulate network partitions by blocking specific endpoints."""
    
    def __init__(
        self,
        blocked_hosts: List[str] = None,
        partition_duration_seconds: float = 10
    ):
        super().__init__(ExperimentType.NETWORK)
        self.blocked_hosts = blocked_hosts or []
        self.partition_duration_seconds = partition_duration_seconds
        self._original_resolver: Optional[Callable] = None
    
    async def inject(self) -> None:
        """Simulate network partition."""
        import socket
        
        logger.warning(f"Simulating network partition for hosts: {self.blocked_hosts}")
        
        # Store original resolver
        self._original_resolver = socket.getaddrinfo
        blocked = set(self.blocked_hosts)
        
        def blocking_resolver(host, *args, **kwargs):
            if host in blocked:
                raise socket.gaierror(8, "nodename nor servname provided, or not known")
            return self._original_resolver(host, *args, **kwargs)
        
        socket.getaddrinfo = blocking_resolver
        await asyncio.sleep(self.partition_duration_seconds)
        self.execution_count += 1
    
    async def cleanup(self) -> None:
        """Restore network connectivity."""
        import socket
        if self._original_resolver:
            socket.getaddrinfo = self._original_resolver
            self._original_resolver = None


class DataCorruptionExperiment(ChaosExperiment):
    """Simulate data corruption scenarios."""
    
    def __init__(
        self,
        corruption_type: str = "missing_field",  # missing_field, wrong_type, truncated
        target_fields: List[str] = None
    ):
        super().__init__(ExperimentType.DATA)
        self.corruption_type = corruption_type
        self.target_fields = target_fields or []
    
    async def inject(self) -> None:
        """Mark that data corruption should be applied."""
        logger.warning(f"Data corruption mode active: {self.corruption_type}")
        self.execution_count += 1
    
    def corrupt_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply corruption to data."""
        corrupted = data.copy()
        
        if self.corruption_type == "missing_field":
            for field in self.target_fields:
                corrupted.pop(field, None)
        
        elif self.corruption_type == "wrong_type":
            for field in self.target_fields:
                if field in corrupted:
                    if isinstance(corrupted[field], str):
                        corrupted[field] = 12345
                    elif isinstance(corrupted[field], int):
                        corrupted[field] = "corrupted"
        
        elif self.corruption_type == "truncated":
            for field in self.target_fields:
                if field in corrupted and isinstance(corrupted[field], str):
                    corrupted[field] = corrupted[field][:len(corrupted[field])//2]
        
        return corrupted
    
    async def cleanup(self) -> None:
        """No cleanup needed."""
        pass


class ChaosEngine:
    """
    Main chaos engineering engine.
    
    Manages experiments, tracks results, and provides safety controls.
    """
    
    def __init__(self, config: ChaosConfig = None):
        self.config = config or ChaosConfig()
        self.experiments: Dict[str, ChaosExperiment] = {}
        self.results: List[ExperimentResult] = []
        self.active_experiments: Set[str] = set()
        self.consecutive_failures = 0
        self.last_experiment_time: Optional[datetime] = None
        self._environment = "development"
    
    def set_environment(self, environment: str) -> None:
        """Set the current environment."""
        self._environment = environment
    
    def _can_run_experiment(self) -> bool:
        """Check if experiments can run."""
        if not self.config.enabled:
            return False
        
        if self._environment not in self.config.allowed_environments:
            logger.debug(f"Chaos disabled in {self._environment} environment")
            return False
        
        if len(self.active_experiments) >= self.config.max_concurrent_experiments:
            logger.debug("Max concurrent experiments reached")
            return False
        
        if self.consecutive_failures >= self.config.circuit_breaker_threshold:
            logger.warning("Chaos circuit breaker triggered - too many failures")
            return False
        
        if self.last_experiment_time:
            cooldown = timedelta(seconds=self.config.cooldown_seconds)
            if datetime.now() - self.last_experiment_time < cooldown:
                return False
        
        return True
    
    def register_experiment(self, name: str, experiment: ChaosExperiment) -> None:
        """Register an experiment."""
        self.experiments[name] = experiment
        logger.info(f"Registered chaos experiment: {name} ({experiment.experiment_type})")
    
    def unregister_experiment(self, name: str) -> None:
        """Unregister an experiment."""
        if name in self.experiments:
            del self.experiments[name]
            logger.info(f"Unregistered chaos experiment: {name}")
    
    @asynccontextmanager
    async def inject(self, experiment_name: str, force: bool = False):
        """
        Context manager for injecting chaos.
        
        Usage:
            async with chaos.inject("latency"):
                await some_operation()
        """
        experiment = self.experiments.get(experiment_name)
        if not experiment:
            yield
            return
        
        should_inject = force or (
            self._can_run_experiment() and
            experiment.should_inject(self.config.probability)
        )
        
        if not should_inject:
            yield
            return
        
        experiment_id = f"{experiment_name}_{int(time.time()*1000)}"
        result = ExperimentResult(
            experiment_id=experiment_id,
            experiment_type=experiment.experiment_type,
            status=ExperimentStatus.RUNNING,
            started_at=datetime.now()
        )
        
        self.active_experiments.add(experiment_id)
        self.last_experiment_time = datetime.now()
        
        try:
            if self.config.dry_run:
                logger.info(f"[DRY RUN] Would inject chaos: {experiment_name}")
                result.injected = False
            else:
                await experiment.inject()
                result.injected = True
            
            result.status = ExperimentStatus.COMPLETED
            self.consecutive_failures = 0
            yield
            
        except Exception as e:
            result.status = ExperimentStatus.FAILED
            result.error = str(e)
            experiment.failure_count += 1
            self.consecutive_failures += 1
            raise
        
        finally:
            result.ended_at = datetime.now()
            result.duration_ms = (result.ended_at - result.started_at).total_seconds() * 1000
            self.results.append(result)
            self.active_experiments.discard(experiment_id)
            
            try:
                await experiment.cleanup()
            except Exception as e:
                logger.error(f"Experiment cleanup failed: {e}")
    
    def chaos_decorator(self, experiment_name: str):
        """
        Decorator for adding chaos injection to functions.
        
        Usage:
            @chaos.chaos_decorator("latency")
            async def my_function():
                pass
        """
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                async with self.inject(experiment_name):
                    return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get chaos experiment statistics."""
        total = len(self.results)
        injected = sum(1 for r in self.results if r.injected)
        failed = sum(1 for r in self.results if r.status == ExperimentStatus.FAILED)
        
        by_type = {}
        for result in self.results:
            exp_type = result.experiment_type.value
            if exp_type not in by_type:
                by_type[exp_type] = {"total": 0, "injected": 0, "failed": 0}
            by_type[exp_type]["total"] += 1
            if result.injected:
                by_type[exp_type]["injected"] += 1
            if result.status == ExperimentStatus.FAILED:
                by_type[exp_type]["failed"] += 1
        
        return {
            "enabled": self.config.enabled,
            "dry_run": self.config.dry_run,
            "environment": self._environment,
            "total_experiments": total,
            "injected_count": injected,
            "failed_count": failed,
            "active_experiments": len(self.active_experiments),
            "consecutive_failures": self.consecutive_failures,
            "by_type": by_type,
            "registered_experiments": list(self.experiments.keys())
        }
    
    def reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker."""
        self.consecutive_failures = 0
        logger.info("Chaos circuit breaker reset")
    
    def abort_all(self) -> None:
        """Abort all active experiments."""
        for exp_name in list(self.active_experiments):
            logger.warning(f"Aborting experiment: {exp_name}")
        self.active_experiments.clear()


# Pre-built experiment configurations
def create_standard_experiments() -> Dict[str, ChaosExperiment]:
    """Create standard chaos experiments."""
    return {
        "light_latency": LatencyExperiment(min_ms=50, max_ms=200),
        "heavy_latency": LatencyExperiment(min_ms=500, max_ms=2000),
        "spike_latency": LatencyExperiment(min_ms=100, max_ms=5000, distribution="exponential"),
        "random_failure": FailureExperiment(message="Random chaos failure"),
        "connection_timeout": TimeoutExperiment(timeout_seconds=30),
        "memory_pressure": ResourceExhaustionExperiment(resource_type="memory", intensity=0.3),
        "cpu_pressure": ResourceExhaustionExperiment(resource_type="cpu", intensity=0.5),
    }


# FastAPI integration
def setup_chaos_routes(app, chaos_engine: ChaosEngine):
    """Add chaos engineering endpoints to FastAPI app."""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    
    router = APIRouter(prefix="/chaos", tags=["chaos"])
    
    class ExperimentConfig(BaseModel):
        name: str
        experiment_type: str
        params: Dict[str, Any] = {}
    
    @router.get("/status")
    async def get_chaos_status():
        """Get chaos engine status and statistics."""
        return chaos_engine.get_statistics()
    
    @router.post("/enable")
    async def enable_chaos():
        """Enable chaos experiments (non-production only)."""
        if chaos_engine._environment == "production":
            raise HTTPException(400, "Cannot enable chaos in production")
        chaos_engine.config.enabled = True
        chaos_engine.config.dry_run = False
        return {"status": "enabled", "dry_run": False}
    
    @router.post("/disable")
    async def disable_chaos():
        """Disable chaos experiments."""
        chaos_engine.config.enabled = False
        chaos_engine.abort_all()
        return {"status": "disabled"}
    
    @router.post("/dry-run")
    async def set_dry_run(enabled: bool = True):
        """Enable/disable dry run mode."""
        chaos_engine.config.dry_run = enabled
        return {"dry_run": enabled}
    
    @router.post("/reset")
    async def reset_chaos():
        """Reset circuit breaker and clear active experiments."""
        chaos_engine.reset_circuit_breaker()
        chaos_engine.abort_all()
        return {"status": "reset"}
    
    @router.get("/experiments")
    async def list_experiments():
        """List registered experiments."""
        return {
            name: {
                "type": exp.experiment_type.value,
                "executions": exp.execution_count,
                "failures": exp.failure_count
            }
            for name, exp in chaos_engine.experiments.items()
        }
    
    @router.post("/trigger/{experiment_name}")
    async def trigger_experiment(experiment_name: str):
        """Manually trigger an experiment."""
        if experiment_name not in chaos_engine.experiments:
            raise HTTPException(404, f"Experiment not found: {experiment_name}")
        
        if chaos_engine._environment == "production":
            raise HTTPException(400, "Cannot trigger chaos in production")
        
        try:
            async with chaos_engine.inject(experiment_name, force=True):
                pass
            return {"status": "completed", "experiment": experiment_name}
        except Exception as e:
            return {"status": "failed", "experiment": experiment_name, "error": str(e)}
    
    app.include_router(router)
