"""Telemetry batching and span logging stubs.

Writes JSON lines to ``logs/mcp_tool_spans.jsonl``.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOG_FILE = Path("logs/mcp_tool_spans.jsonl")
_LOCK = threading.Lock()


@dataclass
class ToolSpan:
    timestamp_ms: int
    tool_name: str
    method: str
    duration_ms: int
    success: bool
    error_code: str | None = None
    extra: dict[str, Any] | None = None


class TelemetryBatcher:
    def __init__(
        self,
        max_batch_size: int = 100,
        flush_interval: float = 10.0,
    ) -> None:
        self.max_batch_size = max_batch_size
        self.flush_interval = flush_interval
        self._buffer: list[ToolSpan] = []
        self._last_flush = time.time()

    def add_span(self, span: ToolSpan) -> None:
        self._buffer.append(span)
        if self.should_flush_size():
            self.flush()

    def should_flush_size(self) -> bool:
        return len(self._buffer) >= self.max_batch_size

    def should_flush_time(self) -> bool:
        return (time.time() - self._last_flush) >= self.flush_interval

    def flush(self) -> None:
        if not self._buffer:
            return
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK, _LOG_FILE.open("a", encoding="utf-8") as fh:
            for span in self._buffer:
                fh.write(json.dumps(span.__dict__) + "\n")
        self._buffer.clear()
        self._last_flush = time.time()


_def_batcher = TelemetryBatcher()


def record_tool_span(
    tool_name: str,
    method: str,
    duration_ms: int,
    success: bool,
    error_code: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    span = ToolSpan(
        timestamp_ms=int(time.time() * 1000),
        tool_name=tool_name,
        method=method,
        duration_ms=duration_ms,
        success=success,
        error_code=error_code,
        extra=extra,
    )
    _def_batcher.add_span(span)


def flush_telemetry() -> None:
    _def_batcher.flush()
