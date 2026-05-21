"""
Chaos Engineering Test Suite
Automated chaos tests for validating system resilience.

Run with:
    python -m pytest services/tests/test_chaos.py -v
    
Or run specific scenarios:
    python services/tests/test_chaos.py --scenario latency
"""

import asyncio
import pytest
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass

# Import chaos engineering components
import sys
sys.path.insert(0, "../..")

from services.shared.chaos import (
    ChaosEngine,
    ChaosConfig,
    LatencyExperiment,
    FailureExperiment,
    TimeoutExperiment,
    ResourceExhaustionExperiment,
    ExperimentType,
    ExperimentStatus,
    create_standard_experiments
)


@dataclass
class ChaosTestResult:
    """Result of a chaos test."""
    scenario_name: str
    passed: bool
    duration_ms: float
    observations: List[str]
    metrics: Dict[str, Any]


class ChaosTestHarness:
    """
    Harness for running chaos engineering tests.
    
    Provides structured way to:
    1. Define test scenarios
    2. Inject failures
    3. Observe system behavior
    4. Validate recovery
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.chaos = ChaosEngine(ChaosConfig(
            enabled=True,
            dry_run=False,
            probability=1.0,  # Always inject during tests
            allowed_environments={"test", "development", "staging"}
        ))
        self.chaos.set_environment("test")
        self.results: List[ChaosTestResult] = []
        
        # Register standard experiments
        for name, exp in create_standard_experiments().items():
            self.chaos.register_experiment(name, exp)
    
    async def run_scenario(
        self,
        name: str,
        chaos_type: str,
        operation: callable,
        validate: callable,
        recovery_time_seconds: float = 5.0
    ) -> ChaosTestResult:
        """
        Run a chaos test scenario.
        
        Args:
            name: Scenario name
            chaos_type: Type of chaos to inject
            operation: The operation to test
            validate: Validation function (returns bool)
            recovery_time_seconds: Time to wait for recovery
        """
        observations = []
        metrics = {
            "chaos_injected": False,
            "operation_succeeded": False,
            "recovered": False,
            "recovery_time_ms": 0
        }
        
        start_time = time.time()
        
        try:
            # Phase 1: Baseline check
            observations.append("Phase 1: Baseline check")
            baseline_ok = await validate()
            if not baseline_ok:
                observations.append("❌ Baseline check failed")
                return self._create_result(name, False, start_time, observations, metrics)
            observations.append("✓ Baseline OK")
            
            # Phase 2: Inject chaos
            observations.append(f"Phase 2: Injecting chaos ({chaos_type})")
            try:
                async with self.chaos.inject(chaos_type, force=True):
                    metrics["chaos_injected"] = True
                    
                    # Phase 3: Execute operation under chaos
                    observations.append("Phase 3: Executing operation under chaos")
                    try:
                        await operation()
                        metrics["operation_succeeded"] = True
                        observations.append("✓ Operation completed (may or may not be expected)")
                    except Exception as e:
                        observations.append(f"✓ Operation failed as expected: {type(e).__name__}")
            except Exception as e:
                observations.append(f"Chaos injection caused exception: {e}")
            
            # Phase 4: Wait for recovery
            observations.append(f"Phase 4: Waiting for recovery ({recovery_time_seconds}s)")
            await asyncio.sleep(recovery_time_seconds)
            
            # Phase 5: Validate recovery
            observations.append("Phase 5: Validating recovery")
            recovery_start = time.time()
            recovered = await validate()
            metrics["recovery_time_ms"] = (time.time() - recovery_start) * 1000
            metrics["recovered"] = recovered
            
            if recovered:
                observations.append("✓ System recovered successfully")
            else:
                observations.append("❌ System failed to recover")
            
            passed = recovered  # Test passes if system recovered
            
        except Exception as e:
            observations.append(f"❌ Unexpected error: {e}")
            passed = False
        
        return self._create_result(name, passed, start_time, observations, metrics)
    
    def _create_result(
        self,
        name: str,
        passed: bool,
        start_time: float,
        observations: List[str],
        metrics: Dict[str, Any]
    ) -> ChaosTestResult:
        """Create a test result."""
        result = ChaosTestResult(
            scenario_name=name,
            passed=passed,
            duration_ms=(time.time() - start_time) * 1000,
            observations=observations,
            metrics=metrics
        )
        self.results.append(result)
        return result
    
    def get_report(self) -> Dict[str, Any]:
        """Generate a test report."""
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        
        return {
            "summary": {
                "total": len(self.results),
                "passed": passed,
                "failed": failed,
                "pass_rate": passed / len(self.results) * 100 if self.results else 0
            },
            "scenarios": [
                {
                    "name": r.scenario_name,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                    "observations": r.observations,
                    "metrics": r.metrics
                }
                for r in self.results
            ],
            "chaos_stats": self.chaos.get_statistics()
        }


# ============================================================================
# Pytest Test Cases
# ============================================================================

@pytest.fixture
def chaos_engine():
    """Create a chaos engine for testing."""
    engine = ChaosEngine(ChaosConfig(
        enabled=True,
        dry_run=False,
        probability=1.0,
        allowed_environments={"test"}
    ))
    engine.set_environment("test")
    return engine


class TestLatencyInjection:
    """Tests for latency injection."""
    
    @pytest.mark.asyncio
    async def test_uniform_latency(self, chaos_engine):
        """Test uniform latency distribution."""
        chaos_engine.register_experiment(
            "test_latency",
            LatencyExperiment(min_ms=100, max_ms=200, distribution="uniform")
        )
        
        start = time.time()
        async with chaos_engine.inject("test_latency", force=True):
            pass
        elapsed = (time.time() - start) * 1000
        
        assert 100 <= elapsed <= 250  # Allow some margin
    
    @pytest.mark.asyncio
    async def test_exponential_latency(self, chaos_engine):
        """Test exponential latency distribution."""
        chaos_engine.register_experiment(
            "exp_latency",
            LatencyExperiment(min_ms=50, max_ms=1000, distribution="exponential")
        )
        
        durations = []
        for _ in range(10):
            start = time.time()
            async with chaos_engine.inject("exp_latency", force=True):
                pass
            durations.append((time.time() - start) * 1000)
        
        # Most should be on the lower end with exponential
        median = sorted(durations)[5]
        assert median < 500  # Median should be in lower half


class TestFailureInjection:
    """Tests for failure injection."""
    
    @pytest.mark.asyncio
    async def test_exception_injection(self, chaos_engine):
        """Test that exceptions are properly injected."""
        chaos_engine.register_experiment(
            "test_failure",
            FailureExperiment(
                exception_class=ValueError,
                message="Chaos test failure"
            )
        )
        
        with pytest.raises(ValueError, match="Chaos test failure"):
            async with chaos_engine.inject("test_failure", force=True):
                pass
    
    @pytest.mark.asyncio
    async def test_partial_failure_rate(self, chaos_engine):
        """Test partial failure rate."""
        chaos_engine.register_experiment(
            "partial_failure",
            FailureExperiment(failure_rate=0.5)
        )
        
        failures = 0
        attempts = 20
        
        for _ in range(attempts):
            try:
                async with chaos_engine.inject("partial_failure", force=True):
                    pass
            except Exception:
                failures += 1
        
        # Should be roughly 50% failures (allow variance)
        assert 5 <= failures <= 15


class TestChaosEngineControls:
    """Tests for chaos engine control mechanisms."""
    
    @pytest.mark.asyncio
    async def test_dry_run_mode(self):
        """Test that dry run mode doesn't inject chaos."""
        engine = ChaosEngine(ChaosConfig(
            enabled=True,
            dry_run=True,
            probability=1.0,
            allowed_environments={"test"}
        ))
        engine.set_environment("test")
        engine.register_experiment("failure", FailureExperiment())
        
        # Should not raise because dry run
        async with engine.inject("failure", force=True):
            pass
    
    @pytest.mark.asyncio
    async def test_environment_restriction(self):
        """Test that chaos is blocked in production."""
        engine = ChaosEngine(ChaosConfig(
            enabled=True,
            dry_run=False,
            probability=1.0,
            allowed_environments={"test", "staging"}
        ))
        engine.set_environment("production")
        engine.register_experiment("failure", FailureExperiment())
        
        # Should not inject because we're in "production"
        async with engine.inject("failure"):
            pass  # No exception because environment blocked
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self, chaos_engine):
        """Test circuit breaker activates after failures."""
        chaos_engine.config.circuit_breaker_threshold = 3
        chaos_engine.register_experiment("always_fail", FailureExperiment())
        
        # Trigger failures
        for _ in range(5):
            try:
                async with chaos_engine.inject("always_fail", force=True):
                    pass
            except Exception:
                pass
        
        assert chaos_engine.consecutive_failures >= 3
        
        # Circuit breaker should prevent more injections
        # (unless force=True)
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, chaos_engine):
        """Test that statistics are properly tracked."""
        chaos_engine.register_experiment(
            "tracked",
            LatencyExperiment(min_ms=10, max_ms=20)
        )
        
        for _ in range(5):
            async with chaos_engine.inject("tracked", force=True):
                pass
        
        stats = chaos_engine.get_statistics()
        
        assert stats["total_experiments"] == 5
        assert stats["injected_count"] == 5
        assert "tracked" in stats["registered_experiments"]


