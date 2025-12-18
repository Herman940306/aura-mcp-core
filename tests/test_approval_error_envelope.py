import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer


async def run():
    cfg = AgentsMCPConfig.from_env()
    server = AgentsMCPServer(cfg)
    try:
        await server._dispatch_tool_call(
            "ide_agents_command", {"method": "run", "command": "echo test"}
        )
    except ValueError as e:
        payload = json.loads(str(e))
        assert "error" in payload
        assert payload["error"].get("code") == "approval_required"
        print("approval envelope ok")
    await server.backend.close()


if __name__ == "__main__":
    asyncio.run(run())
