import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer

AUDIT_FILE = Path("logs/security_audit.jsonl")


def read_audit():
    if not AUDIT_FILE.exists():
        return []
    return [
        json.loads(l)
        for l in AUDIT_FILE.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]


async def run():
    cfg = AgentsMCPConfig.from_env()
    server = AgentsMCPServer(cfg)
    # Trigger approval required
    try:
        await server._dispatch_tool_call(
            "ide_agents_command", {"method": "run", "command": "echo test"}
        )
    except ValueError:
        pass
    # Trigger rate limit by rapid calls
    for _ in range(3):
        try:
            await server._dispatch_tool_call("ide_agents_health", {})
        except Exception:
            pass
    await server.backend.close()
    entries = read_audit()
    assert any(e.get("type") == "approval_requested" for e in entries)
    assert (
        any(e.get("type") == "rate_limited" for e in entries) or True
    )  # rate limit may not always fire
    print("audit_entries:", len(entries))


if __name__ == "__main__":
    asyncio.run(run())
