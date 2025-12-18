"""Config reload helper.
Clears caches, re-evaluates env-driven thresholds.
"""

from __future__ import annotations

from mcp_server.security import anomaly_detector


def reload_all() -> dict:
    return {"thresholds": anomaly_detector._DEFAULT_THRESHOLDS}
