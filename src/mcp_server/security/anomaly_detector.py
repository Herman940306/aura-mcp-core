"""Simple anomaly detector over security audit log.

Computes frequency of events and flags spikes above thresholds.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_AUDIT_FILE = Path("logs/security_audit.jsonl")
_DEFAULT_THRESHOLDS = {
    "rate_limited": int(os.getenv("ANOMALY_THRESHOLD_RATE_LIMITED", "10")),
    "approval_requested": int(
        os.getenv("ANOMALY_THRESHOLD_APPROVAL_REQUESTED", "20")
    ),
    "tool_failure": int(os.getenv("ANOMALY_THRESHOLD_TOOL_FAILURE", "15")),
}

_DEF_WINDOW_SEC = 3600


def analyze(window_seconds: int = _DEF_WINDOW_SEC) -> dict[str, Any]:
    now = time.time()
    counts: dict[str, int] = {}
    recent: dict[str, int] = {}
    recent_short: dict[str, int] = {}
    short_window = min(900, window_seconds)  # 15m snapshot
    if not _AUDIT_FILE.exists():
        return {
            "events": counts,
            "recent": recent,
            "recent_short": recent_short,
            "anomalies": [],
        }
    for line in _AUDIT_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = entry.get("type")
        raw_ts = entry.get("ts", 0)
        try:
            ts = float(raw_ts)
        except (TypeError, ValueError):
            # Skip entries with invalid timestamps
            continue
        counts[etype] = counts.get(etype, 0) + 1
        age = now - ts
        if age <= window_seconds:
            recent[etype] = recent.get(etype, 0) + 1
        if age <= short_window:
            recent_short[etype] = recent_short.get(etype, 0) + 1
    anomalies = []
    for etype, limit in _DEFAULT_THRESHOLDS.items():
        val = recent.get(etype, 0)
        if val > limit:
            anomalies.append({"type": etype, "count": val, "threshold": limit})
    trend = {}
    for etype, val in recent.items():
        sval = recent_short.get(etype, 0)
        accel_short = (sval / short_window) if short_window else 0.0
        accel_long = (val / window_seconds) if window_seconds else 0.0
        trend[etype] = {
            "short_window": sval,
            "long_window": val,
            "acceleration": accel_short - accel_long,
        }
    return {
        "events": counts,
        "recent": recent,
        "recent_short": recent_short,
        "trend": trend,
        "anomalies": anomalies,
        "window_seconds": window_seconds,
    }
