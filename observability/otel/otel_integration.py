"""
OpenTelemetry Integration for Aura IA MCP.

Provides comprehensive distributed tracing, metrics export,
and instrumentation for all Aura IA services.
"""

from __future__ import annotations

import functools
import logging
import os
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

# Type imports for stubs (when opentelemetry not installed)
try:
    from opentelemetry import baggage, metrics, trace
    from opentelemetry.context import Context
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.exporter.prometheus import PrometheusMetricReader
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.propagate import set_global_textmap
    from opentelemetry.propagators.b3 import B3MultiFormat
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import (
        SERVICE_NAME,
        SERVICE_VERSION,
        Resource,
    )
    from opentelemetry.sdk.trace import Span, TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    from opentelemetry.trace import SpanKind, Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    # Stub types for when OTEL is not installed
    Span = Any  # type: ignore
    Context = Any  # type: ignore

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class SpanAttribute(Enum):
    """Standard span attribute keys for Aura IA."""

    SERVICE = "aura.service"
    OPERATION = "aura.operation"
    USER_ID = "aura.user_id"
    SESSION_ID = "aura.session_id"
    ROLE = "aura.role"
    RISK_LEVEL = "aura.risk_level"
    TOOL_NAME = "aura.tool_name"
    MODEL_NAME = "aura.model_name"
    QUERY_TYPE = "aura.query_type"
    RESULT_COUNT = "aura.result_count"
    TOKEN_COUNT = "aura.token_count"
    APPROVAL_STATUS = "aura.approval_status"


@dataclass
class TelemetryConfig:
    """Configuration for OpenTelemetry integration."""

    service_name: str = "aura-ia-gateway"
    service_version: str = "1.0.0"
    environment: str = "development"
    otlp_endpoint: str = "http://localhost:4317"
    enable_tracing: bool = True
    enable_metrics: bool = True
    enable_logging: bool = True
    sample_rate: float = 1.0  # 100% sampling by default
    export_interval_ms: int = 5000
    max_export_batch_size: int = 512
    enable_console_export: bool = False
    prometheus_port: int = 9464
    propagators: list[str] = field(
        default_factory=lambda: ["tracecontext", "b3"]
    )

    @classmethod
    def from_env(cls) -> TelemetryConfig:
        """Create config from environment variables."""
        return cls(
            service_name=os.getenv("OTEL_SERVICE_NAME", "aura-ia-gateway"),
            service_version=os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("ENVIRONMENT", "development"),
            otlp_endpoint=os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
            ),
            enable_tracing=os.getenv("OTEL_TRACING_ENABLED", "true").lower()
            == "true",
            enable_metrics=os.getenv("OTEL_METRICS_ENABLED", "true").lower()
            == "true",
            enable_logging=os.getenv("OTEL_LOGGING_ENABLED", "true").lower()
            == "true",
            sample_rate=float(os.getenv("OTEL_SAMPLE_RATE", "1.0")),
            export_interval_ms=int(
                os.getenv("OTEL_EXPORT_INTERVAL_MS", "5000")
            ),
            prometheus_port=int(os.getenv("OTEL_PROMETHEUS_PORT", "9464")),
        )


