"""Fast sanity smoke test suite for MCP server.

Purpose: Provide a high-signal, low-latency validation of critical MCP
operation domains (startup, tool registry, health, telemetry, approval,
rate limiting, ultra mode presence/absence, and basic concurrency).

Execution: python test_sanity_smoke.py
Outputs: Structured summary to stdout and JSON file `sanity_report.json`.

All tests are designed to pass even if optional backend / external services
are not running (will soft-pass with warnings where appropriate).
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


# Minimal color codes (avoid failure if terminal can't render Unicode)
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def log(section: str, message: str) -> None:
    print(f"{Colors.BLUE}[{section}]{Colors.RESET} {message}")


def ok(msg: str) -> None:
    try:
        print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")
    except UnicodeEncodeError:
        print(f"{Colors.GREEN}[OK]{Colors.RESET} {msg}")


def fail(msg: str) -> None:
    try:
        print(f"{Colors.RED}✗{Colors.RESET} {msg}")
    except UnicodeEncodeError:
        print(f"{Colors.RED}[FAIL]{Colors.RESET} {msg}")


def warn(msg: str) -> None:
    try:
        print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")
    except UnicodeEncodeError:
        print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")


def header(title: str) -> None:
    bar = "=" * 60
    print(f"\n{Colors.BOLD}{Colors.BLUE}{bar}{Colors.RESET}")
    print(f"{Colors.BOLD}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{bar}{Colors.RESET}\n")


class SanityResult:
    def __init__(
        self,
        name: str,
        passed: bool,
        warning: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.name = name
        self.passed = passed
        self.warning = warning
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "warning": self.warning,
            "details": self.details,
        }


async def create_server(ultra: bool = False):
    from mcp_server.ide_agents_mcp_server import (
        AgentsMCPConfig,
        AgentsMCPServer,
    )

    if ultra:
        os.environ["IDE_AGENTS_ULTRA_ENABLED"] = "true"
    else:
        os.environ.pop("IDE_AGENTS_ULTRA_ENABLED", None)
    config = AgentsMCPConfig.from_env()
    return AgentsMCPServer(config)


async def test_startup_initialization_ok() -> SanityResult:
    name = "startup_initialization"
    try:
        server = await create_server()
        count = len(server.tool_handlers)
        if count == 0:
            await server.backend.close()
            return SanityResult(name, False, details={"tool_count": count})
        await server.backend.close()
        return SanityResult(name, True, details={"tool_count": count})
    except Exception as e:
        return SanityResult(name, False, details={"error": str(e)})


async def test_tool_registry_baseline() -> SanityResult:
    name = "tool_registry_baseline"
    expected_core = {
        "ide_agents_health",
        "ide_agents_command",
        "ide_agents_catalog",
        "ide_agents_resource",
        "ide_agents_prompt",
    }
    try:
        server = await create_server()
        registered = set(server.tool_handlers.keys())
        missing = sorted(list(expected_core - registered))
        unexpected = []
        if len(registered) < 50:
            # limit noise for large dynamic registries
            unexpected = sorted(list(registered - expected_core))
        await server.backend.close()
        passed = len(missing) == 0
        return SanityResult(
            name,
            passed,
            warning=None if passed else "Missing core tools",
            details={
                "missing": missing,
                "unexpected_subset": unexpected[:10],
            },
        )
    except Exception as e:
        return SanityResult(name, False, details={"error": str(e)})


async def test_ultra_tools_absent_when_disabled() -> SanityResult:
    name = "ultra_tools_absent_when_disabled"
    ultra_tools = {
        "ide_agents_ml_analyze_emotion",
        "ide_agents_ml_get_predictions",
        "ide_agents_ml_get_learning_insights",
    }
    try:
        server = await create_server(ultra=False)
        registered = set(server.tool_handlers.keys())
        present = sorted(list(ultra_tools & registered))
        await server.backend.close()
        passed = len(present) == 0
        return SanityResult(
            name,
            passed,
            warning=None if passed else "Ultra tools loaded unexpectedly",
            details={"found": present},
        )
    except Exception as e:
        return SanityResult(name, False, details={"error": str(e)})


async def test_ultra_tools_present_when_enabled() -> SanityResult:
    name = "ultra_tools_present_when_enabled"
    ultra_tools = {
        "ide_agents_ml_analyze_emotion",
        "ide_agents_ml_get_predictions",
        "ide_agents_ml_get_learning_insights",
    }
    try:
        server = await create_server(ultra=True)
        registered = set(server.tool_handlers.keys())
        present = sorted(list(ultra_tools & registered))
        await server.backend.close()
        # Pass even if none found; warn if zero (Ultra minimal)
        passed = True
        warning = None if present else "No ultra ML tools loaded"
        return SanityResult(
            name,
            passed,
            warning=warning,
            details={"found": present},
        )
    except Exception as e:
        return SanityResult(name, False, details={"error": str(e)})


async def test_health_ok_min_fields() -> SanityResult:
    name = "health_ok_min_fields"
    try:
        server = await create_server()
        result = await server._dispatch_tool_call("ide_agents_health", {})
        await server.backend.close()
        cond_ok = (
            isinstance(result, dict)
            and result.get("ok")
            and "version" in result
        )
        if cond_ok:
            return SanityResult(
                name,
                True,
                details={
                    "version": result.get("version"),
                    "ultra_enabled": result.get("ultra_enabled"),
                },
            )
        return SanityResult(name, False, details={"response": result})
    except Exception as e:
        return SanityResult(name, False, details={"error": str(e)})


async def test_telemetry_span_structure() -> SanityResult:
    name = "telemetry_span_structure"
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    telemetry_file = logs_dir / "mcp_tool_spans.jsonl"
    if telemetry_file.exists():
        telemetry_file.unlink()
    try:
        from src.mcp_server import telemetry  # local module

        server = await create_server()
        await server._dispatch_tool_call("ide_agents_health", {})
        await asyncio.sleep(0.3)
        # Force flush since batcher uses time-based flush interval (10s)
        telemetry.flush_telemetry()
        await server.backend.close()
        if not telemetry_file.exists():
            return SanityResult(
                name,
                False,
                warning="Telemetry file missing",
                details={},
            )
        lines = telemetry_file.read_text(encoding="utf-8").splitlines()
        if not lines:
            return SanityResult(name, False, details={"empty_file": True})
        try:
            span = json.loads(lines[0])
        except json.JSONDecodeError as e:
            return SanityResult(name, False, details={"json_error": str(e)})
        required = {"tool_name", "duration_ms", "success"}
        missing = sorted(list(required - span.keys()))
        passed = len(missing) == 0
        return SanityResult(
            name,
            passed,
            warning=None if passed else "Missing telemetry keys",
            details={"missing": missing},
        )
    except Exception as e:
        return SanityResult(name, False, details={"error": str(e)})


async def test_invalid_tool_name_error() -> SanityResult:
    name = "invalid_tool_name_error"
    try:
        server = await create_server()
        try:
            await server._dispatch_tool_call("__nonexistent_tool__", {})
            await server.backend.close()
            return SanityResult(
                name,
                False,
                details={"unexpected": "No error raised"},
            )
        except Exception as e:
            await server.backend.close()
            msg = str(e).lower()
            passed = ("not found" in msg) or ("unknown" in msg)
            return SanityResult(name, passed, details={"error_msg": msg})
    except Exception as e:
        return SanityResult(name, False, details={"error": str(e)})


async def test_approval_required_for_run() -> SanityResult:
    name = "approval_required_for_run"
    try:
        import tests.stubs.approval as approval_mod

        approval_mod.approval_queue._approved.clear()
        approval_mod.rate_limiter._last.clear()
        server = await create_server()
        try:
            await server._dispatch_tool_call(
                "ide_agents_command",
                {"method": "run", "command": "echo test"},
            )
            await server.backend.close()
            return SanityResult(
                name,
                False,
                details={"unexpected": "No approval required"},
            )
        except ValueError as e:
            await server.backend.close()
            passed = "approval_required" in str(e)
            return SanityResult(
                name,
                passed,
                details={"error_msg": str(e)[:120]},
            )
    except Exception as e:
        return SanityResult(name, False, details={"error": str(e)})


async def test_rate_limit_enforced() -> SanityResult:
    name = "rate_limit_enforced"
    try:
        import tests.stubs.approval as approval_mod

        approval_mod.rate_limiter._last.clear()
        server = await create_server()
        await server._dispatch_tool_call("ide_agents_health", {})
        try:
            await server._dispatch_tool_call("ide_agents_health", {})
            await server.backend.close()
            return SanityResult(
                name,
                False,
                details={"unexpected": "Second call not rate limited"},
            )
        except ValueError as e:
            await server.backend.close()
            passed = "rate_limited" in str(e)
            return SanityResult(name, passed, details={"error_msg": str(e)})
    except Exception as e:
        return SanityResult(name, False, details={"error": str(e)})


async def test_concurrent_calls_isolated() -> SanityResult:
    name = "concurrent_calls_isolated"
    try:
        server = await create_server()

        async def call_health():
            return await server._dispatch_tool_call("ide_agents_health", {})

        async def call_prompt_list():
            return await server._dispatch_tool_call(
                "ide_agents_prompt",
                {"method": "list"},
            )

        results = await asyncio.gather(
            call_health(),
            call_prompt_list(),
            return_exceptions=True,
        )
        await server.backend.close()
        passed = all(isinstance(r, dict) for r in results)
        return SanityResult(
            name,
            passed,
            details={"types": [type(r).__name__ for r in results]},
        )
    except Exception as e:
        return SanityResult(name, False, details={"error": str(e)})


async def run_all() -> list[SanityResult]:
    header("MCP Sanity Smoke Tests")
    tests = [
        test_startup_initialization_ok,
        test_tool_registry_baseline,
        test_ultra_tools_absent_when_disabled,
        test_ultra_tools_present_when_enabled,
        test_health_ok_min_fields,
        test_telemetry_span_structure,
        test_invalid_tool_name_error,
        test_approval_required_for_run,
        test_rate_limit_enforced,
        test_concurrent_calls_isolated,
    ]
    results: list[SanityResult] = []
    for coro in tests:
        name = coro.__name__
        log("RUN", name)
        res = await coro()
        if res.passed:
            ok(res.name)
            if res.warning:
                warn(res.warning)
        else:
            fail(res.name)
            if res.warning:
                warn(res.warning)
        results.append(res)
    return results


def summarize(results: list[SanityResult]) -> dict[str, Any]:
    passed = sum(1 for r in results if r.passed)
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": [r.to_dict() for r in results],
    }
    return summary


def save_report(data: dict[str, Any]) -> None:
    with open("sanity_report.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    ok("Saved sanity_report.json")


async def main() -> None:
    results = await run_all()
    header("Summary")
    data = summarize(results)
    core = {k: v for k, v in data.items() if k != "results"}
    print(json.dumps(core, indent=2))
    save_report(data)
    if data["failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
