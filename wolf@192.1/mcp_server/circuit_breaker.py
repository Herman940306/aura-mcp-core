"""Async circuit breaker with half-open probing support."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional


class CircuitBreakerOpen(RuntimeError):
    """Raised when the circuit is open and calls are rejected."""


@dataclass(slots=True)
class CircuitBreakerConfig:
    fail_threshold: int = 5
    reset_timeout: float = 20.0
    half_open_max_calls: int = 1


class CircuitBreaker:
    """Simple async-safe circuit breaker for outbound backend calls."""

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self._config = config or CircuitBreakerConfig()
        self._state = "closed"
        self._consecutive_failures = 0
        self._half_open_calls = 0
        self._opened_at = 0.0
        self._last_error: Optional[str] = None
        self._lock = asyncio.Lock()

    async def before_call(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._state == "open":
                elapsed = now - self._opened_at
                if elapsed >= self._config.reset_timeout:
                    self._state = "half_open"
                    self._half_open_calls = 0
                else:
                    remaining = self._config.reset_timeout - elapsed
                    raise CircuitBreakerOpen(f"circuit_open:{remaining:.2f}s_remaining")
            if self._state == "half_open":
                if self._half_open_calls >= self._config.half_open_max_calls:
                    raise CircuitBreakerOpen("circuit_half_open_busy")
                self._half_open_calls += 1

    async def record_success(self) -> None:
        async with self._lock:
            self._state = "closed"
            self._consecutive_failures = 0
            self._half_open_calls = 0
            self._opened_at = 0.0
            self._last_error = None

    async def record_failure(self, error: Optional[str] = None) -> None:
        async with self._lock:
            self._last_error = error
            if self._state == "half_open":
                self._state = "open"
                self._opened_at = time.monotonic()
                self._consecutive_failures = self._config.fail_threshold
                self._half_open_calls = 0
                return
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._config.fail_threshold:
                self._state = "open"
                self._opened_at = time.monotonic()

    async def snapshot(self) -> Dict[str, object]:  # noqa: ANN401
        async with self._lock:
            open_for = 0.0
            if self._state == "open" and self._opened_at:
                open_for = time.monotonic() - self._opened_at
            return {
                "state": self._state,
                "consecutive_failures": self._consecutive_failures,
                "fail_threshold": self._config.fail_threshold,
                "half_open_max_calls": self._config.half_open_max_calls,
                "open_for_seconds": round(open_for, 3),
                "last_error": self._last_error,
            }

    async def current_state(self) -> str:
        async with self._lock:
            return self._state
