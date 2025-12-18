"""
Loki Log Aggregation Integration for Aura IA MCP.

Provides structured logging with Loki push API support,
log correlation with traces, and log-based alerting.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class LogLevel(Enum):
    """Log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LokiConfig:
    """Configuration for Loki integration."""

    endpoint: str = "http://localhost:3100"
    push_path: str = "/loki/api/v1/push"
    tenant_id: str = "aura-ia"
    service_name: str = "aura-ia-gateway"
    environment: str = "development"
    batch_size: int = 100
    flush_interval_seconds: float = 5.0
    max_queue_size: int = 10000
    timeout_seconds: float = 10.0
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    default_labels: dict[str, str] = field(default_factory=dict)
    enable_trace_correlation: bool = True

    @classmethod
    def from_env(cls) -> LokiConfig:
        """Create config from environment variables."""
        return cls(
            endpoint=os.getenv("LOKI_ENDPOINT", "http://localhost:3100"),
            tenant_id=os.getenv("LOKI_TENANT_ID", "aura-ia"),
            service_name=os.getenv("OTEL_SERVICE_NAME", "aura-ia-gateway"),
            environment=os.getenv("ENVIRONMENT", "development"),
            batch_size=int(os.getenv("LOKI_BATCH_SIZE", "100")),
            flush_interval_seconds=float(
                os.getenv("LOKI_FLUSH_INTERVAL", "5.0")
            ),
        )


@dataclass
class LogEntry:
    """A structured log entry."""

    timestamp: datetime
    level: LogLevel
    message: str
    labels: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None

    def to_loki_stream(self) -> dict[str, Any]:
        """Convert to Loki stream format."""
        # Timestamp in nanoseconds
        ts_ns = str(int(self.timestamp.timestamp() * 1e9))

        # Combine structured metadata into JSON line
        log_data = {
            "level": self.level.value,
            "message": self.message,
            **self.metadata,
        }

        if self.trace_id:
            log_data["trace_id"] = self.trace_id
        if self.span_id:
            log_data["span_id"] = self.span_id

        return {
            "stream": {"level": self.level.value, **self.labels},
            "values": [[ts_ns, json.dumps(log_data)]],
        }


