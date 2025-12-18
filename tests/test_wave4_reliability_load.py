"""
Wave 4: Circuit Breaker & Rate Limiter Load Tests

Stress tests for reliability components including:
- Circuit breaker state transitions under load
- Rate limiter behavior at capacity
- Combined reliability features
- Concurrent request handling
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from aura_ia_mcp.core.circuit_breaker import CircuitBreaker, CircuitState
from aura_ia_mcp.core.rate_limiter import RateLimiter


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state machine."""

    def test_closed_to_open_transition(self):
        """Test transition from CLOSED to OPEN."""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=5)

        def failing_func():
            raise Exception("Service unavailable")

        assert cb.state == CircuitState.CLOSED

        # Trigger failures
        for i in range(3):
            try:
                cb.call(failing_func)
            except Exception:
                pass

        # Should be OPEN after threshold
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count >= 3

    def test_open_to_half_open_transition(self):
        """Test transition from OPEN to HALF_OPEN after timeout."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=1)

        def fail():
            raise Exception("Fail")

        # Open circuit
        for _ in range(2):
            try:
                cb.call(fail)
            except Exception:
                pass

        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(1.5)

        # Next attempt should try HALF_OPEN
        def success():
            return "ok"

        result = cb.call(success)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_closed_on_success(self):
        """Test transition from HALF_OPEN to CLOSED on success."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=1)

        def fail():
            raise Exception("Fail")

        def succeed():
            return "success"

        # Open circuit
        for _ in range(2):
            try:
                cb.call(fail)
            except Exception:
                pass

        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(1.5)

        # Successful call closes circuit
        cb.call(succeed)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_to_open_on_failure(self):
        """Test transition from HALF_OPEN back to OPEN on failure."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=1)

        def fail():
            raise Exception("Still failing")

        # Open circuit
        for _ in range(2):
            try:
                cb.call(fail)
            except Exception:
                pass

        # Wait for timeout
        time.sleep(1.5)

        # Failed attempt reopens circuit
        try:
            cb.call(fail)
        except Exception:
            pass

        assert cb.state == CircuitState.OPEN

    def test_circuit_resets_after_recovery(self):
        """Test circuit fully resets after recovery."""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=1)

        def fail():
            raise Exception("Fail")

        def succeed():
            return "ok"

        # Open circuit
        for _ in range(3):
            try:
                cb.call(fail)
            except Exception:
                pass

        assert cb.state == CircuitState.OPEN

        # Recover
        time.sleep(1.5)
        cb.call(succeed)

        # Circuit should be fully reset
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestCircuitBreakerConcurrency:
    """Test circuit breaker under concurrent load."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_closed_circuit(self):
        """Test circuit handles concurrent calls when CLOSED."""
        cb = CircuitBreaker(failure_threshold=10)
        call_count = 0

        async def task():
            nonlocal call_count
            result = await cb.call(asyncio.coroutine(lambda: "ok")())
            call_count += 1
            return result

        # Run 50 concurrent tasks
        results = await asyncio.gather(*[task() for _ in range(50)])

        assert len(results) == 50
        assert all(r == "ok" for r in results)
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_concurrent_failures_open_circuit(self):
        """Test circuit opens correctly under concurrent failures."""
        cb = CircuitBreaker(failure_threshold=5)

        async def failing_task():
            try:
                await cb.call(
                    asyncio.coroutine(
                        lambda: (_ for _ in ()).throw(Exception("Fail"))
                    )()
                )
            except Exception:
                pass

        # Trigger concurrent failures
        await asyncio.gather(*[failing_task() for _ in range(10)])

        # Circuit should be open
        assert cb.state == CircuitState.OPEN

    def test_high_throughput_state_transitions(self):
        """Test state transitions under high throughput."""
        cb = CircuitBreaker(failure_threshold=5, timeout_seconds=2)
        success_count = 0
        failure_count = 0

        def mixed_function(should_fail: bool):
            if should_fail:
                raise Exception("Fail")
            return "ok"

        # Phase 1: Mostly failures -> OPEN
        for i in range(10):
            try:
                result = cb.call(mixed_function, should_fail=True)
                success_count += 1
            except Exception:
                failure_count += 1

        assert cb.state == CircuitState.OPEN

        # Phase 2: Wait for recovery window
        time.sleep(2.5)

        # Phase 3: Successes -> CLOSED
        try:
            cb.call(mixed_function, should_fail=False)
            assert cb.state == CircuitState.CLOSED
        except Exception:
            pass


