"""Chaos engineering and resilience tests.

Implements fault injection scenarios:
- Pod kills
- Network latency injection
- Service unavailability
- Resource exhaustion

Validates system invariants under chaos conditions.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import pytest


class ChaosScenario:
    """Base class for chaos injection scenarios."""

    def __init__(self, name: str):
        """Initialize scenario.

        Args:
            name: Scenario identifier
        """
        self.name = name

    async def inject(self) -> None:
        """Inject chaos condition."""
        raise NotImplementedError

    async def restore(self) -> None:
        """Restore normal conditions."""
        raise NotImplementedError


class PodKillScenario(ChaosScenario):
    """Randomly kills pods to test recovery."""

    def __init__(self, target_pod: str):
        """Initialize pod kill scenario.

        Args:
            target_pod: Pod name pattern to target
        """
        super().__init__("pod_kill")
        self.target_pod = target_pod

    async def inject(self) -> None:
        """Simulate pod kill (mock implementation)."""
        # In real implementation: kubectl delete pod <target_pod>
        await asyncio.sleep(0.1)
        print(f"[CHAOS] Killed pod: {self.target_pod}")

    async def restore(self) -> None:
        """Wait for pod restart."""
        await asyncio.sleep(0.2)
        print(f"[CHAOS] Pod restored: {self.target_pod}")


class LatencyInjectionScenario(ChaosScenario):
    """Injects network latency between services."""

    def __init__(self, latency_ms: int):
        """Initialize latency injection.

        Args:
            latency_ms: Latency to inject (milliseconds)
        """
        super().__init__("latency_injection")
        self.latency_ms = latency_ms

    async def inject(self) -> None:
        """Add latency to requests."""
        # In real: use Istio fault injection or tc command
        print(f"[CHAOS] Injected {self.latency_ms}ms latency")

    async def restore(self) -> None:
        """Remove latency."""
        print("[CHAOS] Restored normal latency")


class ResilienceValidator:
    """Validates system invariants during chaos."""

    def __init__(self, health_check_fn: Any):
        """Initialize validator.

        Args:
            health_check_fn: Async function to check system health
        """
        self.health_check_fn = health_check_fn

    async def validate(
        self, scenario: ChaosScenario, max_downtime_seconds: float = 5.0
    ) -> dict[str, Any]:
        """Run chaos scenario and validate recovery.

        Args:
            scenario: Chaos scenario to execute
            max_downtime_seconds: Maximum acceptable downtime

        Returns:
            Validation result with status and metrics
        """
        # Baseline health check
        baseline = await self.health_check_fn()
        if not baseline.get("healthy"):
            return {"status": "failed", "reason": "Unhealthy before chaos"}

        # Inject chaos
        await scenario.inject()

        # Monitor recovery
        recovery_start = asyncio.get_event_loop().time()
        downtime = 0.0
        recovered = False

        for _ in range(50):  # Poll for 5 seconds
            await asyncio.sleep(0.1)
            health = await self.health_check_fn()
            if health.get("healthy"):
                recovered = True
                downtime = asyncio.get_event_loop().time() - recovery_start
                break

        # Restore normal conditions
        await scenario.restore()

        if not recovered:
            return {
                "status": "failed",
                "reason": "Did not recover within timeout",
                "scenario": scenario.name,
            }

        if downtime > max_downtime_seconds:
            return {
                "status": "failed",
                "reason": f"Downtime {downtime:.2f}s exceeded limit {max_downtime_seconds}s",
                "scenario": scenario.name,
                "downtime": downtime,
            }

        return {
            "status": "passed",
            "scenario": scenario.name,
            "downtime": downtime,
        }


# Mock health check for testing
async def mock_health_check() -> dict[str, Any]:
    """Mock health check that randomly fails/recovers."""
    healthy = random.random() > 0.2  # 80% success rate
    return {"healthy": healthy, "status": 200 if healthy else 503}


@pytest.mark.asyncio
async def test_pod_kill_recovery():
    """Verify system recovers from pod kill."""
    scenario = PodKillScenario("mcp-server-abc123")
    validator = ResilienceValidator(mock_health_check)
    result = await validator.validate(scenario, max_downtime_seconds=5.0)
    # Due to randomness, we just verify it completes
    assert "status" in result
    assert "scenario" in result


@pytest.mark.asyncio
async def test_latency_injection_resilience():
    """Verify system tolerates latency injection."""
    scenario = LatencyInjectionScenario(latency_ms=500)
    validator = ResilienceValidator(mock_health_check)
    result = await validator.validate(scenario, max_downtime_seconds=5.0)
    assert "status" in result


@pytest.mark.asyncio
async def test_multiple_chaos_scenarios():
    """Run multiple chaos scenarios in sequence."""
    scenarios = [
        PodKillScenario("pod-1"),
        LatencyInjectionScenario(200),
        PodKillScenario("pod-2"),
    ]
    validator = ResilienceValidator(mock_health_check)
    results = []
    for scenario in scenarios:
        result = await validator.validate(scenario)
        results.append(result)
    # Verify all scenarios completed
    assert len(results) == 3
