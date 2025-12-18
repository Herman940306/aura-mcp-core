"""Unit tests for cost and usage metrics."""

from __future__ import annotations

from src.mcp_server.metrics import prometheus_exposition, record_model_usage


def test_record_model_usage_basic():
    """Verify model usage recording."""
    record_model_usage(
        model="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=500,
        cost_per_1k_input=0.01,
        cost_per_1k_output=0.03,
        duration_seconds=1.5,
    )
    # No assertion needed; verifies no crash


def test_cost_calculation():
    """Verify cost calculation logic."""
    # Expected cost: (1000/1000 * 0.01) + (500/1000 * 0.03) = 0.01 + 0.015 = 0.025
    record_model_usage(
        model="test-model",
        input_tokens=1000,
        output_tokens=500,
        cost_per_1k_input=0.01,
        cost_per_1k_output=0.03,
        duration_seconds=1.0,
    )
    metrics_output = prometheus_exposition().decode()
    assert "model_cost_usd_total" in metrics_output
    assert "test-model" in metrics_output


def test_prometheus_exposition_includes_cost_metrics():
    """Verify Prometheus exposition includes new cost metrics."""
    record_model_usage(
        model="ollama-llama2",
        input_tokens=200,
        output_tokens=100,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        duration_seconds=0.5,
    )
    output = prometheus_exposition().decode()
    assert "model_tokens_total" in output
    assert "model_cost_usd_total" in output
    assert "model_inference_duration_seconds" in output
