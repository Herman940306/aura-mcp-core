"""SICD (Self-Improving Cyclical Development) training stub.

Minimal module to record training "episodes" to a JSONL file and provide a
placeholder risk scoring heuristic. Safe for SAFE MODE: no heavy ML imports,
soft‑fail on filesystem issues.

Design goals:
- Non-blocking append for episode logging
- Input sanitization to preserve provenance integrity
- Deterministic placeholder scoring (stable across runs)
- Easy future extension (real model scoring, curriculum shaping)

JSONL envelope example (wrapped):
{"ts": ISO8601, "episode_id": "E123", "tags": ["alpha"],
 "metrics": {"x": 1}, "risk": {}}
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_BASE_DIR = Path(os.getenv("SICD_LOG_DIR", "logs"))
_EPISODES_FILE = _BASE_DIR / "sicd_episodes.jsonl"

# Ensure directory exists (best-effort; ignore failures in SAFE MODE)
with contextlib.suppress(Exception):  # pragma: no cover - trivial
    _BASE_DIR.mkdir(parents=True, exist_ok=True)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_float(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (ValueError, TypeError):
        return None


def score_risk(metrics: dict[str, Any]) -> dict[str, Any]:
    """Return placeholder risk scoring.

    Current heuristic aggregates any numeric metric into a simple average and
    produces three fabricated buckets. This function is deterministic and will
    be replaced by real modeling later.
    """
    extracted: list[float] = []
    for v in metrics.values():
        fv = _safe_float(v)
        if fv is not None:
            extracted.append(fv)
    avg = sum(extracted) / (len(extracted) or 1)
    # Simple bucketization
    NEGATIVE_BOUND = 0
    LOW_BOUND = 1
    MOD_BOUND = 5
    if avg < NEGATIVE_BOUND:
        level = "negative"
    elif avg < LOW_BOUND:
        level = "low"
    elif avg < MOD_BOUND:
        level = "moderate"
    else:
        level = "elevated"
    return {
        "average": avg,
        "count": len(extracted),
        "level": level,
        "ts": _iso_now(),
        "model": "placeholder_v1",
    }


def record_episode(
    episode_id: str,
    *,
    tags: Iterable[str] | None = None,
    metrics: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record a training episode to the JSONL log and return the envelope.

    This is intentionally tolerant: failures to write the log file are ignored
    so that the calling workflow does not fail in SAFE MODE.
    """
    if not episode_id:
        raise ValueError("episode_id must be a non-empty string")
    tags_list = [t for t in (tags or []) if t]
    metrics_map: dict[str, Any] = metrics or {}
    risk = score_risk(metrics_map)
    envelope: dict[str, Any] = {
        "ts": _iso_now(),
        "episode_id": episode_id,
        "tags": tags_list,
        "metrics": metrics_map,
        "risk": risk,
        "extra": extra or {},
    }
    line = json.dumps(envelope, separators=(",", ":"))
    try:
        with _LOCK, _EPISODES_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        # Silently ignore write issues (e.g., permissions) in SAFE MODE
        pass
    return envelope


__all__ = ["record_episode", "score_risk"]
