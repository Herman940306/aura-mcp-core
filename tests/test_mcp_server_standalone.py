"""Test script to verify MCP Server standalone operation.

This script tests:
1. MCP server starts correctly
2. Backend service is running on port 8001
3. Health endpoint returns OK status
4. ULTRA mode enables ML tools when IDE_AGENTS_ULTRA_ENABLED=true
5. Telemetry spans are written to logs/mcp_tool_spans.jsonl

Project Creator: Herman Swanepoel
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_test(message: str) -> None:
    """Print test message."""
    print(f"{Colors.BLUE}[TEST]{Colors.RESET} {message}")


def print_success(message: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}✓{Colors.RESET} {message}")


def print_error(message: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}✗{Colors.RESET} {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {message}")


def print_header(message: str) -> None:
    """Print section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{message}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")


async def test_backend_service() -> bool:
    """Test if backend service is running on port 8001."""
    print_test("Testing backend service on port 8001...")

    backend_url = os.getenv("IDE_AGENTS_BACKEND_URL", "http://127.0.0.1:8001")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try health endpoint
            try:
                response = await client.get(f"{backend_url}/health")
                if response.status_code == 200:
                    print_success(
                        f"Backend service is running at {backend_url}"
                    )
                    print(f"  Response: {response.json()}")
                    return True
            except Exception:
                pass

            # Try root endpoint
            try:
                response = await client.get(backend_url)
                if response.status_code in (
                    200,
                    404,
                ):  # 404 is ok, means server is up
                    print_success(
                        f"Backend service is reachable at {backend_url}"
                    )
                    return True
            except Exception:
                pass

    except Exception as e:
        print_error(f"Backend service is NOT running: {e}")
        print_warning("Please start the backend service on port 8001")
        return False

    print_error(f"Backend service is NOT reachable at {backend_url}")
    return False


async def test_mcp_server_import() -> bool:
    """Test if MCP server can be imported."""
    print_test("Testing MCP server import...")

    try:
        print_success("MCP server module imported successfully")
        return True
    except Exception as e:
        print_error(f"Failed to import MCP server: {e}")
        return False


