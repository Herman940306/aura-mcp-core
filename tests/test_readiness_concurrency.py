"""Concurrency behavior test for readiness caching.

Ensures multiple simultaneous /readyz tool invocations remain stable and
leverage positive readiness cache to avoid excessive backend checks.
"""

import asyncio

import tests.stubs.approval as approval_mod
from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer


async def _ready_call(server: AgentsMCPServer):
    # Disable rate limiting for concurrency window
    approval_mod.rate_limiter.interval = 0.0
    approval_mod.rate_limiter._last.clear()
    return await server.call_tool("ide_agents_readyz", {})


NUM_CALLS = 20
LATENCY_SPREAD_LIMIT = 300  # ms


async def readiness_concurrency() -> bool:
    cfg = AgentsMCPConfig.from_env()
    server = AgentsMCPServer(cfg)
    first = await _ready_call(
        server
    )  # Call to _ready_call with rate limiting disabled
    # Launch concurrent readyz calls
    tasks = [
        asyncio.create_task(_ready_call(server)) for _ in range(NUM_CALLS)
    ]
    results = await asyncio.gather(*tasks)
    statuses = [r.get("status") for r in results]
    latencies: list[int] = []
    for r in results:
        val = r.get("backend_latency_ms")
        if isinstance(val, int):
            latencies.append(val)
    # Basic invariants
    assert all(s in {"ready", "degraded"} for s in statuses), statuses
    assert len(results) == NUM_CALLS
    # Latency stability heuristic: max spread below 300ms (cache + pooling)
    if latencies:
        spread = max(latencies) - min(latencies)
        assert (
            spread < LATENCY_SPREAD_LIMIT
        ), f"Latency spread too high: {spread}ms"
    # If initial state ready and ttl>0 expect cached latency identical
    if first.get("status") == "ready" and cfg.ready_cache_ttl > 0:
        unique_lat = {r.get("backend_latency_ms") for r in results}
        assert (
            len(unique_lat) == 1
        ), f"Expected single cached latency value, got {unique_lat}"
    await server.backend.close()
    return True


async def main():
    ok = await readiness_concurrency()
    print("readiness_concurrency:", ok)


def test_readiness_concurrency():
    """Ensures readiness caching handles concurrent invocations."""
    assert asyncio.run(readiness_concurrency()) is True


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
    asyncio.run(main())
if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
