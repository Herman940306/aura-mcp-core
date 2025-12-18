"""OpenTelemetry tracing initialization (optional).

Activated when environment variable OTEL_ENABLED in {"1","true","yes"}.
Exports spans to OTLP endpoint if OTEL_EXPORTER_OTLP_ENDPOINT set; otherwise
uses in-memory (no-op) exporter.

Supports both gRPC (port 4317) and HTTP (port 4318) protocols based on
OTEL_EXPORTER_OTLP_PROTOCOL environment variable.
"""

from __future__ import annotations

import logging
import os
from typing import Any

# OpenTelemetry tracing initialization (optional).

logger = logging.getLogger("ide_agents.tracing")

# Track if tracing was initialized
_tracing_initialized = False


def is_tracing_enabled() -> bool:
    """Check if OpenTelemetry tracing is enabled."""
    flag = os.getenv("OTEL_ENABLED", "").lower()
    return flag in {"1", "true", "yes"}


def init_tracing(service_name: str = "ide-agents-mcp") -> bool:
    """Initialize OpenTelemetry tracing.

    Returns True if tracing was successfully initialized.
    """
    global _tracing_initialized

    flag = os.getenv("OTEL_ENABLED", "").lower()
    if flag not in {"1", "true", "yes"}:
        logger.info(
            "OpenTelemetry disabled (OTEL_ENABLED=%s)", flag or "unset"
        )
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )

        # Get service name from env or use default
        service_name = os.getenv("OTEL_SERVICE_NAME", service_name)
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc").lower()

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        span_exporter = None

        if endpoint:
            try:
                if protocol == "grpc":
                    # gRPC exporter (Jaeger port 4317)
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: E501
                        OTLPSpanExporter as GrpcOTLPSpanExporter,
                    )

                    span_exporter = GrpcOTLPSpanExporter(
                        endpoint=endpoint,
                        insecure=True,
                    )
                    logger.info(
                        "Using gRPC OTLP exporter: %s -> %s",
                        service_name,
                        endpoint,
                    )
                else:
                    # HTTP exporter (Jaeger port 4318)
                    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: E501
                        OTLPSpanExporter as HttpOTLPSpanExporter,
                    )

                    # HTTP endpoint needs /v1/traces path
                    http_endpoint = endpoint
                    if not http_endpoint.endswith("/v1/traces"):
                        http_endpoint = f"{endpoint.rstrip('/')}/v1/traces"
                    span_exporter = HttpOTLPSpanExporter(
                        endpoint=http_endpoint
                    )
                    logger.info(
                        "Using HTTP OTLP exporter: %s -> %s",
                        service_name,
                        http_endpoint,
                    )
            except (ImportError, OSError, ValueError) as exc:
                logger.warning(
                    "OTLP exporter init failed (%s), fallback to console",
                    exc,
                )

        if span_exporter is None:
            span_exporter = ConsoleSpanExporter()
            logger.info("Using ConsoleSpanExporter (no OTLP endpoint)")

        processor = BatchSpanProcessor(span_exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        _tracing_initialized = True
        logger.info(
            "OpenTelemetry tracing initialized: service=%s, endpoint=%s, protocol=%s",
            service_name,
            endpoint or "console",
            protocol,
        )
        return True
    except (ImportError, OSError, ValueError) as exc:
        logger.warning("Tracing initialization failed: %s", exc)
        return False


def instrument_fastapi(app: Any) -> bool:
    """Instrument a FastAPI/Starlette application with OpenTelemetry.

    Call this AFTER init_tracing() to add automatic span creation for HTTP requests.
    Works with both FastAPI and Starlette applications.

    Returns True if instrumentation was successful.
    """
    if not _tracing_initialized:
        logger.debug(
            "Skipping FastAPI instrumentation (tracing not initialized)"
        )
        return False

    # Exclude health check endpoints from tracing to reduce noise
    excluded_urls = "health,healthz,readyz,metrics,favicon.ico"

    # Try FastAPI first
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls=excluded_urls)
        logger.info("FastAPI instrumented with OpenTelemetry")
        return True
    except (ImportError, Exception) as exc:
        logger.debug("FastAPI instrumentation failed: %s", exc)

    # Try Starlette
    try:
        from opentelemetry.instrumentation.starlette import (
            StarletteInstrumentor,
        )

        StarletteInstrumentor.instrument_app(app, excluded_urls=excluded_urls)
        logger.info("Starlette instrumented with OpenTelemetry")
        return True
    except ImportError as exc:
        logger.warning("Starlette instrumentation not available: %s", exc)
        return False
    except Exception as exc:
        logger.warning("Starlette instrumentation failed: %s", exc)
        return False


def instrument_httpx() -> bool:
    """Instrument httpx client with OpenTelemetry for outgoing HTTP calls.

    Returns True if instrumentation was successful.
    """
    if not _tracing_initialized:
        logger.debug(
            "Skipping httpx instrumentation (tracing not initialized)"
        )
        return False

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("httpx instrumented with OpenTelemetry")
        return True
    except ImportError as exc:
        logger.warning("httpx instrumentation not available: %s", exc)
        return False
    except Exception as exc:
        logger.warning("httpx instrumentation failed: %s", exc)
        return False


__all__ = [
    "init_tracing",
    "instrument_fastapi",
    "instrument_httpx",
    "is_tracing_enabled",
]