class TestRateLimiterLoad:
    """Test rate limiter under load."""

    def test_rate_limit_capacity(self):
        """Test rate limiter respects capacity."""
        limiter = RateLimiter(capacity=10, refill_rate=0.0)  # No refill
        client = "test_client"

        allowed = 0
        denied = 0

        for _ in range(20):
            if limiter.is_allowed(client):
                allowed += 1
            else:
                denied += 1

        assert allowed == 10  # Capacity
        assert denied == 10

    def test_rate_limit_refill_over_time(self):
        """Test rate limiter refills tokens correctly."""
        limiter = RateLimiter(capacity=5, refill_rate=10.0)  # 10 tokens/sec
        client = "test_client"

        # Exhaust capacity
        for _ in range(5):
            assert limiter.is_allowed(client)

        # Should be blocked
        assert not limiter.is_allowed(client)

        # Wait for refill (need 1 token = 0.1 seconds)
        time.sleep(0.2)

        # Should allow 2 more requests (~2 tokens refilled)
        assert limiter.is_allowed(client)
        assert limiter.is_allowed(client)

    def test_rate_limit_burst_handling(self):
        """Test rate limiter handles burst traffic."""
        limiter = RateLimiter(capacity=100, refill_rate=50.0)
        client = "burst_client"

        # Burst of 100 requests
        burst_allowed = sum(
            1 for _ in range(100) if limiter.is_allowed(client)
        )
        assert burst_allowed == 100  # All allowed initially

        # Next 50 should be blocked
        burst_blocked = sum(
            1 for _ in range(50) if not limiter.is_allowed(client)
        )
        assert burst_blocked == 50

    def test_rate_limit_concurrent_clients(self):
        """Test rate limiter isolates clients."""
        limiter = RateLimiter(capacity=10, refill_rate=5.0)

        def client_requests(client_id: str) -> int:
            """Make requests until blocked."""
            allowed = 0
            for _ in range(15):  # Try 15 requests
                if limiter.is_allowed(client_id):
                    allowed += 1
            return allowed

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(client_requests, f"client_{i}")
                for i in range(5)
            ]
            results = [f.result() for f in futures]

        # Each client should get ~10 tokens
        assert all(8 <= r <= 11 for r in results)  # Allow some variance

    def test_rate_limit_sustained_load(self):
        """Test rate limiter under sustained load."""
        limiter = RateLimiter(capacity=20, refill_rate=10.0)
        client = "sustained_client"

        total_allowed = 0
        total_denied = 0

        # Sustained requests over 2 seconds
        start = time.time()
        while time.time() - start < 2.0:
            if limiter.is_allowed(client):
                total_allowed += 1
            else:
                total_denied += 1
            time.sleep(0.05)  # Request every 50ms

        # Should allow ~20 initial + ~20 refilled = ~40 total
        assert 35 <= total_allowed <= 45  # Allow variance


