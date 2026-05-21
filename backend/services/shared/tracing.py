"""Distributed tracing with OpenTelemetry"""
import os
import logging
from typing import Optional
from opentelemetry import trace, metrics
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from fastapi import Request

logger = logging.getLogger(__name__)


def init_tracing(service_name: str):
    """Initialize OpenTelemetry tracing"""
    try:
        # Resource
        resource = Resource.create({
            "service.name": service_name,
            "environment": os.getenv("ENVIRONMENT", "development")
        })
        
        # Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=os.getenv("JAEGER_HOST", "localhost"),
            agent_port=int(os.getenv("JAEGER_PORT", 6831)),
        )
        
        # Tracer provider
        trace_provider = TracerProvider(resource=resource)
        trace_provider.add_span_processor(
            BatchSpanProcessor(jaeger_exporter)
        )
        trace.set_tracer_provider(trace_provider)
        
        # Auto-instrumentation
        FastAPIInstrumentor.instrument_app
        Psycopg2Instrumentor().instrument()
        RequestsInstrumentor().instrument()
        RedisInstrumentor().instrument()
        
        logger.info(f"Tracing initialized for {service_name}")
        return trace_provider
    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        logger.warning("Continuing without distributed tracing")
        return None


def get_tracer(name: str = "app"):
    """Get tracer instance"""
    return trace.get_tracer(name)


async def extract_trace_context(request: Request) -> dict:
    """Extract trace context from request headers"""
    return {
        "trace_id": request.headers.get("X-Trace-ID"),
        "span_id": request.headers.get("X-Span-ID"),
        "user_id": request.headers.get("X-User-ID"),
        "request_id": request.headers.get("X-Request-ID")
    }


def create_span_attributes(
    operation: str,
    service: str,
    **kwargs
) -> dict:
    """Create standard span attributes"""
    return {
        "operation": operation,
        "service": service,
        **kwargs
    }
