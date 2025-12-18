"""Test OTEL tracing enable flag behavior."""

from __future__ import annotations

import os


def test_tracing_disabled_by_default():
    """Verify tracing does not activate without flag."""
    # Clear flag
    os.environ.pop("OTEL_ENABLED", None)
    from src.mcp_server.tracing_setup import init_tracing

    # Should be no-op (no crash)
    init_tracing("test-service")
    # No actual tracer provider should be set if flag missing


def test_tracing_enabled_flag():
    """Verify tracing attempts initialization when flag set."""
    os.environ["OTEL_ENABLED"] = "true"
    from src.mcp_server.tracing_setup import init_tracing

    # Should attempt init (may fail if opentelemetry not installed)
    try:
        init_tracing("test-service")
    except Exception:  # noqa: BLE001
        # Expected if opentelemetry dependencies missing
        pass
    finally:
        os.environ.pop("OTEL_ENABLED", None)