class AuraTelemetry:
    """
    Central telemetry manager for Aura IA MCP.

    Provides:
    - Distributed tracing with OpenTelemetry
    - Metrics export to Prometheus
    - Structured logging with trace correlation
    - Automatic instrumentation for FastAPI, HTTPX, etc.
    """

    _instance: AuraTelemetry | None = None

    def __new__(cls, config: TelemetryConfig | None = None) -> AuraTelemetry:
        """Singleton pattern for telemetry manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: TelemetryConfig | None = None):
        if self._initialized:  # type: ignore
            return

        self.config = config or TelemetryConfig.from_env()
        self._tracer: Any | None = None
        self._meter: Any | None = None
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._gauges: dict[str, Any] = {}
        self._initialized = True

        if OTEL_AVAILABLE:
            self._setup_telemetry()
        else:
            logger.warning(
                "OpenTelemetry packages not installed. "
                "Run: pip install opentelemetry-api opentelemetry-sdk "
                "opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi"
            )

    def _setup_telemetry(self) -> None:
        """Initialize OpenTelemetry components."""
        if not OTEL_AVAILABLE:
            return

        # Create resource
        resource = Resource.create(
            {
                SERVICE_NAME: self.config.service_name,
                SERVICE_VERSION: self.config.service_version,
                "deployment.environment": self.config.environment,
                "service.namespace": "aura-ia",
            }
        )

        # Setup tracing
        if self.config.enable_tracing:
            self._setup_tracing(resource)

        # Setup metrics
        if self.config.enable_metrics:
            self._setup_metrics(resource)

        # Setup logging instrumentation
        if self.config.enable_logging:
            self._setup_logging()

        # Setup propagators
        self._setup_propagators()

        logger.info(
            f"Telemetry initialized for {self.config.service_name} "
            f"(tracing={self.config.enable_tracing}, metrics={self.config.enable_metrics})"
        )

    def _setup_tracing(self, resource: Any) -> None:
        """Setup distributed tracing."""
        # Create sampler
        sampler = TraceIdRatioBased(self.config.sample_rate)

        # Create tracer provider
        provider = TracerProvider(resource=resource, sampler=sampler)

        # Add OTLP exporter
        otlp_exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint)
        provider.add_span_processor(
            BatchSpanProcessor(
                otlp_exporter,
                max_export_batch_size=self.config.max_export_batch_size,
                schedule_delay_millis=self.config.export_interval_ms,
            )
        )

        # Optionally add console exporter for debugging
        if self.config.enable_console_export:
            provider.add_span_processor(
                BatchSpanProcessor(ConsoleSpanExporter())
            )

        # Set global tracer provider
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer(
            self.config.service_name, self.config.service_version
        )

    def _setup_metrics(self, resource: Any) -> None:
        """Setup metrics collection."""
        # Create metric readers
        readers = []

        # OTLP metric exporter
        otlp_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=self.config.otlp_endpoint),
            export_interval_millis=self.config.export_interval_ms,
        )
        readers.append(otlp_reader)

        # Prometheus metric reader
        prometheus_reader = PrometheusMetricReader()
        readers.append(prometheus_reader)

        # Create meter provider
        provider = MeterProvider(resource=resource, metric_readers=readers)
        metrics.set_meter_provider(provider)

        self._meter = metrics.get_meter(
            self.config.service_name, self.config.service_version
        )

        # Initialize standard metrics
        self._init_standard_metrics()

    def _init_standard_metrics(self) -> None:
        """Initialize standard Aura IA metrics."""
        if not self._meter:
            return

        # Request counters
        self._counters["requests"] = self._meter.create_counter(
            "aura_requests_total",
            description="Total number of requests",
            unit="1",
        )

        self._counters["errors"] = self._meter.create_counter(
            "aura_errors_total", description="Total number of errors", unit="1"
        )

        self._counters["tool_calls"] = self._meter.create_counter(
            "aura_tool_calls_total",
            description="Total tool invocations",
            unit="1",
        )

        self._counters["approvals"] = self._meter.create_counter(
            "aura_approvals_total",
            description="Total approval requests",
            unit="1",
        )

        # Histograms
        self._histograms["request_duration"] = self._meter.create_histogram(
            "aura_request_duration_seconds",
            description="Request duration in seconds",
            unit="s",
        )

        self._histograms["inference_duration"] = self._meter.create_histogram(
            "aura_inference_duration_seconds",
            description="ML inference duration in seconds",
            unit="s",
        )

        self._histograms["rag_query_duration"] = self._meter.create_histogram(
            "aura_rag_query_duration_seconds",
            description="RAG query duration in seconds",
            unit="s",
        )

        self._histograms["debate_duration"] = self._meter.create_histogram(
            "aura_debate_duration_seconds",
            description="Dual-model debate duration in seconds",
            unit="s",
        )

        # Gauges
        self._gauges["active_sessions"] = self._meter.create_up_down_counter(
            "aura_active_sessions",
            description="Number of active sessions",
            unit="1",
        )

        self._gauges["queue_depth"] = self._meter.create_up_down_counter(
            "aura_queue_depth", description="Current queue depth", unit="1"
        )

    def _setup_logging(self) -> None:
        """Setup logging instrumentation."""
        LoggingInstrumentor().instrument(set_logging_format=True)

    def _setup_propagators(self) -> None:
        """Setup context propagators."""
        # Use W3C TraceContext as primary, B3 as fallback
        set_global_textmap(TraceContextTextMapPropagator())

    def instrument_fastapi(self, app: Any) -> None:
        """Instrument a FastAPI application."""
        if not OTEL_AVAILABLE:
            logger.warning(
                "Cannot instrument FastAPI: OpenTelemetry not available"
            )
            return

        FastAPIInstrumentor.instrument_app(
            app, excluded_urls="health,healthz,readyz,metrics"
        )
        logger.info("FastAPI instrumentation enabled")

    def instrument_httpx(self) -> None:
        """Instrument HTTPX client."""
        if not OTEL_AVAILABLE:
            return

        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX instrumentation enabled")

    @contextmanager
    def start_span(
        self,
        name: str,
        kind: Any | None = None,
        attributes: dict[str, Any] | None = None,
        context: Any | None = None,
    ) -> Generator[Any, None, None]:
        """
        Start a new span.

        Usage:
            with telemetry.start_span("process_request", attributes={"user_id": "123"}):
                # ... do work ...
        """
        if not self._tracer:
            yield None
            return

        span_kind = kind if kind else SpanKind.INTERNAL
        with self._tracer.start_as_current_span(
            name, kind=span_kind, attributes=attributes, context=context
        ) as span:
            try:
                yield span
            except Exception as e:
                if span:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                raise

    def trace(
        self,
        name: str | None = None,
        kind: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Callable[[F], F]:
        """
        Decorator to trace a function.

        Usage:
            @telemetry.trace("process_data", attributes={"type": "batch"})
            def process_data(data):
                ...
        """

        def decorator(func: F) -> F:
            span_name = name or f"{func.__module__}.{func.__name__}"

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.start_span(
                    span_name, kind=kind, attributes=attributes
                ):
                    return func(*args, **kwargs)

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.start_span(
                    span_name, kind=kind, attributes=attributes
                ):
                    return await func(*args, **kwargs)

            if asyncio_iscoroutinefunction(func):
                return async_wrapper  # type: ignore
            return wrapper  # type: ignore

        return decorator

    def record_request(
        self,
        service: str,
        method: str,
        status: int,
        duration_seconds: float,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Record a request metric."""
        labels = {
            "service": service,
            "method": method,
            "status": str(status),
            **(attributes or {}),
        }

        if "requests" in self._counters:
            self._counters["requests"].add(1, labels)

        if status >= 400 and "errors" in self._counters:
            self._counters["errors"].add(1, labels)

        if "request_duration" in self._histograms:
            self._histograms["request_duration"].record(
                duration_seconds, labels
            )

    def record_tool_call(
        self,
        tool_name: str,
        success: bool,
        duration_seconds: float,
        role: str | None = None,
    ) -> None:
        """Record a tool invocation."""
        labels = {
            "tool": tool_name,
            "success": str(success).lower(),
            "role": role or "unknown",
        }

        if "tool_calls" in self._counters:
            self._counters["tool_calls"].add(1, labels)

    def record_inference(
        self,
        model: str,
        duration_seconds: float,
        token_count: int,
        success: bool,
    ) -> None:
        """Record an ML inference."""
        labels = {"model": model, "success": str(success).lower()}

        if "inference_duration" in self._histograms:
            self._histograms["inference_duration"].record(
                duration_seconds, labels
            )

    def record_rag_query(
        self, collection: str, duration_seconds: float, result_count: int
    ) -> None:
        """Record a RAG query."""
        labels = {"collection": collection}

        if "rag_query_duration" in self._histograms:
            self._histograms["rag_query_duration"].record(
                duration_seconds, labels
            )

    def record_debate(
        self, duration_seconds: float, rounds: int, consensus_reached: bool
    ) -> None:
        """Record a dual-model debate."""
        labels = {"consensus": str(consensus_reached).lower()}

        if "debate_duration" in self._histograms:
            self._histograms["debate_duration"].record(
                duration_seconds, labels
            )

    def record_approval(
        self, action_type: str, risk_level: str, status: str
    ) -> None:
        """Record an approval request."""
        labels = {
            "action_type": action_type,
            "risk_level": risk_level,
            "status": status,
        }

        if "approvals" in self._counters:
            self._counters["approvals"].add(1, labels)

    def get_current_span(self) -> Any | None:
        """Get the current active span."""
        if not OTEL_AVAILABLE:
            return None
        return trace.get_current_span()

    def add_span_attribute(self, key: str, value: Any) -> None:
        """Add an attribute to the current span."""
        span = self.get_current_span()
        if span:
            span.set_attribute(key, value)

    def add_span_event(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> None:
        """Add an event to the current span."""
        span = self.get_current_span()
        if span:
            span.add_event(name, attributes=attributes)

    def get_trace_id(self) -> str | None:
        """Get the current trace ID."""
        span = self.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().trace_id, "032x")
        return None


