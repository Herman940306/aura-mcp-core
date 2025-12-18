"""Tests for Wave 6 Phase 2: QdrantConnectionPool with retry and circuit breaker."""

import time
from unittest.mock import patch

import pytest
from prometheus_client import CollectorRegistry

from aura_ia_mcp.services.model_gateway.qdrant_pool import (
    CircuitBreakerOpen,
    QdrantConnectionPool,
    retry_with_backoff,
)

# Skip if qdrant-client not available
pytest.importorskip("qdrant_client")

from qdrant_client import QdrantClient


def test_connection_pool_initialization():
    """Test connection pool initializes with correct size."""
    registry = CollectorRegistry()

    pool = QdrantConnectionPool(
        location=":memory:",
        pool_size=3,
        timeout=5.0,
        metrics_registry=registry,
    )

    assert pool.pool_size == 3
    assert pool._pool.qsize() == 3  # All available initially
    assert pool._in_use_count == 0

    pool.close()


def test_connection_pool_acquire_release():
    """Test acquiring and releasing connections."""
    registry = CollectorRegistry()

    pool = QdrantConnectionPool(
        location=":memory:", pool_size=2, metrics_registry=registry
    )

    # Acquire first client
    with pool.acquire(health_check=False) as client1:
        assert isinstance(client1, QdrantClient)
        assert pool._in_use_count == 1
        assert pool._pool.qsize() == 1

        # Acquire second client
        with pool.acquire(health_check=False) as client2:
            assert isinstance(client2, QdrantClient)
            assert pool._in_use_count == 2
            assert pool._pool.qsize() == 0  # Pool exhausted

    # Both released
    assert pool._in_use_count == 0
    assert pool._pool.qsize() == 2

    pool.close()


def test_connection_pool_retry_success():
    """Test execute_with_retry succeeds after transient failure."""
    registry = CollectorRegistry()

    pool = QdrantConnectionPool(
        location=":memory:", pool_size=2, metrics_registry=registry
    )

    # Mock operation that fails twice then succeeds
    attempt_count = {"count": 0}

    def flaky_operation(client: QdrantClient) -> str:
        attempt_count["count"] += 1
        if attempt_count["count"] < 3:
            raise Exception("Transient error")
        return "success"

    # Should succeed after retries
    result = pool.execute_with_retry(
        operation=flaky_operation,
        max_retries=3,
        base_delay=0.01,  # Fast for testing
        operation_name="test_op",
    )

    assert result == "success"
    assert attempt_count["count"] == 3  # Failed twice, succeeded third time

    pool.close()


def test_connection_pool_retry_exhausted():
    """Test execute_with_retry raises after max retries exhausted."""
    registry = CollectorRegistry()

    pool = QdrantConnectionPool(
        location=":memory:", pool_size=2, metrics_registry=registry
    )

    # Mock operation that always fails
    def failing_operation(client: QdrantClient) -> str:
        raise ValueError("Persistent error")

    # Should raise after max retries
    with pytest.raises(ValueError, match="Persistent error"):
        pool.execute_with_retry(
            operation=failing_operation,
            max_retries=2,
            base_delay=0.01,
            operation_name="test_fail",
        )

    pool.close()


def test_circuit_breaker_opens_after_threshold():
    """Test circuit breaker opens after consecutive failures."""
    registry = CollectorRegistry()

    # Low threshold for testing
    with patch.dict("os.environ", {"QDRANT_CIRCUIT_BREAKER_THRESHOLD": "3"}):
        pool = QdrantConnectionPool(
            location=":memory:", pool_size=2, metrics_registry=registry
        )

    # Simulate consecutive failures
    def failing_operation(client: QdrantClient) -> str:
        raise Exception("Error")

    # First 3 failures should open circuit breaker
    for i in range(3):
        try:
            pool.execute_with_retry(
                operation=failing_operation,
                max_retries=0,  # No retries, just record failure
                operation_name="test_cb",
            )
        except Exception:
            pass

    # Circuit breaker should now be open
    assert pool._circuit_breaker_open
    assert pool._consecutive_errors == 3

    # Next operation should fail fast
    with pytest.raises(CircuitBreakerOpen):
        pool.execute_with_retry(
            operation=failing_operation,
            max_retries=0,
            operation_name="test_cb_open",
        )

    pool.close()


def test_circuit_breaker_resets_on_success():
    """Test circuit breaker resets after successful operation."""
    registry = CollectorRegistry()

    pool = QdrantConnectionPool(
        location=":memory:", pool_size=2, metrics_registry=registry
    )

    # Record some failures
    pool._consecutive_errors = 5

    # Successful operation should reset
    def success_operation(client: QdrantClient) -> str:
        return "ok"

    result = pool.execute_with_retry(
        operation=success_operation, max_retries=0, operation_name="test_reset"
    )

    assert result == "ok"
    assert pool._consecutive_errors == 0

    pool.close()


def test_circuit_breaker_timeout_reset():
    """Test circuit breaker resets after timeout."""
    registry = CollectorRegistry()

    with patch.dict("os.environ", {"QDRANT_CIRCUIT_BREAKER_THRESHOLD": "2"}):
        pool = QdrantConnectionPool(
            location=":memory:", pool_size=2, metrics_registry=registry
        )

    # Open circuit breaker
    pool._consecutive_errors = 2
    pool._circuit_breaker_open = True
    pool._circuit_open_time = (
        time.time() - 61.0
    )  # 61 seconds ago (past timeout)

    # Should reset on next check
    pool._check_circuit_breaker()

    assert not pool._circuit_breaker_open
    assert pool._consecutive_errors == 0

    pool.close()


def test_retry_decorator():
    """Test retry_with_backoff decorator."""
    attempt_count = {"count": 0}

    @retry_with_backoff(max_retries=2, base_delay=0.01)
    def flaky_function():
        attempt_count["count"] += 1
        if attempt_count["count"] < 2:
            raise Exception("Transient")
        return "success"

    result = flaky_function()

    assert result == "success"
    assert attempt_count["count"] == 2


def test_connection_pool_metrics_recorded():
    """Test that Prometheus metrics are recorded."""
    registry = CollectorRegistry()

    pool = QdrantConnectionPool(
        location=":memory:", pool_size=3, metrics_registry=registry
    )

    # Acquire connection
    with pool.acquire(health_check=False):
        pass

    # Check metrics exist
    metric_families = {m.name for m in registry.collect()}
    assert "qdrant_connection_pool_size" in metric_families
    assert (
        "qdrant_retry" in metric_families
    )  # Counter without _total suffix in collection
    assert "qdrant_circuit_breaker_open" in metric_families

    pool.close()


def test_connection_pool_concurrent_usage():
    """Test pool handles concurrent access correctly."""
    registry = CollectorRegistry()

    pool = QdrantConnectionPool(
        location=":memory:", pool_size=5, metrics_registry=registry
    )

    results = []

    def concurrent_operation(client: QdrantClient) -> int:
        time.sleep(0.01)  # Simulate work
        return 1

    # Simulate concurrent requests (sequential in test)
    for _ in range(10):
        result = pool.execute_with_retry(
            operation=concurrent_operation,
            max_retries=0,
            operation_name="concurrent",
        )
        results.append(result)

    assert len(results) == 10
    assert all(r == 1 for r in results)

    # Pool should be fully available after all operations
    assert pool._pool.qsize() == 5
    assert pool._in_use_count == 0

    pool.close()

    pool.close()
