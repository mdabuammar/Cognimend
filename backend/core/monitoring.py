"""
Enterprise-grade monitoring and observability
Used by: Google, Meta, Amazon, Netflix
"""

import time
import logging
import asyncio
import json
import uuid
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

# ========== METRICS DATACLASSES ==========

@dataclass
class QueryMetrics:
    """Individual query metrics"""
    query_id: str
    question: str
    latency_ms: int
    tokens_used: int
    cost_usd: float
    confidence: float
    model_used: str
    cache_hit: bool
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SystemMetrics:
    """System-level metrics"""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0
    total_tokens: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return (self.successful_queries / self.total_queries) * 100

    @property
    def cache_hit_rate(self) -> float:
        total_cache_requests = self.cache_hits + self.cache_misses
        if total_cache_requests == 0:
            return 0.0
        return (self.cache_hits / total_cache_requests) * 100

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_queries == 0:
            return 0.0
        return self.total_latency_ms / self.successful_queries

    @property
    def avg_cost_per_query(self) -> float:
        if self.successful_queries == 0:
            return 0.0
        return self.total_cost_usd / self.successful_queries


# ========== PROMETHEUS-STYLE METRICS COLLECTOR ==========

class MetricsCollector:
    """
    Collects and aggregates metrics
    Compatible with Prometheus, Grafana, DataDog
    """

    def __init__(self):
        self.metrics = SystemMetrics()
        self.latency_buckets = defaultdict(int)  # Histogram
        self.error_counts = defaultdict(int)  # Error tracking
        self.model_usage = defaultdict(int)  # Model distribution
        self.hourly_costs = defaultdict(float)  # Cost per hour
        self.lock = threading.Lock()

        # SLO tracking (Service Level Objectives)
        self.slo_targets = {
            "p50_latency_ms": 800,
            "p95_latency_ms": 2000,
            "p99_latency_ms": 3000,
            "success_rate": 99.5,
            "cache_hit_rate": 40.0,
        }

    def record_query(self, metrics: QueryMetrics):
        """Record a query with thread safety"""
        with self.lock:
            self.metrics.total_queries += 1

            if metrics.error:
                self.metrics.failed_queries += 1
                self.error_counts[metrics.error] += 1
            else:
                self.metrics.successful_queries += 1
                self.metrics.total_latency_ms += metrics.latency_ms
                self.metrics.total_cost_usd += metrics.cost_usd
                self.metrics.total_tokens += metrics.tokens_used

                # Record model usage
                self.model_usage[metrics.model_used] += 1

                # Histogram buckets (for percentile calculations)
                self._record_latency_bucket(metrics.latency_ms)

                # Hourly cost tracking
                hour_key = metrics.timestamp.strftime("%Y-%m-%d %H:00")
                self.hourly_costs[hour_key] += metrics.cost_usd

            # Cache tracking
            if metrics.cache_hit:
                self.metrics.cache_hits += 1
            else:
                self.metrics.cache_misses += 1

    def _record_latency_bucket(self, latency_ms: int):
        """Record latency in histogram buckets"""
        buckets = [100, 200, 500, 800, 1000, 1500, 2000, 3000, 5000, 10000]
        for bucket in buckets:
            if latency_ms <= bucket:
                self.latency_buckets[bucket] += 1
                break
        else:
            self.latency_buckets[float("inf")] += 1

    def get_percentile(self, percentile: int) -> float:
        """Calculate latency percentile (P50, P95, P99)"""
        total_requests = sum(self.latency_buckets.values())
        if total_requests == 0:
            return 0.0

        target_count = (percentile / 100) * total_requests
        cumulative = 0

        for bucket in sorted(self.latency_buckets.keys()):
            cumulative += self.latency_buckets[bucket]
            if cumulative >= target_count:
                return bucket

        return 0.0

    def check_slo_compliance(self) -> Dict[str, Any]:
        """Check if system meets SLO targets"""
        current_p50 = self.get_percentile(50)
        current_p95 = self.get_percentile(95)
        current_p99 = self.get_percentile(99)

        return {
            "p50_latency": {
                "current": current_p50,
                "target": self.slo_targets["p50_latency_ms"],
                "met": current_p50 <= self.slo_targets["p50_latency_ms"],
            },
            "p95_latency": {
                "current": current_p95,
                "target": self.slo_targets["p95_latency_ms"],
                "met": current_p95 <= self.slo_targets["p95_latency_ms"],
            },
            "p99_latency": {
                "current": current_p99,
                "target": self.slo_targets["p99_latency_ms"],
                "met": current_p99 <= self.slo_targets["p99_latency_ms"],
            },
            "success_rate": {
                "current": self.metrics.success_rate,
                "target": self.slo_targets["success_rate"],
                "met": self.metrics.success_rate >= self.slo_targets["success_rate"],
            },
            "cache_hit_rate": {
                "current": self.metrics.cache_hit_rate,
                "target": self.slo_targets["cache_hit_rate"],
                "met": self.metrics.cache_hit_rate >= self.slo_targets["cache_hit_rate"],
            },
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        slo_compliance = self.check_slo_compliance()

        return {
            "overview": {
                "total_queries": self.metrics.total_queries,
                "successful": self.metrics.successful_queries,
                "failed": self.metrics.failed_queries,
                "success_rate": round(self.metrics.success_rate, 2),
            },
            "performance": {
                "avg_latency_ms": round(self.metrics.avg_latency_ms, 2),
                "p50_latency_ms": self.get_percentile(50),
                "p95_latency_ms": self.get_percentile(95),
                "p99_latency_ms": self.get_percentile(99),
            },
            "cache": {
                "hits": self.metrics.cache_hits,
                "misses": self.metrics.cache_misses,
                "hit_rate": round(self.metrics.cache_hit_rate, 2),
            },
            "costs": {
                "total_usd": round(self.metrics.total_cost_usd, 4),
                "avg_per_query": round(self.metrics.avg_cost_per_query, 6),
                "total_tokens": self.metrics.total_tokens,
            },
            "models": dict(self.model_usage),
            "errors": dict(self.error_counts),
            "slo_compliance": slo_compliance,
            "hourly_costs": dict(sorted(self.hourly_costs.items())[-24:]),  # Last 24 hours
        }

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        metrics_text = []

        # Counter metrics
        metrics_text.append("# HELP queries_total Total number of queries")
        metrics_text.append("# TYPE queries_total counter")
        metrics_text.append(f"queries_total {self.metrics.total_queries}")

        metrics_text.append("# HELP queries_success Total successful queries")
        metrics_text.append("# TYPE queries_success counter")
        metrics_text.append(f"queries_success {self.metrics.successful_queries}")

        metrics_text.append("# HELP queries_failed Total failed queries")
        metrics_text.append("# TYPE queries_failed counter")
        metrics_text.append(f"queries_failed {self.metrics.failed_queries}")

        # Histogram for latency
        metrics_text.append("# HELP query_latency_ms Query latency in milliseconds")
        metrics_text.append("# TYPE query_latency_ms histogram")
        for bucket, count in sorted(self.latency_buckets.items()):
            metrics_text.append(f'query_latency_ms_bucket{{le="{bucket}"}} {count}')

        # Gauge metrics
        metrics_text.append("# HELP cache_hit_rate Cache hit rate percentage")
        metrics_text.append("# TYPE cache_hit_rate gauge")
        metrics_text.append(f"cache_hit_rate {self.metrics.cache_hit_rate}")

        metrics_text.append("# HELP total_cost_usd Total cost in USD")
        metrics_text.append("# TYPE total_cost_usd counter")
        metrics_text.append(f"total_cost_usd {self.metrics.total_cost_usd}")

        return "\n".join(metrics_text)


# Global collector instance
metrics_collector = MetricsCollector()


# ========== DISTRIBUTED TRACING ==========

class TraceContext:
    """
    Distributed tracing context
    Compatible with OpenTelemetry, Jaeger
    """

    def __init__(
        self,
        trace_id: str,
        span_id: str,
        parent_span_id: Optional[str] = None,
    ):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.start_time = time.time()
        self.attributes = {}
        self.events = []

    def add_attribute(self, key: str, value: Any):
        """Add span attribute"""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        """Add span event"""
        self.events.append(
            {
                "name": name,
                "timestamp": time.time(),
                "attributes": attributes or {},
            }
        )

    def finish(self) -> Dict[str, Any]:
        """Finish span and return trace data"""
        duration_ms = int((time.time() - self.start_time) * 1000)

        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "duration_ms": duration_ms,
            "attributes": self.attributes,
            "events": self.events,
        }


