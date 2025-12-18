"""Provenance logging for MCP tool invocations and training episodes.

Writes line-delimited JSON records to `logs/provenance.jsonl` capturing:
  * timestamp (unix float)
  * kind: tool|episode
  * name (tool name or episode id)
  * success (bool, tools only)
  * duration_ms (tools only)
  * metadata (flattened arguments / episode metadata)

This lightweight module avoids external dependencies and keeps write path
simple. Call `log_tool_invocation` from the MCP dispatch layer after each
tool execution and `log_episode` from training orchestration when episodes
start or complete.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_PROVENANCE_PATH = Path(
    os.getenv("PROVENANCE_LOG_PATH", "logs/provenance.jsonl")
)
_PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _safe_json(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):  # narrow exception types
        return str(value)


def _append(record: dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False)
    with _PROVENANCE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def log_tool_invocation(
    name: str,
    arguments: dict[str, Any],
    success: bool,
    duration_ms: float,
    result: dict[str, Any] | None = None,
) -> None:
    rec_meta = None
    if isinstance(result, dict) and "summary" in result:
        rec_meta = _safe_json(result.get("summary"))
    record = {
        "ts": time.time(),
        "kind": "tool",
        "name": name,
        "success": success,
        "duration_ms": round(duration_ms, 3),
        "arguments": _safe_json(arguments),
        "result_meta": rec_meta,
    }
    _append(record)


def log_episode(
    episode_id: str,
    phase: str,
    meta: dict[str, Any] | None = None,
) -> None:
    record = {
        "ts": time.time(),
        "kind": "episode",
        "name": episode_id,
        "phase": phase,
        "metadata": _safe_json(meta or {}),
    }
    _append(record)


__all__ = ["log_tool_invocation", "log_episode"]
