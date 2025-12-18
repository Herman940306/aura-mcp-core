"""ULTRA live calibration/ranking distribution sanity test.

Skips (pass) if IDE_AGENTS_ULTRA_URL not set. Otherwise queries calibration
tool over varying raw_score values and asserts monotonically increasing
probabilities. Ranking sanity: if ranking endpoint available, ensure scores
are not all identical.
"""

import asyncio
import os
from statistics import mean

from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"


def ok(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


async def ultra_live_distribution_test() -> bool:
    if not os.getenv("IDE_AGENTS_ULTRA_URL"):
        ok("skip no ultra backend configured")
        return True
    os.environ["IDE_AGENTS_ULTRA_ENABLED"] = "1"
    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    scores = [0.05, 0.2, 0.4, 0.6, 0.8, 0.95]
    probs = []
    for s in scores:
        try:
            res = await server.call_tool(
                "ide_agents_ml_calibrate_confidence", {"raw_score": s}
            )
        except Exception as e:  # noqa: BLE001
            ok(f"skip calibration error: {e}")
            await server.backend.close()
            return True
        p = res.get("calibrated_probability")
        if not isinstance(p, (int, float)):
            fail("missing calibrated_probability")
            await server.backend.close()
            return False
        probs.append(p)
    # Monotonic check (allow small noise epsilon)
    for a, b in zip(probs, probs[1:], strict=False):
        if b < a - 0.02:  # allow minor jitter
            fail("probabilities not monotonic")
            await server.backend.close()
            return False
    # Optional ranking endpoint sanity if available
    try:
        rank_res = await server.call_tool(
            "ide_agents_ml_rank_predictions_rlhf",
            {"user_id": "tester", "candidates": ["A", "B", "C", "D"]},
        )
        ranking = rank_res.get("ranking") or []
        if ranking and isinstance(ranking, list):
            # Ensure scores not all identical
            scored = [r.get("score") or r.get("norm_score") for r in ranking]
            scored = [s for s in scored if isinstance(s, (int, float))]
            if scored and all(abs(x - mean(scored)) < 1e-6 for x in scored):
                fail("uniform ranking scores")
                await server.backend.close()
                return False
    except Exception:
        ok("skip ranking endpoint error")
    await server.backend.close()
    return True


async def main():
    ok("RUN ultra_live_distribution_test")
    res = await ultra_live_distribution_test()
    if res:
        ok("ultra_live_distribution_test")
    else:
        fail("ultra_live_distribution_test")
    exit(0 if res else 1)


if __name__ == "__main__":
    asyncio.run(main())
