"""Qdrant connection pool with retry logic and circuit breaker.

Wave 6 Phase 2: Production-grade connection management for Qdrant client.
"""

import logging
import os
import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from queue import Empty, Queue
from typing import Any, TypeVar

from prometheus_client import CollectorRegistry, Counter, Gauge

try:
    from qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None  # type: ignore

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default metrics
_default_pool_size = Gauge(
    "qdrant_connection_pool_size",
    "Number of connections in pool",
    ["state"],  # available, in_use
)
_default_retry_count = Counter(
    "qdrant_retry_total", "Number of retry attempts", ["operation", "success"]
)
_default_circuit_breaker_state = Gauge(
    "qdrant_circuit_breaker_open", "Circuit breaker state (1=open, 0=closed)"
)


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""

    pass


class QdrantConnectionPool:
    """Connection pool for Qdrant clients with health checks and retry logic.

    Features:
    - Pool of reusable QdrantClient instances
    - Health checks on acquire (ping collection list)
    - Automatic retry with exponential backoff
    - Circuit breaker pattern (fail fast after consecutive errors)
    - Prometheus metrics
    """

    def __init__(
        self,
        url: str | None = None,
        pool_size: int = 5,
        timeout: float = 5.0,
        location: str | None = None,
        metrics_registry: CollectorRegistry | None = None,
    ):
        """Initialize connection pool.

        Args:
            url: Qdrant server URL (optional if location provided)
            pool_size: Number of clients in pool (default: 5)
            timeout: Client timeout in seconds (default: 5.0)
            location: In-memory location (e.g., ":memory:") for testing
            metrics_registry: Optional Prometheus registry for test isolation
        """
        if QdrantClient is None:
            raise RuntimeError("qdrant-client not installed")

        self.url = url
        self.location = location
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool: Queue = Queue(maxsize=pool_size)
        self._in_use_count = 0

        # Circuit breaker state
        self._consecutive_errors = 0
        self._circuit_breaker_threshold = int(
            os.getenv("QDRANT_CIRCUIT_BREAKER_THRESHOLD", "10")
        )
        self._circuit_breaker_open = False
        self._circuit_open_time: float | None = None
        self._circuit_reset_timeout = 60.0  # Reset after 60 seconds

        # Metrics
        if metrics_registry is not None:
            self._pool_size_gauge = Gauge(
                "qdrant_connection_pool_size",
                "Number of connections in pool",
                ["state"],
                registry=metrics_registry,
            )
            self._retry_counter = Counter(
                "qdrant_retry_total",
                "Number of retry attempts",
                ["operation", "success"],
                registry=metrics_registry,
            )
            self._circuit_breaker_gauge = Gauge(
                "qdrant_circuit_breaker_open",
                "Circuit breaker state (1=open, 0=closed)",
                registry=metrics_registry,
            )
        else:
            self._pool_size_gauge = _default_pool_size
            self._retry_counter = _default_retry_count
            self._circuit_breaker_gauge = _default_circuit_breaker_state

        # Initialize pool with clients
        for _ in range(pool_size):
            if location:
                client = QdrantClient(location=location, timeout=timeout)
            elif url:
                client = QdrantClient(url=url, timeout=timeout)
            else:
                raise ValueError("Either url or location must be provided")
            self._pool.put(client)

        self._update_metrics()

    def _update_metrics(self):
        """Update Prometheus metrics."""
        available = self._pool.qsize()
        in_use = self._in_use_count

        self._pool_size_gauge.labels(state="available").set(available)
        self._pool_size_gauge.labels(state="in_use").set(in_use)
        self._circuit_breaker_gauge.set(1 if self._circuit_breaker_open else 0)

    def _check_circuit_breaker(self):
        """Check if circuit breaker should reset or raise exception."""
        if not self._circuit_breaker_open:
            return

        # Check if timeout expired
        if (
            self._circuit_open_time
            and time.time() - self._circuit_open_time
            > self._circuit_reset_timeout
        ):
            logger.info("Circuit breaker resetting after timeout")
            self._circuit_breaker_open = False
            self._consecutive_errors = 0
            self._circuit_open_time = None
            self._update_metrics()
            return

        raise CircuitBreakerOpen(
            f"Circuit breaker open due to {self._consecutive_errors} consecutive errors. "
            f"Will reset after {self._circuit_reset_timeout}s."
        )

    def _record_success(self):
        """Record successful operation (reset consecutive errors)."""
        if self._consecutive_errors > 0:
            logger.info(
                f"Resetting consecutive errors (was {self._consecutive_errors})"
            )
        self._consecutive_errors = 0

        # Close circuit breaker if it was open
        if self._circuit_breaker_open:
            logger.info("Circuit breaker closing after successful operation")
            self._circuit_breaker_open = False
            self._circuit_open_time = None
            self._update_metrics()

    def _record_failure(self):
        """Record failed operation (increment consecutive errors)."""
        self._consecutive_errors += 1

        if (
            self._consecutive_errors >= self._circuit_breaker_threshold
            and not self._circuit_breaker_open
        ):
            logger.error(
                f"Circuit breaker opening after {self._consecutive_errors} consecutive errors"
            )
            self._circuit_breaker_open = True
            self._circuit_open_time = time.time()
            self._update_metrics()

    @contextmanager
    def acquire(self, health_check: bool = True):
        """Acquire a client from the pool (context manager).

        Args:
            health_check: Perform health check (ping) on acquire (default: True)

        Yields:
            QdrantClient instance

        Raises:
            CircuitBreakerOpen: If circuit breaker is open
            Empty: If pool exhausted (all clients in use)
        """
        self._check_circuit_breaker()

        # Acquire client from pool
        client = self._pool.get(timeout=self.timeout)
        self._in_use_count += 1
        self._update_metrics()

        try:
            # Health check
            if health_check:
                try:
                    client.get_collections()
                except Exception as e:
                    logger.warning(f"Health check failed: {e}")
                    # Return to pool and raise
                    self._pool.put(client)
                    self._in_use_count -= 1
                    self._update_metrics()
                    raise

            yield client

            # Success: reset consecutive errors
            self._record_success()

        except Exception:
            # Failure: increment consecutive errors
            self._record_failure()
            raise
        finally:
            # Always return to pool
            self._pool.put(client)
            self._in_use_count -= 1
            self._update_metrics()

    def execute_with_retry(
        self,
        operation: Callable[[QdrantClient], T],
        max_retries: int = 3,
        base_delay: float = 0.5,
        operation_name: str = "unknown",
    ) -> T:
        """Execute operation with retry and exponential backoff.

        Args:
            operation: Callable that takes QdrantClient and returns result
            max_retries: Maximum retry attempts (default: 3)
            base_delay: Initial retry delay in seconds (default: 0.5)
            operation_name: Name for metrics (default: "unknown")

        Returns:
            Result of operation

        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                with self.acquire() as client:
                    result = operation(client)

                    # Success
                    if attempt > 0:
                        self._retry_counter.labels(
                            operation=operation_name, success="true"
                        ).inc()
                    return result

            except CircuitBreakerOpen:
                # Don't retry if circuit breaker is open
                raise
            except Exception as e:
                last_exception = e

                if attempt < max_retries:
                    # Calculate exponential backoff
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"Operation '{operation_name}' failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    # Max retries exhausted
                    self._retry_counter.labels(
                        operation=operation_name, success="false"
                    ).inc()
                    logger.error(
                        f"Operation '{operation_name}' failed after {max_retries + 1} attempts"
                    )

        raise last_exception  # type: ignore

    def close(self):
        """Close all connections in pool."""
        while not self._pool.empty():
            try:
                client = self._pool.get_nowait()
                # Qdrant client doesn't have explicit close, but we can clear reference
                del client
            except Empty:
                break


def retry_with_backoff(max_retries: int = 3, base_delay: float = 0.5):
    """Decorator for retry with exponential backoff (simple version without pool).

    Args:
        max_retries: Maximum retry attempts
        base_delay: Initial retry delay in seconds

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt < max_retries:
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            f"Function '{func.__name__}' failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)

            raise last_exception  # type: ignore

        return wrapper

    return decorator


def create_qdrant_pool_from_env() -> QdrantConnectionPool:
    """Create QdrantConnectionPool from environment variables.

    Environment variables:
        QDRANT_URL: Qdrant server URL (default: http://localhost:6333)
        QDRANT_POOL_SIZE: Pool size (default: 5)
        QDRANT_TIMEOUT: Client timeout in seconds (default: 5)
        QDRANT_CIRCUIT_BREAKER_THRESHOLD: Consecutive errors before opening (default: 10)

    Returns:
        Configured QdrantConnectionPool
    """
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    pool_size = int(os.getenv("QDRANT_POOL_SIZE", "5"))
    timeout = float(os.getenv("QDRANT_TIMEOUT", "5.0"))

    return QdrantConnectionPool(url=url, pool_size=pool_size, timeout=timeout)