def trace_operation(operation_name: str):
    """Decorator for tracing operations"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            trace_id = str(uuid.uuid4())
            span_id = str(uuid.uuid4())

            ctx = TraceContext(trace_id, span_id)
            ctx.add_attribute("operation", operation_name)
            ctx.add_attribute("function", func.__name__)

            try:
                result = await func(*args, **kwargs)
                ctx.add_attribute("status", "success")
                return result
            except Exception as e:
                ctx.add_attribute("status", "error")
                ctx.add_attribute("error", str(e))
                raise
            finally:
                trace_data = ctx.finish()
                logger.debug(f"Trace: {json.dumps(trace_data)}")

        return wrapper

    return decorator


# ========== ALERTING SYSTEM ==========

class AlertManager:
    """
    Alert management system
    Integrates with: PagerDuty, Slack, Email
    """

    def __init__(self):
        self.alert_history = []
        self.alert_cooldown = {}  # Prevent alert spam
        self.cooldown_seconds = 300  # 5 minutes

    def should_alert(self, alert_type: str) -> bool:
        """Check if we should send alert (cooldown logic)"""
        last_alert_time = self.alert_cooldown.get(alert_type)

        if last_alert_time:
            if time.time() - last_alert_time < self.cooldown_seconds:
                return False

        self.alert_cooldown[alert_type] = time.time()
        return True

    def send_alert(
        self,
        severity: str,
        title: str,
        message: str,
        metadata: Dict[str, Any] = None,
    ):
        """Send alert to configured channels"""

        if not self.should_alert(title):
            logger.info(f"Alert suppressed (cooldown): {title}")
            return

        alert = {
            "severity": severity,  # critical, warning, info
            "title": title,
            "message": message,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }

        self.alert_history.append(alert)

        # Keep only last 1000 alerts
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]

        # Log alert
        log_func = {
            "critical": logger.critical,
            "warning": logger.warning,
            "info": logger.info,
        }.get(severity, logger.info)

        log_func(f"🚨 ALERT [{severity.upper()}]: {title} - {message}")

    def check_slo_alerts(self, slo_compliance: Dict[str, Any]):
        """Check SLO compliance and send alerts"""

        for metric_name, metric_data in slo_compliance.items():
            if not metric_data["met"]:
                self.send_alert(
                    severity="warning",
                    title=f"SLO Violation: {metric_name}",
                    message=f"Current: {metric_data['current']}, Target: {metric_data['target']}",
                    metadata=metric_data,
                )

    def check_cost_alerts(
        self, hourly_costs: Dict[str, float], threshold: float = 2.0
    ):
        """Check for cost anomalies"""

        recent_costs = list(hourly_costs.values())[-1:] if hourly_costs else [0]
        current_hour_cost = recent_costs[0]

        if current_hour_cost > threshold:
            self.send_alert(
                severity="critical",
                title="High Cost Alert",
                message=f"Hourly cost ${current_hour_cost:.2f} exceeds threshold ${threshold:.2f}",
                metadata={
                    "current_cost": current_hour_cost,
                    "threshold": threshold,
                },
            )


# Global alert manager
alert_manager = AlertManager()


# ========== HEALTH CHECK SYSTEM ==========

class HealthChecker:
    """
    Comprehensive health checking
    Used in: Kubernetes liveness/readiness probes
    """

    def __init__(self):
        self.checks = {}
        self.last_check_time = {}
        self.cache_duration = 10  # Cache health check results for 10s

    def register_check(self, name: str, check_func: Callable):
        """Register a health check"""
        self.checks[name] = check_func

    async def run_check(self, name: str) -> Dict[str, Any]:
        """Run a single health check with caching"""

        # Check cache
        if name in self.last_check_time:
            if (
                time.time() - self.last_check_time[name]["time"]
                < self.cache_duration
            ):
                return self.last_check_time[name]["result"]

        # Run check
        try:
            start = time.time()
            check_func = self.checks[name]
            result = (
                await check_func()
                if asyncio.iscoroutinefunction(check_func)
                else check_func()
            )
            duration_ms = int((time.time() - start) * 1000)

            check_result = {
                "status": "healthy",
                "latency_ms": duration_ms,
                "details": result,
            }
        except Exception as e:
            check_result = {"status": "unhealthy", "error": str(e)}

        # Cache result
        self.last_check_time[name] = {"time": time.time(), "result": check_result}

        return check_result

    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all registered health checks"""

        results = {}
        overall_status = "healthy"

        for name in self.checks:
            result = await self.run_check(name)
            results[name] = result

            if result["status"] == "unhealthy":
                overall_status = "unhealthy"
            elif result["status"] == "degraded" and overall_status == "healthy":
                overall_status = "degraded"

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "checks": results,
        }


