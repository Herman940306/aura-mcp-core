from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path


def _log_paths() -> tuple[Path, Path]:
    log_dir = Path(os.getenv("MCP_TOOL_SPANS_DIR", "logs"))
    return log_dir, log_dir / "mcp_tool_spans.jsonl"


@dataclass
class ToolSpan:
    timestamp_ms: int
    tool_name: str
    method: str | None
    duration_ms: int
    success: bool
    error_code: str | None
    # Extended optional fields
    extra: dict | None


class TelemetryBatcher:
    """Batches telemetry spans for efficient I/O."""

    def __init__(
        self, max_batch_size: int = 100, flush_interval: float = 10.0
    ) -> None:
        self.max_batch_size = max_batch_size
        self.flush_interval = flush_interval
        self._buffer: list[ToolSpan] = []
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self._flush_task: asyncio.Task | None = None

    def add_span(self, span: ToolSpan) -> None:
        """Add a span to the buffer and flush if needed."""
        with self._lock:
            self._buffer.append(span)
            should_flush = len(self._buffer) >= self.max_batch_size

        if should_flush:
            self._flush_sync()

    def _flush_sync(self) -> None:
        """Synchronously flush buffer to disk."""
        with self._lock:
            if not self._buffer:
                return
            spans_to_write = self._buffer[:]
            self._buffer.clear()
            self._last_flush = time.time()

        log_dir, log_file = _log_paths()
        log_dir.mkdir(parents=True, exist_ok=True)

        try:
            with log_file.open("a", encoding="utf-8") as f:
                for span in spans_to_write:
                    f.write(
                        json.dumps(asdict(span), ensure_ascii=False) + "\n"
                    )
        except Exception as e:
            # Log error but don't crash
            import sys

            sys.stderr.write(f"[telemetry] Failed to write spans: {e}\n")

    def should_flush_time(self) -> bool:
        """Check if flush interval has elapsed."""
        with self._lock:
            return (time.time() - self._last_flush) >= self.flush_interval

    def flush(self) -> None:
        """Force flush all buffered spans."""
        self._flush_sync()


# Global telemetry batcher
_batcher = TelemetryBatcher()


def emit_span(
    tool_name: str,
    start_time: float,
    method: str | None = None,
    success: bool = True,
    error_code: str | None = None,
    extra: dict | None = None,
) -> None:
    """Emit a telemetry span (batched for performance)."""
    end = time.perf_counter()
    span = ToolSpan(
        timestamp_ms=int(time.time() * 1000),
        tool_name=tool_name,
        method=method,
        duration_ms=int((end - start_time) * 1000),
        success=success,
        error_code=error_code,
        extra=extra,
    )
    _batcher.add_span(span)

    # Check if time-based flush is needed
    if _batcher.should_flush_time():
        _batcher.flush()


def flush_telemetry() -> None:
    """Force flush all buffered telemetry spans."""
    _batcher.flush()
