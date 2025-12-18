import asyncio
import json
import sys
import threading
import time
from pathlib import Path

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
    cfg.ultra_enabled = True
    server = AgentsMCPServer(cfg)
    # Force fallback by simulating missing ultra_url and no backend semantic (handled automatically if backend not providing)
    ranking = await server._dispatch_tool_call(
        "ide_agents_github_rank_repos", {"query": "python", "limit": 1}
    )
    assert "ranking" in ranking
    print(json.dumps(ranking, indent=2))
    await server.backend.close()


if __name__ == "__main__":
    asyncio.run(run())