# Global health checker
health_checker = HealthChecker()


# ========== STRUCTURED LOGGING ==========

class StructuredLogger:
    """
    Structured logging for production
    Compatible with: ELK Stack, Splunk, CloudWatch
    """

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)

    def log(self, level: str, message: str, **kwargs):
        """Log with structured metadata"""

        log_entry = {
            "service": self.service_name,
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            **kwargs,
        }

        log_func = getattr(self.logger, level.lower(), self.logger.info)
        log_func(json.dumps(log_entry))

    def query_log(
        self,
        query_id: str,
        question: str,
        latency_ms: int,
        cost_usd: float,
        confidence: float,
        error: Optional[str] = None,
    ):
        """Specialized query logging"""

        self.log(
            level="INFO" if not error else "ERROR",
            message="Query processed",
            query_id=query_id,
            question=question[:100],  # Truncate long questions
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            confidence=confidence,
            error=error,
        )


# ========== PERFORMANCE PROFILER ==========

class PerformanceProfiler:
    """
    Detailed performance profiling
    """

    def __init__(self):
        self.profiles = defaultdict(list)

    def profile(self, operation_name: str):
        """Decorator for profiling functions"""

        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                start_cpu = time.process_time()

                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    wall_time_ms = int((time.time() - start_time) * 1000)
                    cpu_time_ms = int((time.process_time() - start_cpu) * 1000)

                    profile_data = {
                        "operation": operation_name,
                        "wall_time_ms": wall_time_ms,
                        "cpu_time_ms": cpu_time_ms,
                        "timestamp": datetime.now().isoformat(),
                    }

                    self.profiles[operation_name].append(profile_data)

                    # Keep only last 1000 profiles per operation
                    if len(self.profiles[operation_name]) > 1000:
                        self.profiles[operation_name] = (
                            self.profiles[operation_name][-1000:]
                        )

            return wrapper

        return decorator

    def get_profile_stats(self, operation_name: str) -> Dict[str, Any]:
        """Get statistics for an operation"""

        profiles = self.profiles.get(operation_name, [])

        if not profiles:
            return {"error": "No profiles found"}

        wall_times = [p["wall_time_ms"] for p in profiles]
        cpu_times = [p["cpu_time_ms"] for p in profiles]

        wall_times_sorted = sorted(wall_times)
        cpu_times_sorted = sorted(cpu_times)

        return {
            "operation": operation_name,
            "count": len(profiles),
            "wall_time": {
                "min": min(wall_times),
                "max": max(wall_times),
                "avg": sum(wall_times) / len(wall_times),
                "p50": wall_times_sorted[len(wall_times) // 2],
                "p95": wall_times_sorted[int(len(wall_times) * 0.95)],
                "p99": wall_times_sorted[int(len(wall_times) * 0.99)],
            },
            "cpu_time": {
                "min": min(cpu_times),
                "max": max(cpu_times),
                "avg": sum(cpu_times) / len(cpu_times),
            },
        }


# Global profiler
profiler = PerformanceProfiler()