class TestResourceExhaustion:
    """Tests for resource exhaustion experiments."""
    
    @pytest.mark.asyncio
    async def test_memory_pressure(self, chaos_engine):
        """Test memory pressure experiment."""
        chaos_engine.register_experiment(
            "memory",
            ResourceExhaustionExperiment(
                resource_type="memory",
                intensity=0.1,  # Light pressure
                duration_seconds=0.5
            )
        )
        
        import gc
        gc.collect()
        
        async with chaos_engine.inject("memory", force=True):
            pass
        
        # Memory should be freed after cleanup
        gc.collect()


class TestChaosDecorator:
    """Tests for chaos decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_injection(self, chaos_engine):
        """Test chaos decorator works."""
        chaos_engine.register_experiment(
            "dec_latency",
            LatencyExperiment(min_ms=50, max_ms=100)
        )
        
        @chaos_engine.chaos_decorator("dec_latency")
        async def slow_function():
            return "result"
        
        start = time.time()
        result = await slow_function()
        elapsed = (time.time() - start) * 1000
        
        assert result == "result"
        assert elapsed >= 50


# ============================================================================
# Scenario-Based Tests
# ============================================================================

class TestResilienceScenarios:
    """High-level resilience scenario tests."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_under_chaos(self):
        """Test that circuit breaker protects during chaos."""
        # Simulate a circuit breaker
        failure_count = 0
        circuit_open = False
        threshold = 3
        
        async def protected_operation():
            nonlocal failure_count, circuit_open
            
            if circuit_open:
                raise Exception("Circuit is open")
            
            # Simulate failure
            failure_count += 1
            if failure_count >= threshold:
                circuit_open = True
            raise Exception("Service unavailable")
        
        # Call until circuit opens
        for _ in range(5):
            try:
                await protected_operation()
            except Exception:
                pass
        
        assert circuit_open
        assert failure_count >= threshold
    
    @pytest.mark.asyncio
    async def test_retry_with_backoff(self):
        """Test retry mechanism with exponential backoff."""
        attempts = []
        
        async def flaky_operation():
            attempts.append(time.time())
            if len(attempts) < 3:
                raise Exception("Temporary failure")
            return "success"
        
        async def retry_with_backoff(operation, max_retries=5, base_delay=0.1):
            for attempt in range(max_retries):
                try:
                    return await operation()
                except Exception:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
            raise Exception("Max retries exceeded")
        
        result = await retry_with_backoff(flaky_operation)
        
        assert result == "success"
        assert len(attempts) == 3
        
        # Verify backoff timing
        if len(attempts) >= 2:
            gap1 = attempts[1] - attempts[0]
            assert gap1 >= 0.1  # First retry after 100ms
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling under slow operations."""
        async def slow_operation():
            await asyncio.sleep(5)
            return "completed"
        
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_operation(), timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation when primary service fails."""
        primary_healthy = False
        fallback_used = False
        
        async def get_data():
            nonlocal fallback_used
            
            if primary_healthy:
                return {"source": "primary", "data": "full"}
            else:
                fallback_used = True
                return {"source": "cache", "data": "stale"}
        
        result = await get_data()
        
        assert fallback_used
        assert result["source"] == "cache"


