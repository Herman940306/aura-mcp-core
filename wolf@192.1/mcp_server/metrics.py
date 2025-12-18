"""In-process metrics collection with Prometheus exposition.

Thread-safe counters maintained for total tool calls, successes, failures,
per-tool counts, and a Prometheus `/metrics` endpoint.
"""

from __future__ import annotations

import threading
import time

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

_lock = threading.Lock()
_process_start_time = time.time()
_counters: dict[str, int] = {
    "tool_calls_total": 0,
    "tool_calls_success": 0,
    "tool_calls_failure": 0,
}
_per_tool: dict[str, int] = {}


_registry = CollectorRegistry()
_tool_calls_total = Counter(
    "tool_calls_total",
    "Total tool invocations",
    registry=_registry,
)
_tool_calls_success = Counter(
    "tool_calls_success",
    "Successful tool invocations",
    registry=_registry,
)
_tool_calls_failure = Counter(
    "tool_calls_failure",
    "Failed tool invocations",
    registry=_registry,
)
_tool_last_success_rate = Gauge(
    "tool_success_rate",
    "Last computed tool success rate",
    registry=_registry,
)

# Tool call latency histogram (taxonomy: tool_latency_seconds)
_tool_call_latency_seconds = Histogram(
    "tool_latency_seconds",
    "Tool execution latency distribution (seconds)",
    labelnames=("tool",),
    buckets=(
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.0,
        5.0,
        10.0,
    ),
    registry=_registry,
)

# Backend health check metrics
_backend_checks_total = Counter(
    "backend_health_checks_total",
    "Total backend health checks",
    registry=_registry,
)
_backend_checks_success = Counter(
    "backend_health_checks_success",
    "Successful backend health checks",
    registry=_registry,
)
_backend_checks_failure = Counter(
    "backend_health_checks_failure",
    "Failed backend health checks",
    registry=_registry,
)
_backend_last_latency_ms = Gauge(
    "backend_health_last_latency_ms",
    "Last measured backend health latency (ms)",
    registry=_registry,
)

# Cost and usage metrics (taxonomy: model_tokens_total, model_cost_usd_total)
_model_tokens_total = Counter(
    "model_tokens_total",
    "Total tokens processed by model",
    labelnames=("model", "direction"),
    registry=_registry,
)
_model_cost_usd_total = Counter(
    "model_cost_usd_total",
    "Total estimated cost in USD",
    labelnames=("model",),
    registry=_registry,
)
_model_inference_duration_seconds = Histogram(
    "model_inference_duration_seconds",
    "Model inference latency distribution",
    labelnames=("model",),
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
    registry=_registry,
)


def incr(tool_name: str, success: bool) -> None:
    with _lock:
        _counters["tool_calls_total"] += 1
        if success:
            _counters["tool_calls_success"] += 1
        else:
            _counters["tool_calls_failure"] += 1
        _per_tool[tool_name] = _per_tool.get(tool_name, 0) + 1
        _tool_calls_total.inc()
        if success:
            _tool_calls_success.inc()
        else:
            _tool_calls_failure.inc()


def record_tool_latency(tool_name: str, duration_seconds: float) -> None:
    """Record latency for a tool invocation.

    Safe no-op if duration invalid (negative or non-numeric).
    """
    if duration_seconds is None:
        return
    try:
        if duration_seconds < 0:
            return
        _tool_call_latency_seconds.labels(tool=tool_name).observe(
            duration_seconds
        )
    except Exception:  # noqa: BLE001
        # Defensive: never raise from metrics path
        pass


def snapshot() -> dict[str, object]:  # noqa: ANN401
    with _lock:
        if _counters["tool_calls_total"]:
            success_rate = (
                _counters["tool_calls_success"] / _counters["tool_calls_total"]
            )
        else:
            success_rate = 0.0
        _tool_last_success_rate.set(success_rate)
        elapsed = max(0.0, time.time() - _process_start_time)
        return {
            **_counters,
            "per_tool": dict(sorted(_per_tool.items())),
            "success_rate": success_rate,
            "uptime_seconds": elapsed,
        }


def prometheus_exposition() -> bytes:
    """Return Prometheus metrics payload."""
    return generate_latest(_registry)


def record_backend_health(success: bool, latency_ms: int | None) -> None:
    with _lock:
        _backend_checks_total.inc()
        if success:
            _backend_checks_success.inc()
        else:
            _backend_checks_failure.inc()
        if latency_ms is not None:
            _backend_last_latency_ms.set(latency_ms)


def performance_summary() -> dict[str, object]:  # noqa: ANN401
    """Return performance rates (calls/sec) since process start."""
    snap = snapshot()
    uptime_val = snap.get("uptime_seconds", 0.0)
    # Safe numeric conversion without broad excepts
    if isinstance(uptime_val, (int, float)):
        uptime = float(uptime_val)
    else:
        try:
            uptime = float(str(uptime_val))
        except ValueError:
            uptime = 0.0
    uptime = uptime if uptime > 0.0 else 1e-6

    def _safe_int(value: object) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        try:
            return int(str(value))
        except ValueError:
            return 0

    calls_total = _safe_int(snap.get("tool_calls_total", 0))
    success = _safe_int(snap.get("tool_calls_success", 0))
    failure = _safe_int(snap.get("tool_calls_failure", 0))
    # Backend total: derive from success + failure counters (public API)
    backend_total = _safe_int(
        _backend_checks_success._value.get()
    ) + _safe_int(  # noqa: SLF001
        _backend_checks_failure._value.get()
    )  # noqa: SLF001
    return {
        "uptime_seconds": uptime,
        "tool_calls_per_sec": calls_total / uptime,
        "success_rate": snap.get("success_rate"),
        "success_per_sec": success / uptime,
        "failure_per_sec": failure / uptime,
        "backend_checks_total": backend_total,
    }


def record_model_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_per_1k_input: float,
    cost_per_1k_output: float,
    duration_seconds: float,
) -> None:
    """Record model token usage and cost metrics.

    Args:
        model: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost_per_1k_input: Cost per 1K input tokens (USD)
        cost_per_1k_output: Cost per 1K output tokens (USD)
        duration_seconds: Inference duration
    """
    _model_tokens_total.labels(model=model, direction="input").inc(
        input_tokens
    )
    _model_tokens_total.labels(model=model, direction="output").inc(
        output_tokens
    )
    input_cost = (input_tokens / 1000.0) * cost_per_1k_input
    output_cost = (output_tokens / 1000.0) * cost_per_1k_output
    total_cost = input_cost + output_cost
    _model_cost_usd_total.labels(model=model).inc(total_cost)
    _model_inference_duration_seconds.labels(model=model).observe(
        duration_seconds
    )


__all__ = [
    "incr",
    "snapshot",
    "prometheus_exposition",
    "record_backend_health",
    "performance_summary",
    "record_tool_latency",
    "record_model_usage",
]
