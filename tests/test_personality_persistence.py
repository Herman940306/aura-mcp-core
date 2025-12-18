import asyncio
import json
import shutil
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer

data_dir = Path("data")
profile_file = data_dir / "personality_profile.json"


async def run():
    if profile_file.exists():
        shutil.copy(profile_file, profile_file.with_suffix(".bak"))
        profile_file.unlink()
    cfg = AgentsMCPConfig.from_env()
    cfg.ultra_enabled = True
    server = AgentsMCPServer(cfg)
    before = await server.call_tool(
        "ide_agents_ml_get_personality_profile", {}
    )
    upd = await server.call_tool(
        "ide_agents_ml_adjust_personality", {"traits": ["focused", "calm"]}
    )
    after = await server.call_tool("ide_agents_ml_get_personality_profile", {})
    assert before["profile"].get("traits") == []
    assert set(after["profile"].get("traits", [])) == {"focused", "calm"}
    print(
        json.dumps({"before": before, "after": after, "update": upd}, indent=2)
    )
    await server.shutdown()


if __name__ == "__main__":
    asyncio.run(run())
