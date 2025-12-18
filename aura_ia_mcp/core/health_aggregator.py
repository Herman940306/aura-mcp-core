"""Health check aggregator for monitoring backend services."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class HealthStatus:
    """Health status for a service."""

    healthy: bool
    latency_ms: float
    last_check: float
    error: str | None = None


class HealthAggregator:
    """Aggregate health checks from multiple services."""

    def __init__(self, cache_ttl: int = 30):
        """
        Initialize health aggregator.

        Args:
            cache_ttl: Cache time-to-live in seconds
        """
        self.cache_ttl = cache_ttl
        self.cache: dict[str, HealthStatus] = {}
        self.checks: dict[str, callable] = {}

    def register(self, name: str, check_func: callable) -> None:
        """Register a health check function."""
        self.checks[name] = check_func

    async def check_all(self, force: bool = False) -> dict[str, HealthStatus]:
        """
        Check all registered services.

        Args:
            force: Force fresh checks, ignore cache

        Returns:
            Dictionary of service names to health statuses
        """
        now = time.time()
        results = {}

        # Collect checks to run
        checks_to_run = []
        for name, check_func in self.checks.items():
            # Use cache if available and fresh
            if not force and name in self.cache:
                cached = self.cache[name]
                if (now - cached.last_check) < self.cache_ttl:
                    results[name] = cached
                    continue

            checks_to_run.append((name, check_func))

        # Run checks concurrently
        if checks_to_run:
            check_results = await asyncio.gather(
                *[self._run_check(name, func) for name, func in checks_to_run],
                return_exceptions=True,
            )

            for (name, _), result in zip(
                checks_to_run, check_results, strict=False
            ):
                if isinstance(result, Exception):
                    status = HealthStatus(
                        healthy=False,
                        latency_ms=0.0,
                        last_check=now,
                        error=str(result),
                    )
                else:
                    status = result

                self.cache[name] = status
                results[name] = status

        return results

    async def _run_check(
        self, name: str, check_func: callable
    ) -> HealthStatus:
        """Run a single health check."""
        start = time.time()

        try:
            is_healthy = await check_func()
            latency = (time.time() - start) * 1000  # Convert to ms

            return HealthStatus(
                healthy=is_healthy, latency_ms=latency, last_check=time.time()
            )
        except Exception as e:
            return HealthStatus(
                healthy=False,
                latency_ms=0.0,
                last_check=time.time(),
                error=str(e),
            )

    def get_overall_status(self) -> dict[str, Any]:
        """Get overall system health status."""
        if not self.cache:
            return {"status": "unknown", "services": {}}

        all_healthy = all(status.healthy for status in self.cache.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "services": {
                name: {
                    "healthy": status.healthy,
                    "latency_ms": status.latency_ms,
                    "error": status.error,
                }
                for name, status in self.cache.items()
            },
        }
