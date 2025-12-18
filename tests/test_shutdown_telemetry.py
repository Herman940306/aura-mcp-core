import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer


def count_spans(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(
        1 for _ in path.read_text(encoding="utf-8").splitlines() if _.strip()
    )


async def run():
    cfg = AgentsMCPConfig.from_env()
    cfg.ultra_enabled = False
    server = AgentsMCPServer(cfg)
    # invoke a few tools
    await server.call_tool("ide_agents_health", {})
    await server.call_tool("ide_agents_catalog", {"method": "list_entities"})
    spans_file = Path("logs/mcp_tool_spans.jsonl")
    before = count_spans(spans_file)
    await server.shutdown()
    # allow flush
    time.sleep(0.1)
    after = count_spans(spans_file)
    assert after >= before
    print(json.dumps({"before": before, "after": after}, indent=2))


if __name__ == "__main__":
    asyncio.run(run())
