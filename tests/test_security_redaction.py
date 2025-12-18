"""Security redaction test.

Ensures sensitive env values do not appear directly in recent log lines.
Heuristic check only.
"""

import os
from pathlib import Path


def main() -> None:
    secret = "TEST_SUPER_SECRET_TOKEN_123"  # synthetic secret
    os.environ["GITHUB_TOKEN"] = secret
    # Initialize logging explicitly
    import mcp_logging

    logger = mcp_logging.MCPLogger.get_logger("mcp.security_test")
    logger.info("Security redaction test start")
    import asyncio

    from mcp_server.ide_agents_mcp_server import (
        AgentsMCPConfig,
        AgentsMCPServer,
    )

    server = AgentsMCPServer(AgentsMCPConfig.from_env())
    asyncio.run(server._dispatch_tool_call("ide_agents_health", {}))
    asyncio.run(server.backend.close())
    log_file = Path("logs/mcp_main.log")
    if not log_file.exists():
        # Force write to create file
        logger.info("Creating main log file for redaction check")
    if not log_file.exists():
        print("✗ main log missing for redaction check")
        exit(1)
    tail = log_file.read_text(encoding="utf-8")[-2000:]
    if secret in tail:
        print("✗ secret leaked in logs")
        exit(1)
    print("✓ redaction heuristic passed")
    exit(0)


if __name__ == "__main__":
    main()