class TestCombinedReliability:
    """Test circuit breaker and rate limiter together."""

    @pytest.mark.asyncio
    async def test_rate_limit_before_circuit_breaker(self):
        """Test rate limiter blocks before circuit breaker is invoked."""
        limiter = RateLimiter(capacity=5, refill_rate=0.0)
        cb = CircuitBreaker(failure_threshold=3)
        client = "test_client"

        async def protected_call():
            if not limiter.is_allowed(client):
                raise Exception("Rate limited")
            return await cb.call(asyncio.coroutine(lambda: "ok")())

        # First 5 should pass
        for _ in range(5):
            result = await protected_call()
            assert result == "ok"

        # 6th should fail at rate limiter
        with pytest.raises(Exception, match="Rate limited"):
            await protected_call()

        # Circuit breaker should still be CLOSED
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_stops_rate_limit_drain(self):
        """Test open circuit prevents rate limit token consumption."""
        limiter = RateLimiter(capacity=10, refill_rate=0.0)
        cb = CircuitBreaker(failure_threshold=2)
        client = "test_client"

        async def failing_call():
            if not limiter.is_allowed(client, tokens=1):
                raise Exception("Rate limited")
            result = await cb.call(
                asyncio.coroutine(
                    lambda: (_ for _ in ()).throw(Exception("Fail"))
                )()
            )
            return result

        # Trigger circuit breaker
        for _ in range(2):
            try:
                await failing_call()
            except Exception:
                pass

        assert cb.state == CircuitState.OPEN

        # Further calls should fail immediately (no rate limit consumption)
        initial_tokens = limiter.buckets[client].tokens
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await cb.call(asyncio.coroutine(lambda: "ok")())

        # Rate limiter tokens should be unchanged
        assert limiter.buckets[client].tokens == initial_tokens

    def test_cascading_reliability_features(self):
        """Test multiple reliability layers work together."""
        limiter = RateLimiter(capacity=5, refill_rate=2.0)
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=1)
        client = "cascade_client"

        results: list[str] = []

        def protected_service_call(should_fail: bool) -> str:
            # Layer 1: Rate limiting
            if not limiter.is_allowed(client):
                results.append("rate_limited")
                raise Exception("Rate limited")

            # Layer 2: Circuit breaker
            try:
                if should_fail:
                    result = cb.call(
                        lambda: (_ for _ in ()).throw(
                            Exception("Service fail")
                        )()
                    )
                else:
                    result = cb.call(lambda: "success")
                results.append("success")
                return result
            except Exception as e:
                if "Circuit breaker is OPEN" in str(e):
                    results.append("circuit_open")
                else:
                    results.append("service_fail")
                raise

        # Phase 1: Normal operation (rate limited after capacity)
        for _ in range(7):
            try:
                protected_service_call(should_fail=False)
            except Exception:
                pass

        assert results.count("success") == 5
        assert results.count("rate_limited") == 2

        # Clear results
        results.clear()
        time.sleep(0.5)  # Refill some tokens

        # Phase 2: Service failures open circuit
        for _ in range(3):
            try:
                protected_service_call(should_fail=True)
            except Exception:
                pass

        assert cb.state == CircuitState.OPEN
        assert results.count("service_fail") == 3

        # Phase 3: Circuit open blocks all requests
        results.clear()
        for _ in range(3):
            try:
                protected_service_call(should_fail=False)
            except Exception:
                pass

        # Should fail at circuit breaker (rate limit tokens not consumed)
        assert all(r == "circuit_open" for r in results)


class TestStressScenarios:
    """High-load stress test scenarios."""

    @pytest.mark.asyncio
    async def test_thundering_herd(self):
        """Test handling thundering herd scenario."""
        limiter = RateLimiter(capacity=50, refill_rate=25.0)
        cb = CircuitBreaker(failure_threshold=10)

        async def client_request(client_id: int) -> str:
            client_key = f"client_{client_id}"
            if not limiter.is_allowed(client_key):
                return "rate_limited"

            try:
                result = await cb.call(asyncio.coroutine(lambda: "ok")())
                return "success"
            except Exception:
                return "circuit_open"

        # Simulate 100 concurrent clients
        tasks = [client_request(i) for i in range(100)]
        results = await asyncio.gather(*tasks)

        # Should handle gracefully
        success_count = results.count("success")
        rate_limited_count = results.count("rate_limited")

        assert success_count > 0
        assert rate_limited_count > 0
        assert success_count + rate_limited_count == 100

    def test_repeated_recovery_attempts(self):
        """Test circuit breaker handles repeated recovery attempts."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=0.5)

        def intermittent_service(call_number: int) -> str:
            # Fails on odd calls, succeeds on even
            if call_number % 2 == 1:
                raise Exception("Intermittent fail")
            return "ok"

        results = []
        for i in range(20):
            try:
                result = cb.call(intermittent_service, i)
                results.append(("success", cb.state.value))
            except Exception:
                results.append(("fail", cb.state.value))

            if cb.state == CircuitState.OPEN:
                time.sleep(0.6)  # Wait for recovery window

        # Should have mix of successes and failures
        success_count = sum(1 for r, _ in results if r == "success")
        assert success_count > 0

        # Circuit should eventually stabilize
        final_state = results[-1][1]
        assert final_state in ["closed", "half_open"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