class LokiHandler(logging.Handler):
    """
    Python logging handler that sends logs to Loki.

    Integrates with the standard logging module for seamless adoption.
    """

    def __init__(
        self, config: LokiConfig | None = None, level: int = logging.INFO
    ):
        super().__init__(level)
        self.config = config or LokiConfig.from_env()
        self._aggregator: LokiLogAggregator | None = None

    def set_aggregator(self, aggregator: LokiLogAggregator) -> None:
        """Set the log aggregator."""
        self._aggregator = aggregator

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to Loki."""
        if not self._aggregator:
            return

        try:
            # Map Python log levels to Loki levels
            level_map = {
                logging.DEBUG: LogLevel.DEBUG,
                logging.INFO: LogLevel.INFO,
                logging.WARNING: LogLevel.WARNING,
                logging.ERROR: LogLevel.ERROR,
                logging.CRITICAL: LogLevel.CRITICAL,
            }
            level = level_map.get(record.levelno, LogLevel.INFO)

            # Extract trace context if available
            trace_id = getattr(record, "otelTraceID", None)
            span_id = getattr(record, "otelSpanID", None)

            # Build metadata
            metadata = {
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            # Add exception info if present
            if record.exc_info:
                metadata["exception"] = self.format(record)

            # Create log entry
            entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created, tz=UTC),
                level=level,
                message=record.getMessage(),
                metadata=metadata,
                trace_id=trace_id,
                span_id=span_id,
            )

            self._aggregator.add_entry(entry)

        except Exception:
            self.handleError(record)


class LokiLogAggregator:
    """
    Aggregates logs and pushes them to Loki in batches.

    Features:
    - Batch sending for efficiency
    - Automatic flushing on interval
    - Retry logic with exponential backoff
    - Queue overflow handling
    - Thread-safe operation
    """

    def __init__(self, config: LokiConfig | None = None):
        self.config = config or LokiConfig.from_env()
        self._queue: queue.Queue[LogEntry] = queue.Queue(
            maxsize=self.config.max_queue_size
        )
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._flush_thread: threading.Thread | None = None
        self._client: Any | None = None
        self._dropped_count = 0

        # Initialize default labels
        self._default_labels = {
            "service": self.config.service_name,
            "environment": self.config.environment,
            **self.config.default_labels,
        }

        if HTTPX_AVAILABLE:
            self._client = httpx.Client(timeout=self.config.timeout_seconds)

    def start(self) -> None:
        """Start the background flush thread."""
        if self._flush_thread is not None:
            return

        self._stop_event.clear()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True
        )
        self._flush_thread.start()

    def stop(self) -> None:
        """Stop the background flush thread and flush remaining logs."""
        self._stop_event.set()
        if self._flush_thread:
            self._flush_thread.join(timeout=10.0)
            self._flush_thread = None

        # Final flush
        self.flush()

        if self._client:
            self._client.close()

    def add_entry(self, entry: LogEntry) -> bool:
        """
        Add a log entry to the queue.

        Returns:
            True if entry was added, False if queue is full.
        """
        # Add default labels
        entry.labels = {**self._default_labels, **entry.labels}

        try:
            self._queue.put_nowait(entry)
            return True
        except queue.Full:
            self._dropped_count += 1
            return False

    def log(
        self,
        level: LogLevel,
        message: str,
        labels: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        """Log a message directly."""
        entry = LogEntry(
            timestamp=datetime.now(UTC),
            level=level,
            message=message,
            labels=labels or {},
            metadata=metadata or {},
            trace_id=trace_id,
            span_id=span_id,
        )
        self.add_entry(entry)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error message."""
        self.log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log a critical message."""
        self.log(LogLevel.CRITICAL, message, **kwargs)

    def _flush_loop(self) -> None:
        """Background thread that periodically flushes logs."""
        while not self._stop_event.is_set():
            try:
                # Wait for flush interval or stop event
                self._stop_event.wait(
                    timeout=self.config.flush_interval_seconds
                )

                if not self._stop_event.is_set():
                    self.flush()

            except Exception as e:
                # Log to stderr since we can't use the logging system here
                import sys

                print(f"Error in Loki flush loop: {e}", file=sys.stderr)

    def flush(self) -> int:
        """
        Flush queued logs to Loki.

        Returns:
            Number of entries flushed.
        """
        entries: list[LogEntry] = []

        # Drain up to batch_size entries from queue
        while len(entries) < self.config.batch_size:
            try:
                entry = self._queue.get_nowait()
                entries.append(entry)
            except queue.Empty:
                break

        if not entries:
            return 0

        # Group entries by label set for efficient Loki push
        streams = self._group_entries_to_streams(entries)

        # Push to Loki
        success = self._push_to_loki(streams)

        if not success:
            # Re-queue entries on failure (if possible)
            for entry in entries:
                try:
                    self._queue.put_nowait(entry)
                except queue.Full:
                    self._dropped_count += 1

        return len(entries) if success else 0

    def _group_entries_to_streams(
        self, entries: list[LogEntry]
    ) -> list[dict[str, Any]]:
        """Group log entries into Loki streams by label set."""
        streams_map: dict[str, dict[str, Any]] = {}

        for entry in entries:
            # Create a key from sorted labels
            label_key = json.dumps(entry.labels, sort_keys=True)

            if label_key not in streams_map:
                streams_map[label_key] = {"stream": entry.labels, "values": []}

            # Add log value
            ts_ns = str(int(entry.timestamp.timestamp() * 1e9))
            log_data = {
                "level": entry.level.value,
                "msg": entry.message,
                **entry.metadata,
            }
            if entry.trace_id:
                log_data["trace_id"] = entry.trace_id
            if entry.span_id:
                log_data["span_id"] = entry.span_id

            streams_map[label_key]["values"].append(
                [ts_ns, json.dumps(log_data)]
            )

        return list(streams_map.values())

    def _push_to_loki(self, streams: list[dict[str, Any]]) -> bool:
        """Push streams to Loki with retry logic."""
        if not HTTPX_AVAILABLE or not self._client:
            return False

        url = f"{self.config.endpoint}{self.config.push_path}"
        payload = {"streams": streams}
        headers = {
            "Content-Type": "application/json",
            "X-Scope-OrgID": self.config.tenant_id,
        }

        for attempt in range(self.config.retry_attempts):
            try:
                response = self._client.post(
                    url, json=payload, headers=headers
                )

                if response.status_code in (200, 204):
                    return True

                if response.status_code >= 500:
                    # Retry on server errors
                    time.sleep(self.config.retry_delay_seconds * (2**attempt))
                    continue

                # Don't retry on client errors
                return False

            except Exception:
                if attempt < self.config.retry_attempts - 1:
                    time.sleep(self.config.retry_delay_seconds * (2**attempt))
                    continue
                return False

        return False

    @property
    def dropped_count(self) -> int:
        """Get the number of dropped log entries."""
        return self._dropped_count

    @property
    def queue_size(self) -> int:
        """Get the current queue size."""
        return self._queue.qsize()


class StructuredLogger:
    """
    High-level structured logger for Aura IA services.

    Provides:
    - Structured logging with consistent format
    - Automatic trace correlation
    - Context management
    - Log-based metrics hints
    """

    def __init__(
        self,
        name: str,
        aggregator: LokiLogAggregator | None = None,
        config: LokiConfig | None = None,
    ):
        self.name = name
        self.aggregator = aggregator or LokiLogAggregator(config)
        self._context: dict[str, Any] = {}
        self._python_logger = logging.getLogger(name)

    def with_context(self, **kwargs: Any) -> StructuredLogger:
        """Create a new logger with additional context."""
        new_logger = StructuredLogger(self.name, self.aggregator)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _get_trace_context(self) -> tuple[str | None, str | None]:
        """Get current trace context if available."""
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span and span.get_span_context().is_valid:
                ctx = span.get_span_context()
                return (
                    format(ctx.trace_id, "032x"),
                    format(ctx.span_id, "016x"),
                )
        except ImportError:
            pass
        return None, None

    def _log(
        self,
        level: LogLevel,
        message: str,
        labels: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Internal logging method."""
        trace_id, span_id = self._get_trace_context()

        metadata = {"logger": self.name, **self._context, **kwargs}

        entry = LogEntry(
            timestamp=datetime.now(UTC),
            level=level,
            message=message,
            labels=labels or {},
            metadata=metadata,
            trace_id=trace_id,
            span_id=span_id,
        )

        self.aggregator.add_entry(entry)

        # Also log to Python logger for local output
        py_level = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }[level]

        self._python_logger.log(py_level, message, extra=metadata)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error message."""
        self._log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log a critical message."""
        self._log(LogLevel.CRITICAL, message, **kwargs)

    def exception(
        self, message: str, exc: Exception | None = None, **kwargs: Any
    ) -> None:
        """Log an exception with traceback."""
        import traceback

        if exc:
            kwargs["exception_type"] = type(exc).__name__
            kwargs["exception_message"] = str(exc)
            kwargs["traceback"] = traceback.format_exc()

        self._log(LogLevel.ERROR, message, **kwargs)

    # Specialized log methods for Aura IA events

    def log_request(
        self,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log an HTTP request."""
        self.info(
            f"{method} {path} - {status}",
            labels={"type": "request"},
            method=method,
            path=path,
            status=status,
            duration_ms=duration_ms,
            user_id=user_id,
            **kwargs,
        )

    def log_tool_call(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float,
        role: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log a tool invocation."""
        level = LogLevel.INFO if success else LogLevel.WARNING
        self._log(
            level,
            f"Tool call: {tool_name} - {'success' if success else 'failed'}",
            labels={"type": "tool_call"},
            tool_name=tool_name,
            success=success,
            duration_ms=duration_ms,
            role=role,
            **kwargs,
        )

    def log_approval(
        self,
        action: str,
        risk_level: str,
        status: str,
        approver: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log an approval decision."""
        self.info(
            f"Approval {status}: {action} (risk: {risk_level})",
            labels={"type": "approval"},
            action=action,
            risk_level=risk_level,
            approval_status=status,
            approver=approver,
            **kwargs,
        )

    def log_security_event(
        self, event_type: str, severity: str, description: str, **kwargs: Any
    ) -> None:
        """Log a security-related event."""
        level = (
            LogLevel.WARNING if severity != "critical" else LogLevel.CRITICAL
        )
        self._log(
            level,
            f"Security: {event_type} - {description}",
            labels={"type": "security", "severity": severity},
            event_type=event_type,
            security_severity=severity,
            **kwargs,
        )


# Global aggregator instance
_aggregator: LokiLogAggregator | None = None


def get_aggregator(config: LokiConfig | None = None) -> LokiLogAggregator:
    """Get or create the global Loki aggregator."""
    global _aggregator
    if _aggregator is None:
        _aggregator = LokiLogAggregator(config)
        _aggregator.start()
    return _aggregator


def get_logger(
    name: str, config: LokiConfig | None = None
) -> StructuredLogger:
    """Get a structured logger for the given name."""
    return StructuredLogger(name, get_aggregator(config))


def setup_logging_handler(config: LokiConfig | None = None) -> LokiHandler:
    """
    Setup a Loki handler for Python's logging module.

    Usage:
        handler = setup_logging_handler()
        logging.root.addHandler(handler)
    """
    handler = LokiHandler(config)
    handler.set_aggregator(get_aggregator(config))
    return handler


def shutdown() -> None:
    """Shutdown the global aggregator."""
    global _aggregator
    if _aggregator:
        _aggregator.stop()
        _aggregator = None


if __name__ == "__main__":
    # Example usage
    config = LokiConfig(
        endpoint="http://localhost:3100", service_name="aura-ia-example"
    )

    logger = get_logger("example", config)

    # Basic logging
    logger.debug("Debug message", extra_field="value")
    logger.info("Info message", user_id="123")
    logger.warning("Warning message", alert=True)
    logger.error("Error message", error_code=500)

    # Specialized logging
    logger.log_request("POST", "/api/chat", 200, 150.5, user_id="user123")
    logger.log_tool_call("search_documents", True, 250.0, role="analyst")
    logger.log_approval("delete_file", "high", "approved", approver="admin")
    logger.log_security_event(
        "rate_limit_exceeded", "warning", "User exceeded rate limit"
    )

    # Context-based logging
    request_logger = logger.with_context(
        request_id="req-123", session_id="sess-456"
    )
    request_logger.info("Processing request")
    request_logger.info("Request completed")

    # Flush and shutdown
    shutdown()
    print("Logging example completed")
