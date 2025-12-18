"""Ultra mode matrix tests.

Verifies tool presence across ULTRA flags (enabled, mock, local).
"""

import asyncio
import os

ULTRA_CORE = {
    "ide_agents_ml_analyze_emotion",
    "ide_agents_ml_get_predictions",
    "ide_agents_ml_get_learning_insights",
}


def banner(title: str) -> None:
    print(f"\n=== {title} ===")


async def collect(ultra: bool, mock: bool, local: bool):
    from mcp_server.ide_agents_mcp_server import (
        AgentsMCPConfig,
        AgentsMCPServer,
    )

    if ultra:
        os.environ["IDE_AGENTS_ULTRA_ENABLED"] = "true"
    else:
        os.environ.pop("IDE_AGENTS_ULTRA_ENABLED", None)
    if mock:
        os.environ["IDE_AGENTS_ULTRA_MOCK"] = "true"
    else:
        os.environ.pop("IDE_AGENTS_ULTRA_MOCK", None)
    if local:
        os.environ["IDE_AGENTS_ULTRA_LOCAL"] = "true"
    else:
        os.environ.pop("IDE_AGENTS_ULTRA_LOCAL", None)
    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    tools = set(server.tool_handlers.keys())
    await server.backend.close()
    return tools


async def run_matrix():
    combos = [
        (False, False, False),
        (True, False, False),
        (True, True, False),
        (True, False, True),
    ]
    results = []
    for ultra, mock, local in combos:
        tools = await collect(ultra, mock, local)
        present = sorted(list(ULTRA_CORE & tools))
        results.append(
            {
                "ultra": ultra,
                "mock": mock,
                "local": local,
                "found": present,
            }
        )
    return results


async def main():
    banner("ULTRA Modes Matrix")
    results = await run_matrix()
    all_ok = True
    for row in results:
        print(row)
        if row["ultra"] and not row["found"]:
            all_ok = False
    if all_ok:
        print("\n✓ Ultra matrix validation passed")
        exit(0)
    else:
        print("\n✗ Ultra matrix validation failed")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