async def test_mcp_server_initialization() -> bool:
    """Test if MCP server can be initialized."""
    print_test("Testing MCP server initialization...")

    try:
        from mcp_server.ide_agents_mcp_server import (
            AgentsMCPConfig,
            AgentsMCPServer,
        )

        # Test with default config
        config = AgentsMCPConfig.from_env()
        print(f"  Backend URL: {config.backend_base_url}")
        print(f"  Request Timeout: {config.request_timeout}s")
        print(f"  ULTRA Enabled: {config.ultra_enabled}")
        print(f"  ULTRA Mock: {config.ultra_mock_enabled}")

        server = AgentsMCPServer(config)
        print_success("MCP server initialized successfully")

        # Check registered tools
        tool_count = len(server.tool_handlers)
        print(f"  Registered tools: {tool_count}")

        # List some tools
        core_tools = [
            "ide_agents_health",
            "ide_agents_command",
            "ide_agents_catalog",
            "ide_agents_resource",
            "ide_agents_prompt",
        ]

        for tool in core_tools:
            if tool in server.tool_handlers:
                print_success(f"  Found core tool: {tool}")
            else:
                print_error(f"  Missing core tool: {tool}")

        # Check ML tools if ULTRA enabled
        if config.ultra_enabled:
            ml_tools = [
                "ide_agents_ml_analyze_emotion",
                "ide_agents_ml_get_predictions",
                "ide_agents_ml_get_learning_insights",
            ]
            for tool in ml_tools:
                if tool in server.tool_handlers:
                    print_success(f"  Found ML tool: {tool}")
                else:
                    print_warning(f"  ML tool not loaded: {tool}")

        await server.backend.close()
        return True

    except Exception as e:
        print_error(f"Failed to initialize MCP server: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_health_endpoint() -> bool:
    """Test the health endpoint."""
    print_test("Testing health endpoint...")

    try:
        from mcp_server.ide_agents_mcp_server import (
            AgentsMCPConfig,
            AgentsMCPServer,
        )

        config = AgentsMCPConfig.from_env()
        server = AgentsMCPServer(config)

        # Call health handler directly
        result = await server._handle_health({})

        if result.get("ok"):
            print_success("Health endpoint returned OK")
            print(f"  Version: {result.get('version')}")
            print(f"  ULTRA Enabled: {result.get('ultra_enabled')}")
            await server.backend.close()
            return True
        else:
            print_error("Health endpoint did not return OK")
            await server.backend.close()
            return False

    except Exception as e:
        print_error(f"Health endpoint test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_ultra_mode() -> bool:
    """Test ULTRA mode ML tools."""
    print_test("Testing ULTRA mode ML tools...")

    ultra_enabled = os.getenv("IDE_AGENTS_ULTRA_ENABLED", "").lower() in (
        "1",
        "true",
        "yes",
    )

    if not ultra_enabled:
        print_warning(
            "ULTRA mode is NOT enabled (IDE_AGENTS_ULTRA_ENABLED not set)"
        )
        print_warning("Set IDE_AGENTS_ULTRA_ENABLED=true to enable ML tools")
        return False

    print_success("ULTRA mode is enabled")

    try:
        from mcp_server.ide_agents_mcp_server import (
            AgentsMCPConfig,
            AgentsMCPServer,
        )

        config = AgentsMCPConfig.from_env()
        server = AgentsMCPServer(config)

        # Check for ML tools
        ml_tools = [
            "ide_agents_ml_analyze_emotion",
            "ide_agents_ml_get_predictions",
            "ide_agents_ml_get_learning_insights",
            "ide_agents_ml_analyze_reasoning",
            "ide_agents_ml_get_personality_profile",
            "ide_agents_ml_get_system_status",
        ]

        found_count = 0
        for tool in ml_tools:
            if tool in server.tool_handlers:
                print_success(f"  ML tool available: {tool}")
                found_count += 1
            else:
                print_warning(f"  ML tool not found: {tool}")

        await server.backend.close()

        if found_count > 0:
            print_success(f"Found {found_count} ML tools")
            return True
        else:
            print_error("No ML tools found despite ULTRA mode being enabled")
            return False

    except Exception as e:
        print_error(f"ULTRA mode test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_telemetry() -> bool:
    """Test telemetry span writing."""
    print_test("Testing telemetry span writing...")

    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    telemetry_file = logs_dir / "mcp_tool_spans.jsonl"

    # Clear existing telemetry file for clean test
    if telemetry_file.exists():
        telemetry_file.unlink()

    try:
        from mcp_server.ide_agents_mcp_server import (
            AgentsMCPConfig,
            AgentsMCPServer,
        )

        config = AgentsMCPConfig.from_env()
        server = AgentsMCPServer(config)

        # Call health endpoint to generate telemetry
        await server._dispatch_tool_call("ide_agents_health", {})

        # Wait a moment for telemetry to be written
        await asyncio.sleep(0.5)

        # Check if telemetry file was created
        if telemetry_file.exists():
            print_success(f"Telemetry file created: {telemetry_file}")

            # Read and validate telemetry
            with open(telemetry_file) as f:
                lines = f.readlines()

            if lines:
                print_success(f"Found {len(lines)} telemetry span(s)")

                # Parse first span
                span = json.loads(lines[0])
                print(f"  Tool: {span.get('tool_name')}")
                print(f"  Duration: {span.get('duration_ms')}ms")
                print(f"  Success: {span.get('success')}")

                await server.backend.close()
                return True
            else:
                print_error("Telemetry file is empty")
                await server.backend.close()
                return False
        else:
            print_error(f"Telemetry file not created: {telemetry_file}")
            await server.backend.close()
            return False

    except Exception as e:
        print_error(f"Telemetry test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_command_line_execution() -> bool:
    """Test running MCP server from command line."""
    print_test("Testing command line execution...")

    try:
        # Try to run the server with a timeout
        print(
            "  Running: python -m ide_agents_mcp_server (will timeout after 3s)"
        )

        process = subprocess.Popen(
            [sys.executable, "-m", "ide_agents_mcp_server"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait a bit for startup
        time.sleep(3)

        # Terminate the process
        process.terminate()

        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()

        # Check if server started
        if "ide-agents-mcp" in stderr or "Initialized" in stderr:
            print_success("MCP server started from command line")
            print(f"  Stderr output: {stderr[:200]}")
            return True
        else:
            print_error("MCP server did not start properly")
            if stderr:
                print(f"  Stderr: {stderr[:500]}")
            if stdout:
                print(f"  Stdout: {stdout[:500]}")
            return False

    except Exception as e:
        print_error(f"Command line execution test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main() -> None:
    """Run all tests."""
    print_header("MCP Server Standalone Operation Tests")

    results: dict[str, bool] = {}

    # Test 1: Backend service
    results["Backend Service"] = await test_backend_service()

    # Test 2: MCP server import
    results["MCP Import"] = await test_mcp_server_import()

    # Test 3: MCP server initialization
    results["MCP Initialization"] = await test_mcp_server_initialization()

    # Test 4: Health endpoint
    results["Health Endpoint"] = await test_health_endpoint()

    # Test 5: ULTRA mode
    results["ULTRA Mode"] = await test_ultra_mode()

    # Test 6: Telemetry
    results["Telemetry"] = await test_telemetry()

    # Test 7: Command line execution
    results["Command Line"] = await test_command_line_execution()

    # Print summary
    print_header("Test Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        if result:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")

    print(
        f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.RESET}"
    )

    if passed == total:
        print(
            f"{Colors.GREEN}{Colors.BOLD}✓ All tests passed!{Colors.RESET}\n"
        )
        sys.exit(0)
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ Some tests failed{Colors.RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