def asyncio_iscoroutinefunction(func: Any) -> bool:
    """Check if function is a coroutine function."""
    import asyncio

    return asyncio.iscoroutinefunction(func)


# Global telemetry instance
_telemetry: AuraTelemetry | None = None


def get_telemetry(config: TelemetryConfig | None = None) -> AuraTelemetry:
    """Get or create the global telemetry instance."""
    global _telemetry
    if _telemetry is None:
        _telemetry = AuraTelemetry(config)
    return _telemetry


def init_telemetry(
    service_name: str,
    service_version: str = "1.0.0",
    otlp_endpoint: str | None = None,
    **kwargs: Any,
) -> AuraTelemetry:
    """
    Initialize telemetry with custom configuration.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        otlp_endpoint: OpenTelemetry collector endpoint
        **kwargs: Additional TelemetryConfig options

    Returns:
        Configured AuraTelemetry instance
    """
    config = TelemetryConfig(
        service_name=service_name,
        service_version=service_version,
        otlp_endpoint=otlp_endpoint or "http://localhost:4317",
        **kwargs,
    )
    return get_telemetry(config)


# Convenience decorators
def trace_function(
    name: str | None = None, attributes: dict[str, Any] | None = None
) -> Callable[[F], F]:
    """Decorator to trace a function."""
    return get_telemetry().trace(name=name, attributes=attributes)


if __name__ == "__main__":
    # Example usage
    telemetry = init_telemetry(
        service_name="aura-ia-gateway",
        service_version="1.0.0",
        enable_console_export=True,
    )

    @telemetry.trace("example_operation")
    def example_function(x: int) -> int:
        with telemetry.start_span("inner_operation"):
            time.sleep(0.1)
            return x * 2

    # Run example
    result = example_function(21)
    print(f"Result: {result}")

    # Record some metrics
    telemetry.record_request("gateway", "POST", 200, 0.15)
    telemetry.record_tool_call("search_documents", True, 0.5, "analyst")
    telemetry.record_inference("gpt-4", 1.2, 150, True)

    print(f"Trace ID: {telemetry.get_trace_id()}")
