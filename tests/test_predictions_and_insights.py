import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
import threading
import time

from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer
from mcp_server.real_backend_server import run_server as backend_run

_started = False


def ensure_backend():
    global _started
    if _started:
        return
    th = threading.Thread(
        target=backend_run,
        kwargs={"host": "127.0.0.1", "port": 8001},
        daemon=True,
    )
    th.start()
    _started = True
    time.sleep(0.3)


async def run():
    ensure_backend()
    cfg = AgentsMCPConfig.from_env()
    cfg.ultra_enabled = True
    server = AgentsMCPServer(cfg)
    preds = await server.call_tool(
        "ide_agents_ml_get_predictions", {"context": "dev_user"}
    )
    insights = await server.call_tool(
        "ide_agents_ml_get_learning_insights", {"context": "dev_user"}
    )
    assert preds.get("predictions") and isinstance(
        preds.get("predictions"), list
    )
    assert insights.get("insights") and isinstance(
        insights.get("insights"), list
    )
    print(json.dumps({"predictions": preds, "insights": insights}, indent=2))
    await server.shutdown()


if __name__ == "__main__":
    asyncio.run(run())
