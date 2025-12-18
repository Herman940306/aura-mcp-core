"""Shutdown flush test.

Ensures telemetry flush occurs on server shutdown.
"""

import asyncio
import json
from pathlib import Path


async def main():
    from mcp_server.ide_agents_mcp_server import (
        AgentsMCPConfig,
        AgentsMCPServer,
    )

    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    await server._dispatch_tool_call("ide_agents_health", {})
    await server.shutdown()
    log_file = Path("logs/mcp_tool_spans.jsonl")
    if not log_file.exists():
        print("✗ shutdown flush missing file")
        exit(1)
    lines = log_file.read_text(encoding="utf-8").splitlines()
    if not lines:
        print("✗ shutdown flush empty")
        exit(1)
    first = json.loads(lines[0])
    if "tool_name" in first:
        print("✓ shutdown flush passed")
        exit(0)
    print("✗ shutdown flush invalid span")
    exit(1)


if __name__ == "__main__":
    asyncio.run(main())
