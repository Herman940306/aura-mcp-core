import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer


async def run():
    cfg = AgentsMCPConfig.from_env()
    server = AgentsMCPServer(cfg)
    before = await server.call_tool(
        "ide_agents_security_anomalies", {"window_seconds": 3600}
    )
    reload_res = await server.call_tool("ide_agents_reload", {})
    after = await server.call_tool(
        "ide_agents_security_anomalies", {"window_seconds": 3600}
    )
    assert "thresholds" in reload_res
    print(
        json.dumps(
            {
                "before": before.get("trend"),
                "reload": reload_res,
                "after": after.get("trend"),
            },
            indent=2,
        )
    )
    await server.shutdown()


if __name__ == "__main__":
    asyncio.run(run())
