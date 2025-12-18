"""ULTRA semantic validation test (local mock tools).

Enables ULTRA to load ML plugin then exercises local-only tools that do not
hit backend endpoints, validating structure and value ranges.
"""

import asyncio
import os

from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"


def ok(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


async def ultra_semantic_test() -> bool:
    os.environ["IDE_AGENTS_ULTRA_ENABLED"] = "1"
    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    required_tools = {
        "ide_agents_ml_adjust_personality",
        "ide_agents_ml_behavioral_baseline_check",
        "ide_agents_ml_trigger_auto_adaptation",
        "ide_agents_ml_get_ultra_dashboard",
    }
    # Verify registration
    missing = [t for t in required_tools if t not in server.tool_handlers]
    if missing:
        fail(f"missing tools: {missing}")
        await server.backend.close()
        return False

    # Collect results
    personality = await server.call_tool(
        "ide_agents_ml_adjust_personality",
        {
            "personality_type": "analytical",
            "mood": "focused",
            "tone": "neutral",
        },
    )
    baseline = await server.call_tool(
        "ide_agents_ml_behavioral_baseline_check", {"user_id": "tester"}
    )
    adaptation = await server.call_tool(
        "ide_agents_ml_trigger_auto_adaptation", {"reason": "validate"}
    )
    dashboard = await server.call_tool("ide_agents_ml_get_ultra_dashboard", {})
    await server.backend.close()

    # Validate structures
    if personality.get("status") != "simulated":
        fail("personality status invalid")
        return False
    deviation = baseline.get("baseline", {}).get("deviation")
    if not (isinstance(deviation, (int, float)) and 0 <= deviation <= 1):
        fail("baseline deviation out of range")
        return False
    if not adaptation.get("triggered"):
        fail("adaptation not triggered")
        return False
    brier = dashboard.get("confidence_calibration", {}).get("brier_score")
    roc_auc = dashboard.get("confidence_calibration", {}).get("roc_auc")
    if not (isinstance(brier, (int, float)) and 0 <= brier <= 1):
        fail("brier_score invalid")
        return False
    if not (isinstance(roc_auc, (int, float)) and 0 <= roc_auc <= 1):
        fail("roc_auc invalid")
        return False
    return True


async def main():
    ok("RUN ultra_semantic_test")
    res = await ultra_semantic_test()
    if res:
        ok("ultra_semantic_test")
    else:
        fail("ultra_semantic_test")
    exit(0 if res else 1)


if __name__ == "__main__":
    asyncio.run(main())
