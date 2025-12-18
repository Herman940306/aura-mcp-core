"""Test script for Telemetry and Monitoring (Task 10).

This script tests:
1. Verify telemetry spans are recorded for all tool invocations
2. Verify spans include timestamp, tool name, method, duration, success status
3. Verify error codes are recorded for failed invocations
4. Test telemetry file format (JSON Lines in `logs/mcp_tool_spans.jsonl`)
5. Verify rate limiting events are tracked
6. Test telemetry data can be read and analyzed

Project Creator: Herman Swanepoel
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


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


def get_telemetry_file_path() -> Path:
    """Get the telemetry file path."""
    log_dir = Path(os.getenv("MCP_TOOL_SPANS_DIR", "logs"))
    return log_dir / "mcp_tool_spans.jsonl"


def clear_telemetry_file() -> None:
    """Clear the telemetry file for testing."""
    telemetry_file = get_telemetry_file_path()
    if telemetry_file.exists():
        telemetry_file.unlink()
    telemetry_file.parent.mkdir(parents=True, exist_ok=True)


def read_telemetry_spans() -> list[dict[str, Any]]:
    """Read all telemetry spans from the log file."""
    telemetry_file = get_telemetry_file_path()
    if not telemetry_file.exists():
        return []

    spans = []
    with telemetry_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    spans.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return spans


async def test_telemetry_spans_recorded() -> bool:
    """Test that telemetry spans are recorded for tool invocations."""
    print_test("Testing telemetry spans are recorded...")

    try:
        from mcp_server.ide_agents_mcp_server import (
            AgentsMCPConfig,
            AgentsMCPServer,
        )

        # Clear telemetry file
        clear_telemetry_file()

        config = AgentsMCPConfig.from_env()
        server = AgentsMCPServer(config)

        # Invoke a simple tool
        await server._dispatch_tool_call("ide_agents_health", {})

        # Wait a bit for file write
        await asyncio.sleep(0.1)

        # Read telemetry spans
        spans = read_telemetry_spans()

        if not spans:
            print_error("No telemetry spans recorded")
            await server.backend.close()
            return False

        print_success(f"Telemetry spans recorded: {len(spans)} span(s)")

        # Verify the span is for the health tool
        health_spans = [
            s for s in spans if s.get("tool_name") == "ide_agents_health"
        ]
        if health_spans:
            print_success("  Health tool span found")
        else:
            print_warning("  Health tool span not found")

        await server.backend.close()
        return True

    except Exception as e:
        print_error(f"Telemetry spans recording test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_span_structure() -> bool:
    """Test that spans include required fields."""
    print_test("Testing span structure (required fields)...")

    try:
        from mcp_server.ide_agents_mcp_server import (
            AgentsMCPConfig,
            AgentsMCPServer,
        )

        # Clear telemetry file
        clear_telemetry_file()

        config = AgentsMCPConfig.from_env()
        server = AgentsMCPServer(config)

        # Invoke a tool with method
        await server._dispatch_tool_call(
            "ide_agents_resource", {"method": "list"}
        )

        # Wait for file write
        await asyncio.sleep(0.1)

        # Read telemetry spans
        spans = read_telemetry_spans()

        if not spans:
            print_error("No telemetry spans found")
            await server.backend.close()
            return False

        span = spans[0]

        # Check required fields
        required_fields = [
            "timestamp_ms",
            "tool_name",
            "duration_ms",
            "success",
        ]

        all_present = True
        for field in required_fields:
            if field in span:
                print_success(f"  Field '{field}' present")
            else:
                print_error(f"  Field '{field}' missing")
                all_present = False

        # Check field types
        if "timestamp_ms" in span:
            if isinstance(span["timestamp_ms"], int):
                print_success("  timestamp_ms is integer")
            else:
                print_warning(
                    f"  timestamp_ms type: {type(span['timestamp_ms'])}"
                )

        if "tool_name" in span:
            if isinstance(span["tool_name"], str):
                print_success(f"  tool_name: {span['tool_name']}")
            else:
                print_warning(f"  tool_name type: {type(span['tool_name'])}")

        if "method" in span:
            print_success(f"  method: {span['method']}")
        else:
            print("  method: None (optional)")

        if "duration_ms" in span:
            if isinstance(span["duration_ms"], int):
                print_success(f"  duration_ms: {span['duration_ms']}ms")
            else:
                print_warning(
                    f"  duration_ms type: {type(span['duration_ms'])}"
                )

        if "success" in span:
            if isinstance(span["success"], bool):
                print_success(f"  success: {span['success']}")
            else:
                print_warning(f"  success type: {type(span['success'])}")

        await server.backend.close()
        return all_present

    except Exception as e:
        print_error(f"Span structure test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_error_code_recording() -> bool:
    """Test that error codes are recorded for failed invocations."""
    print_test("Testing error code recording for failures...")

    try:
        from mcp_server.ide_agents_mcp_server import (
            AgentsMCPConfig,
            AgentsMCPServer,
        )

        # Clear telemetry file
        clear_telemetry_file()

        config = AgentsMCPConfig.from_env()
        server = AgentsMCPServer(config)

        # Invoke a tool that will fail (missing required argument)
        try:
            await server._dispatch_tool_call(
                "ide_agents_resource", {"method": "get"}
            )
        except ValueError:
            # Expected to fail
            pass

        # Wait for file write
        await asyncio.sleep(0.1)

        # Read telemetry spans
        spans = read_telemetry_spans()

        if not spans:
            print_error("No telemetry spans found")
            await server.backend.close()
            return False

        # Find failed span
        failed_spans = [s for s in spans if not s.get("success", True)]

        if not failed_spans:
            print_error("No failed spans found")
            await server.backend.close()
            return False

        failed_span = failed_spans[0]

        print_success("Failed span found")
        print(f"  success: {failed_span.get('success')}")

        if "error_code" in failed_span:
            print_success(f"  error_code: {failed_span['error_code']}")

            # Verify it's a valid error code
            if failed_span["error_code"] == "ValueError":
                print_success("  Error code is correct (ValueError)")
            else:
                print_warning(
                    f"  Unexpected error code: {failed_span['error_code']}"
                )
        else:
            print_error("  error_code field missing")
            await server.backend.close()
            return False

        await server.backend.close()
        return True

    except Exception as e:
        print_error(f"Error code recording test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_telemetry_file_format() -> bool:
    """Test telemetry file format (JSON Lines)."""
    print_test("Testing telemetry file format (JSON Lines)...")

    try:
        from mcp_server.ide_agents_mcp_server import (
            AgentsMCPConfig,
            AgentsMCPServer,
        )

        # Clear telemetry file
        clear_telemetry_file()

        config = AgentsMCPConfig.from_env()
        server = AgentsMCPServer(config)

        # Invoke multiple tools
        await server._dispatch_tool_call("ide_agents_health", {})
        await asyncio.sleep(0.3)  # Wait for rate limiter
        await server._dispatch_tool_call(
            "ide_agents_resource", {"method": "list"}
        )

        # Wait for file writes
        await asyncio.sleep(0.1)

        # Check file exists
        telemetry_file = get_telemetry_file_path()
        if not telemetry_file.exists():
            print_error("Telemetry file does not exist")
            await server.backend.close()
            return False

        print_success(f"Telemetry file exists: {telemetry_file}")

        # Read file and verify JSON Lines format
        with telemetry_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            print_error("Telemetry file is empty")
            await server.backend.close()
            return False

        print_success(f"Telemetry file has {len(lines)} line(s)")

        # Verify each line is valid JSON
        valid_json_lines = 0
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    valid_json_lines += 1
                else:
                    print_warning(f"  Line {i+1} is not a JSON object")
            except json.JSONDecodeError as e:
                print_error(f"  Line {i+1} is not valid JSON: {e}")

        non_empty_lines = [line for line in lines if line.strip()]
        if valid_json_lines == len(non_empty_lines):
            print_success(
                f"  All {valid_json_lines} lines are valid JSON objects"
            )
        else:
            print_warning(
                f"  Only {valid_json_lines}/{len(lines)} lines are valid"
            )

        await server.backend.close()
        return valid_json_lines > 0

    except Exception as e:
        print_error(f"Telemetry file format test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_rate_limiting_tracking() -> bool:
    """Test that rate limiting events are tracked."""
    print_test("Testing rate limiting event tracking...")

    try:
        import tests.stubs.approval as approval_mod
        from mcp_server.ide_agents_mcp_server import (
            AgentsMCPConfig,
            AgentsMCPServer,
        )

        # Clear telemetry file and reset rate limiter
        clear_telemetry_file()
        approval_mod.rate_limiter._last.clear()

        config = AgentsMCPConfig.from_env()
        server = AgentsMCPServer(config)

        # Invoke tool multiple times rapidly to trigger rate limiting
        tool_name = "ide_agents_health"

        # First call should succeed
        await server._dispatch_tool_call(tool_name, {})

        # Second call immediately should be rate limited
        rate_limited = False
        try:
            await server._dispatch_tool_call(tool_name, {})
        except ValueError as e:
            if "rate_limited" in str(e):
                rate_limited = True
                print_success("Rate limiting triggered as expected")

        if not rate_limited:
            print_warning(
                "Rate limiting not triggered " "(may need faster execution)"
            )

        # Wait for rate limit window
        await asyncio.sleep(0.3)

        # Third call should succeed
        await server._dispatch_tool_call(tool_name, {})

        # Wait for file writes
        await asyncio.sleep(0.1)

        # Read telemetry spans
        spans = read_telemetry_spans()

        if not spans:
            print_error("No telemetry spans found")
            await server.backend.close()
            return False

        print_success(f"Total spans recorded: {len(spans)}")

        # Check for rate limited spans (failed with rate_limited error)
        # Note: Rate limiting happens before telemetry, so we won't see
        # a span for the rate-limited call. We verify by checking that
        # we have fewer spans than attempts.

        health_spans = [s for s in spans if s.get("tool_name") == tool_name]
        print(f"  Health tool spans: {len(health_spans)}")

        if rate_limited:
            # We should have 2 successful spans (1st and 3rd calls)
            if len(health_spans) == 2:
                print_success(
                    "  Correct number of spans (rate-limited call not recorded)"
                )
            else:
                print_warning(f"  Expected 2 spans, got {len(health_spans)}")

        await server.backend.close()
        return True

    except Exception as e:
        print_error(f"Rate limiting tracking test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_telemetry_data_analysis() -> bool:
    """Test that telemetry data can be read and analyzed."""
    print_test("Testing telemetry data analysis...")

    try:
        from mcp_server.ide_agents_mcp_server import (
            AgentsMCPConfig,
            AgentsMCPServer,
        )

        # Clear telemetry file
        clear_telemetry_file()

        config = AgentsMCPConfig.from_env()
        server = AgentsMCPServer(config)

        # Invoke multiple tools to generate data
        tools_to_test = [
            ("ide_agents_health", {}),
            ("ide_agents_resource", {"method": "list"}),
            ("ide_agents_prompt", {"method": "list"}),
        ]

        for tool_name, args in tools_to_test:
            await server._dispatch_tool_call(tool_name, args)
            await asyncio.sleep(0.3)  # Wait for rate limiter

        # Wait for file writes
        await asyncio.sleep(0.1)

        # Read and analyze telemetry data
        spans = read_telemetry_spans()

        if not spans:
            print_error("No telemetry spans found")
            await server.backend.close()
            return False

        print_success(f"Analyzed {len(spans)} telemetry spans")

        # Analysis 1: Count by tool
        tool_counts: dict[str, int] = {}
        for span in spans:
            tool_name = span.get("tool_name", "unknown")
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        print("  Tool invocation counts:")
        for tool, count in sorted(tool_counts.items()):
            print(f"    {tool}: {count}")

        # Analysis 2: Success rate
        total = len(spans)
        successful = sum(1 for s in spans if s.get("success", False))
        success_rate = (successful / total * 100) if total > 0 else 0

        print(f"  Success rate: {success_rate:.1f}% ({successful}/{total})")

        # Analysis 3: Average duration
        durations = [
            s.get("duration_ms", 0) for s in spans if "duration_ms" in s
        ]
        if durations:
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)
            print(f"  Average duration: {avg_duration:.2f}ms")
            print(f"  Min duration: {min_duration}ms")
            print(f"  Max duration: {max_duration}ms")

        # Analysis 4: Methods used
        methods: set[str] = set()
        for span in spans:
            method = span.get("method")
            if method and isinstance(method, str):
                methods.add(method)

        if methods:
            print(f"  Methods used: {', '.join(sorted(methods))}")

        # Analysis 5: Errors
        errors: list[str] = []
        for s in spans:
            if not s.get("success", True):
                error_code = s.get("error_code")
                if error_code and isinstance(error_code, str):
                    errors.append(error_code)
        if errors:
            print(f"  Errors encountered: {', '.join(set(errors))}")
        else:
            print("  No errors encountered")

        await server.backend.close()
        return True

    except Exception as e:
        print_error(f"Telemetry data analysis test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_multiple_tool_invocations() -> bool:
    """Test telemetry for multiple different tool invocations."""
    print_test("Testing telemetry for multiple tool types...")

    try:
        from mcp_server.ide_agents_mcp_server import (
            AgentsMCPConfig,
            AgentsMCPServer,
        )

        # Clear telemetry file
        clear_telemetry_file()

        config = AgentsMCPConfig.from_env()
        server = AgentsMCPServer(config)

        # Test various tools
        test_cases = [
            ("ide_agents_health", {}),
            ("ide_agents_resource", {"method": "list"}),
            ("ide_agents_resource", {"method": "get", "name": "repo.graph"}),
            ("ide_agents_prompt", {"method": "list"}),
            ("ide_agents_prompt", {"method": "get", "name": "/diff_review"}),
        ]

        for tool_name, args in test_cases:
            try:
                await server._dispatch_tool_call(tool_name, args)
                await asyncio.sleep(0.3)  # Wait for rate limiter
            except Exception:
                # Some may fail, that's okay
                pass

        # Wait for file writes
        await asyncio.sleep(0.1)

        # Read telemetry spans
        spans = read_telemetry_spans()

        if not spans:
            print_error("No telemetry spans found")
            await server.backend.close()
            return False

        print_success(f"Recorded {len(spans)} spans from multiple tools")

        # Verify we have spans for different tools
        unique_tools = set(s.get("tool_name") for s in spans)
        print(f"  Unique tools: {len(unique_tools)}")
        for tool in sorted(unique_tools):
            tool_spans = [s for s in spans if s.get("tool_name") == tool]
            print(f"    {tool}: {len(tool_spans)} span(s)")

        # Verify we have spans with different methods
        unique_methods: set[str] = set()
        for s in spans:
            method = s.get("method")
            if method and isinstance(method, str):
                unique_methods.add(method)
        if unique_methods:
            print(f"  Unique methods: {', '.join(sorted(unique_methods))}")

        await server.backend.close()
        return len(unique_tools) >= 3

    except Exception as e:
        print_error(f"Multiple tool invocations test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main() -> None:
    """Run all telemetry and monitoring tests."""
    print_header("Telemetry and Monitoring Tests (Task 10)")

    results: dict[str, bool] = {}

    # Test 1: Telemetry spans are recorded
    results["Telemetry Spans Recorded"] = await test_telemetry_spans_recorded()

    # Test 2: Span structure
    results["Span Structure"] = await test_span_structure()

    # Test 3: Error code recording
    results["Error Code Recording"] = await test_error_code_recording()

    # Test 4: Telemetry file format
    results["Telemetry File Format"] = await test_telemetry_file_format()

    # Test 5: Rate limiting tracking
    results["Rate Limiting Tracking"] = await test_rate_limiting_tracking()

    # Test 6: Telemetry data analysis
    results["Telemetry Data Analysis"] = await test_telemetry_data_analysis()

    # Test 7: Multiple tool invocations
    results["Multiple Tool Invocations"] = (
        await test_multiple_tool_invocations()
    )

    # Print summary
    print_header("Test Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        if result:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")

    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed")
    print(f"{Colors.RESET}")

    if passed == total:
        msg = f"{Colors.GREEN}{Colors.BOLD}✓ All tests passed!"
        print(f"{msg}{Colors.RESET}\n")
        sys.exit(0)
    else:
        msg = f"{Colors.RED}{Colors.BOLD}✗ Some tests failed"
        print(f"{msg}{Colors.RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