# ============================================================================
# CLI Runner
# ============================================================================

async def run_chaos_scenarios():
    """Run all chaos scenarios and generate report."""
    harness = ChaosTestHarness()
    
    # Define mock operations and validators
    async def mock_operation():
        await asyncio.sleep(0.1)
        return True
    
    async def mock_validate():
        return True
    
    # Run scenarios
    scenarios = [
        ("Light Latency", "light_latency"),
        ("Heavy Latency", "heavy_latency"),
        ("Random Failure", "random_failure"),
        ("Memory Pressure", "memory_pressure"),
    ]
    
    print("=" * 60)
    print("CHAOS ENGINEERING TEST SUITE")
    print("=" * 60)
    
    for name, chaos_type in scenarios:
        print(f"\nRunning scenario: {name}")
        result = await harness.run_scenario(
            name=name,
            chaos_type=chaos_type,
            operation=mock_operation,
            validate=mock_validate,
            recovery_time_seconds=1.0
        )
        
        status = "✓ PASSED" if result.passed else "✗ FAILED"
        print(f"  {status} ({result.duration_ms:.0f}ms)")
        for obs in result.observations:
            print(f"    {obs}")
    
    # Print summary
    report = harness.get_report()
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total: {report['summary']['total']}")
    print(f"Passed: {report['summary']['passed']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"Pass Rate: {report['summary']['pass_rate']:.1f}%")
    
    return report


if __name__ == "__main__":
    asyncio.run(run_chaos_scenarios())
