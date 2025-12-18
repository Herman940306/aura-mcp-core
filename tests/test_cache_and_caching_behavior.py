"""Cache behavior tests.

Validates resource and prompt caching TTL does not immediately reload after
first access and schema caching returns consistent objects.
"""

import asyncio
from pathlib import Path
from typing import Any


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def ok(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


async def fetch(server, name: str, args: dict[str, Any]):
    return await server._dispatch_tool_call(name, args)


async def test_resource_cache() -> bool:
    from mcp_server import approval as approval_mod
    from mcp_server.ide_agents_mcp_server import (
        AgentsMCPConfig,
        AgentsMCPServer,
    )

    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    first = await fetch(
        server,
        "ide_agents_resource",
        {"method": "get", "name": "repo.graph"},
    )
    p = Path(server._resources_dir / "repo.graph.json")
    original = p.read_text(encoding="utf-8")
    # Append harmless whitespace that keeps JSON valid
    p.write_text(original + " \n", encoding="utf-8")
    # Clear rate limiter and wait to avoid rate_limited error
    approval_mod.rate_limiter._last.clear()
    await asyncio.sleep(0.35)
    second = await fetch(
        server,
        "ide_agents_resource",
        {"method": "get", "name": "repo.graph"},
    )
    p.write_text(original, encoding="utf-8")
    await server.backend.close()
    return first.get("content") == second.get("content")


async def test_prompt_cache() -> bool:
    from mcp_server import approval as approval_mod
    from mcp_server.ide_agents_mcp_server import (
        AgentsMCPConfig,
        AgentsMCPServer,
    )

    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    first = await fetch(
        server,
        "ide_agents_prompt",
        {"method": "get", "name": "/diff_review"},
    )
    p = Path(server._prompts_dir / "diff_review.md")
    original = p.read_text(encoding="utf-8")
    # Append harmless whitespace to keep markdown content structure
    p.write_text(original + " \n", encoding="utf-8")
    approval_mod.rate_limiter._last.clear()
    await asyncio.sleep(0.35)
    second = await fetch(
        server,
        "ide_agents_prompt",
        {"method": "get", "name": "/diff_review"},
    )
    p.write_text(original, encoding="utf-8")
    await server.backend.close()
    return first.get("content") == second.get("content")


async def test_schema_cache_consistency() -> bool:
    from mcp_server.ide_agents_mcp_server import (
        AgentsMCPConfig,
        AgentsMCPServer,
    )

    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    s1 = server._tool_input_schema("ide_agents_command")
    s2 = server._tool_input_schema("ide_agents_command")
    await server.backend.close()
    return s1 is s2 or s1 == s2


async def main():
    tests = [
        ("resource_cache", test_resource_cache),
        ("prompt_cache", test_prompt_cache),
        ("schema_cache_consistency", test_schema_cache_consistency),
    ]
    passed = 0
    for name, fn in tests:
        try:
            ok(f"RUN {name}")
            res = await fn()
            if res:
                ok(name)
                passed += 1
            else:
                fail(name)
        except Exception as e:
            fail(f"{name} error: {e}")
    total = len(tests)
    print(f"\nResult: {passed}/{total} passed")
    exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
