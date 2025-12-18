"""Schema validation tests.

Checks schemas for required keys and immutability across repeated calls.
"""

from mcp_server.ide_agents_mcp_server import AgentsMCPConfig, AgentsMCPServer


def main() -> None:
    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    names = [
        "ide_agents_command",
        "ide_agents_catalog",
        "ide_agents_resource",
        "ide_agents_prompt",
        "ide_agents_health",
    ]
    all_ok = True
    for n in names:
        s1 = server._tool_input_schema(n)
        s2 = server._tool_input_schema(n)
        if s1 != s2:
            print("Mismatch schema", n)
            all_ok = False
        if not isinstance(s1, dict) or "type" not in s1:
            print("Invalid schema", n)
            all_ok = False
    if all_ok:
        print("✓ schema validation passed")
    else:
        print("✗ schema validation failed")
    import asyncio

    asyncio.run(server.backend.close())
    exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
