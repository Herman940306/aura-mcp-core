"""High-volume performance stress test with latency percentiles.

Issues 200 mixed tool calls concurrently and reports success ratio plus
latency p50/p95/p99. Fails if success < 90% or p99 > 750ms.
"""

import asyncio
import random
import time
from typing import Any

import tests.stubs.approval as approval_mod
from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"


def ok(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


async def call(
    server: AgentsMCPServer, name: str, args: dict[str, Any]
) -> float:
    start = time.perf_counter()
    approval_mod.rate_limiter._last.clear()  # reset each call
    try:
        await server.call_tool(name, args)
        return (time.perf_counter() - start) * 1000.0
    except Exception as e:  # noqa: BLE001
        if "rate_limited" in str(e):
            return -1.0
        return -2.0  # hard failure


async def high_volume_test() -> bool:
    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    tools = [
        ("ide_agents_health", {}),
        ("ide_agents_prompt", {"method": "list"}),
        ("ide_agents_resource", {"method": "list"}),
        ("ide_agents_server_instructions", {}),
    ]
    tasks: list[asyncio.Task] = []
    for _ in range(200):
        name, base = random.choice(tools)
        tasks.append(asyncio.create_task(call(server, name, dict(base))))
    results = await asyncio.gather(*tasks)
    await server.backend.close()
    successes = [r for r in results if r >= 0]
    rate_limited = [r for r in results if r == -1.0]
    failures = [r for r in results if r == -2.0]
    if successes:
        successes_sorted = sorted(successes)

        def pct(p):
            idx = int(p * len(successes_sorted)) - 1
            idx = max(0, min(idx, len(successes_sorted) - 1))
            return successes_sorted[idx]

        p50 = pct(0.50)
        p95 = pct(0.95)
        p99 = pct(0.99)
    else:
        p50 = p95 = p99 = 0.0
    print(
        f"total=200 success={len(successes)} rate_limited={len(rate_limited)} failures={len(failures)} "
        f"p50={p50:.1f}ms p95={p95:.1f}ms p99={p99:.1f}ms"
    )
    # Thresholds
    return len(successes) >= 180 and p99 < 750.0 and len(failures) == 0


async def main():
    ok("RUN high_volume_performance")
    res = await high_volume_test()
    if res:
        ok("high_volume_performance")
    else:
        fail("high_volume_performance")
    exit(0 if res else 1)


if __name__ == "__main__":
    asyncio.run(main())
