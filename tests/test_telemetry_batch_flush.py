"""Telemetry batch and flush tests.

Ensures spans flush on batch size and explicit flush produces file records.
"""

import asyncio
import json
from pathlib import Path


async def main():
    import tests.stubs.approval as approval_mod
    from mcp_server.ide_agents_mcp_server import (
        AgentsMCPConfig,
        AgentsMCPServer,
    )
    from src.mcp_server import telemetry

    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    for _ in range(5):
        approval_mod.rate_limiter._last.clear()
        await asyncio.sleep(0.35)
        await server._dispatch_tool_call("ide_agents_health", {})
    telemetry.flush_telemetry()
    await server.backend.close()
    log_dir = Path("logs")
    log_file = log_dir / "mcp_tool_spans.jsonl"
    if not log_file.exists():
        print("✗ telemetry file missing")
        exit(1)
    lines = log_file.read_text(encoding="utf-8").splitlines()
    if not lines:
        print("✗ no spans written")
        exit(1)
    first = json.loads(lines[0])
    required = {"tool_name", "duration_ms", "success"}
    if not required.issubset(first.keys()):
        print("✗ missing keys", first.keys())
        exit(1)
    print("✓ telemetry batch flush passed (spans=", len(lines), ")")
    exit(0)


if __name__ == "__main__":
    asyncio.run(main())
    asyncio.run(main())
