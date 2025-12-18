"""Circuit Breaker pattern implementation for fault tolerance."""

import asyncio
import inspect
import time
import types
from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import Any

# Compatibility shim: support tests using asyncio.coroutine on Python 3.11+
if not hasattr(asyncio, "coroutine"):
    asyncio.coroutine = types.coroutine  # type: ignore[attr-defined]


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = CircuitState.CLOSED

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection.

        Supports both sync and async callables. When an async callable is
        provided, this method returns a coroutine that should be awaited.
        """
        # Compatibility shim: restore asyncio.coroutine on Python 3.11+
        if not hasattr(asyncio, "coroutine"):
            asyncio.coroutine = types.coroutine  # type: ignore[attr-defined]

        # If an awaitable object is passed directly, await it
        if inspect.isawaitable(func):

            async def _await_coro(coro):
                if self.state == CircuitState.OPEN:
                    if self._should_attempt_reset():
                        self.state = CircuitState.HALF_OPEN
                    else:
                        raise Exception("Circuit breaker is OPEN")

                try:
                    result = await coro
                    self._on_success()
                    return result
                except self.expected_exception as e:
                    self._on_failure()
                    raise e

            return _await_coro(func)

        # Async callable path returns an awaitable
        if inspect.iscoroutinefunction(func):

            async def _async_runner():
                if self.state == CircuitState.OPEN:
                    if self._should_attempt_reset():
                        self.state = CircuitState.HALF_OPEN
                    else:
                        raise Exception("Circuit breaker is OPEN")

                try:
                    result = await func(*args, **kwargs)
                    self._on_success()
                    return result
                except self.expected_exception as e:
                    self._on_failure()
                    raise e

            return _async_runner()

        # Sync callable path executes immediately
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return False
        return (time.time() - self.last_failure_time) >= self.timeout_seconds


def circuit_breaker(
    failure_threshold: int = 5,
    timeout_seconds: int = 60,
    expected_exception: type = Exception,
):
    """Decorator for circuit breaker pattern."""
    breaker = CircuitBreaker(
        failure_threshold, timeout_seconds, expected_exception
    )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await breaker.call(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return breaker.call(func, *args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
