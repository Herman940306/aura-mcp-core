from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from src.mcp_server.metrics import performance_summary, prometheus_exposition

from .core.config import Settings, get_settings
from .core.health import register_health_endpoints
from .core.logging_setup import setup_logging
from .core.middleware import AuditMiddleware
from .services.gateway import register_service_routes
from .training import routes as training_routes


def create_app() -> FastAPI:
    settings: Settings = get_settings()
    setup_logging(settings)
    app = FastAPI(title="Aura IA MCP", version="0.0.1")
    
    # Add CORS middleware FIRST (before other middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for dashboard access
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    app.add_middleware(AuditMiddleware)
    register_health_endpoints(app)

    # Register core service routes (dependencies gate behavior)
    register_service_routes(app, settings)

    # Register training routes (gated by SAFE_MODE and ENABLE_TRAINING)
    app.include_router(training_routes.training_router)

    # Register role mutation routes (gated by SAFE_MODE and ENABLE_ROLE_MUTATION)
    from .ops.role_engine.mutation_routes import role_mutation_router
    from .ops.role_engine.policy_routes import register_policy_routes

    app.include_router(role_mutation_router)
    register_policy_routes(app)

    @app.get("/metrics", summary="Prometheus metrics", tags=["observability"])
    def metrics_endpoint() -> Response:  # noqa: D401
        data = prometheus_exposition()
        return Response(content=data, media_type="text/plain; version=0.0.4")

    @app.get(
        "/performance",
        summary="Derived performance summary",
        tags=["observability"],
    )
    def performance_endpoint() -> dict:  # noqa: D401
        return performance_summary()

    # OpenTelemetry Instrumentation (conditional based on OTEL_ENABLED)
    import os

    otel_enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"

    if otel_enabled:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.instrumentation.fastapi import (
                FastAPIInstrumentor,
            )
            from opentelemetry.sdk.resources import SERVICE_NAME, Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            # Get config from environment
            service_name = os.getenv("OTEL_SERVICE_NAME", "aura-ia-gateway")
            otlp_endpoint = os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
            )

            # Configure Tracing
            resource = Resource.create(attributes={SERVICE_NAME: service_name})
            trace.set_tracer_provider(TracerProvider(resource=resource))
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint, insecure=True
            )
            span_processor = BatchSpanProcessor(otlp_exporter)
            trace.get_tracer_provider().add_span_processor(span_processor)

            # Instrument FastAPI
            FastAPIInstrumentor.instrument_app(
                app, excluded_urls="health,healthz,readyz,metrics"
            )

            import logging

            logging.getLogger(__name__).info(
                f"OpenTelemetry enabled: {service_name} -> {otlp_endpoint}"
            )
        except ImportError as e:
            import logging

            logging.getLogger(__name__).warning(
                f"OpenTelemetry not available: {e}"
            )
    else:
        import logging

        logging.getLogger(__name__).info(
            "OpenTelemetry disabled (OTEL_ENABLED != true)"
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("aura_ia_mcp.main:app", host="0.0.0.0", port=9200, reload=True)
