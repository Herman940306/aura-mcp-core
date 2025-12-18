"""Unit tests for lightweight metrics snapshot helper."""

from __future__ import annotations

import importlib

import pytest

from mcp_server import metrics


def test_metrics_snapshot_counts_and_success_rate() -> None:
    module = importlib.reload(metrics)
    module.incr("tool_alpha", True)
    module.incr("tool_alpha", False)
    module.incr("tool_beta", True)

    snapshot = module.snapshot()

    assert snapshot["tool_calls_total"] == 3
    assert snapshot["tool_calls_success"] == 2
    assert snapshot["tool_calls_failure"] == 1
    assert snapshot["per_tool"]["tool_alpha"] == 2
    assert snapshot["per_tool"]["tool_beta"] == 1
    assert snapshot["success_rate"] == pytest.approx(2 / 3)
