"""
Observability Package for Aura IA MCP.

Provides comprehensive observability capabilities:
- Prometheus metrics and configuration
- Grafana dashboard generation
- OpenTelemetry distributed tracing
- Loki log aggregation
"""

from observability.loki.loki_integration import (
    LogLevel,
    LokiConfig,
    LokiLogAggregator,
    StructuredLogger,
    get_aggregator,
    get_logger,
)
from observability.otel.otel_integration import (
    AuraTelemetry,
    SpanAttribute,
    TelemetryConfig,
    get_telemetry,
    init_telemetry,
    trace_function,
)

__all__ = [
    # OpenTelemetry
    "AuraTelemetry",
    "TelemetryConfig",
    "get_telemetry",
    "init_telemetry",
    "trace_function",
    "SpanAttribute",
    # Loki
    "LokiConfig",
    "LokiLogAggregator",
    "StructuredLogger",
    "get_logger",
    "get_aggregator",
    "LogLevel",
]
