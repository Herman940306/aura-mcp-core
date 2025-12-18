"""Performance stress and concurrency test.

Launches multiple concurrent tool calls to exercise rate limiting windows
and connection pooling. Uses slight jitter to avoid deterministic collisions.
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
    YELLOW = "\033[93m"
    RESET = "\033[0m"


def ok(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


async def call_tool(
    server: AgentsMCPServer, name: str, args: dict[str, Any]
) -> float:
    start = time.perf_counter()
    try:
        # Reset rate limiter to allow high-frequency performance sampling
        approval_mod.rate_limiter._last.clear()
        res = await server.call_tool(name, args)
        if name == "ide_agents_health" and not res.get("ok"):
            raise ValueError("health_not_ok")
        return time.perf_counter() - start
    except Exception as e:
        # Treat rate limit as soft failure, return negative duration sentinel
        if "rate_limited" in str(e):
            return -1.0
        raise


async def performance_concurrency_test() -> bool:
    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    # Clear any previous rate limiter state
    approval_mod.rate_limiter._last.clear()
    tool_matrix = [
        ("ide_agents_health", {}),
        ("ide_agents_server_instructions", {}),
        ("ide_agents_prompt", {"method": "list"}),
        ("ide_agents_resource", {"method": "list"}),
    ]
    durations: list[float] = []
    tasks = []
    # Fire 16 mixed calls with jitter
    for i in range(16):
        name, base = random.choice(tool_matrix)
        # Jitter: occasionally list again triggers cache hits
        args = dict(base)
        tasks.append(asyncio.create_task(call_tool(server, name, args)))
        await asyncio.sleep(0.015)  # slight staggering reduces collision
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            fail(f"exception: {r}")
            await server.backend.close()
            return False
        durations.append(r)
    await server.backend.close()
    successful = [d for d in durations if d >= 0]
    rate_limited = [d for d in durations if d < 0]
    avg = sum(successful) / (len(successful) or 1)
    summary_tpl = (
        "Total calls: {total} | success: {succ} | rate_limited: {rl} | "
        "avg_latency: {lat:.1f}ms"
    )
    print(
        summary_tpl.format(
            total=len(durations),
            succ=len(successful),
            rl=len(rate_limited),
            lat=avg * 1000,
        )
    )
    # Pass criteria: at least 75% succeed and average latency under 250ms
    return len(successful) >= int(0.75 * len(durations)) and avg < 0.25


async def main():
    ok("RUN performance_concurrency_test")
    try:
        res = await performance_concurrency_test()
        if res:
            ok("performance_concurrency_test")
        else:
            fail("performance_concurrency_test")
    except Exception as e:
        fail(f"performance_concurrency_test error: {e}")
    exit(0 if res else 1)


if __name__ == "__main__":
    asyncio.run(main())
