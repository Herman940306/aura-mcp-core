import asyncio
import json
import sys
import threading
import time
from pathlib import Path

# Ensure src package path available
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer
from mcp_server.real_backend_server import run_server as backend_run

_backend_started = False


def _ensure_backend():
    global _backend_started
    if _backend_started:
        return
    th = threading.Thread(
        target=backend_run,
        kwargs={"host": "127.0.0.1", "port": 8001},
        daemon=True,
    )
    th.start()
    _backend_started = True
    time.sleep(0.2)


async def run():
    cfg = AgentsMCPConfig.from_env()
    _ensure_backend()
    server = AgentsMCPServer(cfg)
    health = await server._dispatch_tool_call("ide_agents_health", {})
    ready = await server._dispatch_tool_call("ide_agents_readyz", {})
    assert health.get("ok") is True
    assert "backend_ok" in health
    assert ready.get("telemetry_writable") in (True, False)
    assert "backend_latency_ms" in ready
    await server.backend.close()
    print("health:", json.dumps(health, indent=2))
    print("readyz:", json.dumps(ready, indent=2))


if __name__ == "__main__":
    asyncio.run(run())
