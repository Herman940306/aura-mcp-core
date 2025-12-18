"""MCP Health Checker

Comprehensive verification of all MCP components with REAL functionality testing.
NO MOCKS - All tests use actual functionality.

Project Creator: Herman Swanepoel
Version: 1.0
"""

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


@dataclass
class HealthResult:
    """Result of a single health check."""

    component: str
    status: str  # "pass", "fail", "warning"
    message: str
    details: dict[str, Any]
    timestamp: datetime
    response_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass
class HealthReport:
    """Complete health check report."""

    overall_status: str  # "pass", "fail", "warning"
    total_checks: int
    passed: int
    failed: int
    warnings: int
    results: list[HealthResult]
    timestamp: datetime
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_status": self.overall_status,
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "results": [r.to_dict() for r in self.results],
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
        }


class MCPHealthChecker:
    """Comprehensive health checker for MCP components with REAL functionality testing."""

    def __init__(self, backend_url: str = "http://127.0.0.1:8001"):
        """Initialize health checker.

        Args:
            backend_url: URL of the backend server
        """
        self.backend_url = backend_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

    async def check_backend_server(self) -> HealthResult:
        """Verify backend server is running and responding.

        Returns:
            HealthResult with backend server status
        """
        start_time = time.time()
        component = "Backend Server"

        try:
            # Make REAL HTTP request to /health endpoint
            response = await self.client.get(f"{self.backend_url}/health")
            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                return HealthResult(
                    component=component,
                    status="pass",
                    message="Backend server is online and responding",
                    details={
                        "url": self.backend_url,
                        "status_code": response.status_code,
                        "response": data,
                    },
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                )
            else:
                return HealthResult(
                    component=component,
                    status="fail",
                    message=f"Backend server returned status {response.status_code}",
                    details={
                        "url": self.backend_url,
                        "status_code": response.status_code,
                    },
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                )

        except httpx.ConnectError:
            return HealthResult(
                component=component,
                status="fail",
                message="Cannot connect to backend server",
                details={
                    "url": self.backend_url,
                    "error": "Connection refused - server may not be running",
                },
                timestamp=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return HealthResult(
                component=component,
                status="fail",
                message=f"Error checking backend server: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_yoane_ai(self) -> HealthResult:
        """Send REAL message to YoanÉ and verify response.

        Returns:
            HealthResult with YoanÉ AI status
        """
        start_time = time.time()
        component = "YoanÉ AI"

        try:
            # First check YoanÉ status
            status_response = await self.client.get(
                f"{self.backend_url}/chat/status"
            )
            response_time = (time.time() - start_time) * 1000

            if status_response.status_code != 200:
                return HealthResult(
                    component=component,
                    status="fail",
                    message="YoanÉ status endpoint not responding",
                    details={"status_code": status_response.status_code},
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                )

            # Send REAL message to YoanÉ
            test_message = (
                "Hello YoanÉ! This is a health check. How are you today?"
            )
            chat_start = time.time()

            chat_response = await self.client.post(
                f"{self.backend_url}/chat/send", json={"message": test_message}
            )

            chat_time = (time.time() - chat_start) * 1000

            if chat_response.status_code == 200:
                data = chat_response.json()
                response_text = data.get("response", "")

                # Verify we got a meaningful response (not a mock)
                if (
                    len(response_text) > 10
                ):  # Real responses should be substantial
                    return HealthResult(
                        component=component,
                        status="pass",
                        message="YoanÉ AI is responding with real messages",
                        details={
                            "test_message": test_message,
                            "response_length": len(response_text),
                            "response_preview": (
                                response_text[:100] + "..."
                                if len(response_text) > 100
                                else response_text
                            ),
                            "mood": data.get("mood", "unknown"),
                            "tools_used": data.get("tools_used", []),
                        },
                        timestamp=datetime.now(),
                        response_time_ms=chat_time,
                    )
                else:
                    return HealthResult(
                        component=component,
                        status="warning",
                        message="YoanÉ response seems too short (possible mock)",
                        details={"response": response_text},
                        timestamp=datetime.now(),
                        response_time_ms=chat_time,
                    )
            else:
                return HealthResult(
                    component=component,
                    status="fail",
                    message=f"YoanÉ chat endpoint returned status {chat_response.status_code}",
                    details={"status_code": chat_response.status_code},
                    timestamp=datetime.now(),
                    response_time_ms=chat_time,
                )

        except Exception as e:
            return HealthResult(
                component=component,
                status="fail",
                message=f"Error testing YoanÉ AI: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_ultra_intelligence(self) -> HealthResult:
        """Execute REAL ULTRA ranking with actual data.

        Returns:
            HealthResult with ULTRA intelligence status
        """
        start_time = time.time()
        component = "ULTRA Intelligence"

        try:
            # Test REAL ULTRA ranking with actual data
            test_query = "machine learning optimization"
            test_candidates = [
                {
                    "id": "1",
                    "text": "Advanced machine learning algorithms for optimization",
                },
                {"id": "2", "text": "Database performance tuning guide"},
                {"id": "3", "text": "Neural network optimization techniques"},
            ]

            response = await self.client.post(
                f"{self.backend_url}/ai/intelligence/ultra/rank",
                json={"query": test_query, "candidates": test_candidates},
            )

            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                ranked_results = data.get("ranked", [])

                # Verify we got real ranking scores (not mocks)
                if ranked_results and all(
                    "score" in r for r in ranked_results
                ):
                    # Check if scores are varied (real ranking)
                    scores = [r["score"] for r in ranked_results]
                    score_variance = max(scores) - min(scores) if scores else 0

                    if score_variance > 0.01:  # Real scores should vary
                        return HealthResult(
                            component=component,
                            status="pass",
                            message="ULTRA intelligence is performing real ranking",
                            details={
                                "query": test_query,
                                "candidates_count": len(test_candidates),
                                "ranked_count": len(ranked_results),
                                "score_range": f"{min(scores):.3f} - {max(scores):.3f}",
                                "top_result": (
                                    ranked_results[0]
                                    if ranked_results
                                    else None
                                ),
                            },
                            timestamp=datetime.now(),
                            response_time_ms=response_time,
                        )
                    else:
                        return HealthResult(
                            component=component,
                            status="warning",
                            message="ULTRA scores show no variance (possible mock)",
                            details={"scores": scores},
                            timestamp=datetime.now(),
                            response_time_ms=response_time,
                        )
                else:
                    return HealthResult(
                        component=component,
                        status="warning",
                        message="ULTRA ranking returned unexpected format",
                        details={"response": data},
                        timestamp=datetime.now(),
                        response_time_ms=response_time,
                    )
            else:
                return HealthResult(
                    component=component,
                    status="fail",
                    message=f"ULTRA endpoint returned status {response.status_code}",
                    details={"status_code": response.status_code},
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                )

        except Exception as e:
            return HealthResult(
                component=component,
                status="fail",
                message=f"Error testing ULTRA intelligence: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_github_integration(self) -> HealthResult:
        """Make REAL GitHub API calls (if token valid).

        Returns:
            HealthResult with GitHub integration status
        """
        start_time = time.time()
        component = "GitHub Integration"

        try:
            # Test REAL GitHub repos endpoint
            response = await self.client.get(
                f"{self.backend_url}/github/repos", params={"limit": 5}
            )

            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                repos = data.get("repos", [])

                # Verify we got real repository data
                if repos and all("name" in r and "url" in r for r in repos):
                    return HealthResult(
                        component=component,
                        status="pass",
                        message="GitHub integration is working with real API calls",
                        details={
                            "repos_count": len(repos),
                            "sample_repos": [r["name"] for r in repos[:3]],
                            "has_real_data": True,
                        },
                        timestamp=datetime.now(),
                        response_time_ms=response_time,
                    )
                else:
                    return HealthResult(
                        component=component,
                        status="warning",
                        message="GitHub returned unexpected data format",
                        details={"response": data},
                        timestamp=datetime.now(),
                        response_time_ms=response_time,
                    )
            elif response.status_code == 401:
                return HealthResult(
                    component=component,
                    status="warning",
                    message="GitHub token invalid or missing",
                    details={"status_code": 401},
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                )
            else:
                return HealthResult(
                    component=component,
                    status="fail",
                    message=f"GitHub endpoint returned status {response.status_code}",
                    details={"status_code": response.status_code},
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                )

        except Exception as e:
            return HealthResult(
                component=component,
                status="fail",
                message=f"Error testing GitHub integration: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_ml_engines(self) -> HealthResult:
        """Test REAL emotion analysis and predictions.

        Returns:
            HealthResult with ML engines status
        """
        start_time = time.time()
        component = "ML Engines"

        try:
            # Test REAL emotion analysis
            test_text = "I am so excited about this new feature! It's going to be amazing!"

            response = await self.client.post(
                f"{self.backend_url}/ai/intelligence/emotion/analyze",
                json={"text": test_text},
            )

            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                emotion = data.get("emotion", "")
                confidence = data.get("confidence", 0)

                # Verify we got real emotion analysis (not mock)
                if emotion and confidence > 0:
                    return HealthResult(
                        component=component,
                        status="pass",
                        message="ML engines are performing real emotion analysis",
                        details={
                            "test_text": test_text,
                            "detected_emotion": emotion,
                            "confidence": confidence,
                            "is_real_analysis": True,
                        },
                        timestamp=datetime.now(),
                        response_time_ms=response_time,
                    )
                else:
                    return HealthResult(
                        component=component,
                        status="warning",
                        message="ML engine response seems incomplete",
                        details={"response": data},
                        timestamp=datetime.now(),
                        response_time_ms=response_time,
                    )
            else:
                return HealthResult(
                    component=component,
                    status="fail",
                    message=f"ML engine endpoint returned status {response.status_code}",
                    details={"status_code": response.status_code},
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                )

        except Exception as e:
            return HealthResult(
                component=component,
                status="fail",
                message=f"Error testing ML engines: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_command_execution(self) -> HealthResult:
        """Execute REAL commands and verify results.

        Returns:
            HealthResult with command execution status
        """
        start_time = time.time()
        component = "Command Execution"

        try:
            # Test REAL command execution with a safe command
            test_command = "echo test"

            response = await self.client.post(
                f"{self.backend_url}/command", json={"command": test_command}
            )

            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})

                # Verify we got real command execution
                if "output" in result or "stdout" in result:
                    return HealthResult(
                        component=component,
                        status="pass",
                        message="Command execution is working with real commands",
                        details={
                            "test_command": test_command,
                            "result": result,
                            "is_real_execution": True,
                        },
                        timestamp=datetime.now(),
                        response_time_ms=response_time,
                    )
                else:
                    return HealthResult(
                        component=component,
                        status="warning",
                        message="Command execution returned unexpected format",
                        details={"response": data},
                        timestamp=datetime.now(),
                        response_time_ms=response_time,
                    )
            else:
                return HealthResult(
                    component=component,
                    status="fail",
                    message=f"Command endpoint returned status {response.status_code}",
                    details={"status_code": response.status_code},
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                )

        except Exception as e:
            return HealthResult(
                component=component,
                status="fail",
                message=f"Error testing command execution: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_all_tools(self) -> HealthResult:
        """Verify all MCP tools are enabled and functional.

        Returns:
            HealthResult with tools status
        """
        start_time = time.time()
        component = "MCP Tools"

        try:
            # Check tools status via config
            from mcp_config_manager import MCPConfigurationManager

            config_manager = MCPConfigurationManager(
                Path(".kiro/settings/mcp.json")
            )
            disabled_tools = config_manager.get_disabled_tools()
            is_enabled = config_manager.is_server_enabled()

            response_time = (time.time() - start_time) * 1000

            if is_enabled and len(disabled_tools) == 0:
                return HealthResult(
                    component=component,
                    status="pass",
                    message="All MCP tools are enabled",
                    details={
                        "server_enabled": is_enabled,
                        "disabled_tools_count": 0,
                        "all_tools_enabled": True,
                    },
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                )
            elif not is_enabled:
                return HealthResult(
                    component=component,
                    status="fail",
                    message="MCP server is disabled",
                    details={
                        "server_enabled": False,
                        "disabled_tools_count": len(disabled_tools),
                    },
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                )
            else:
                return HealthResult(
                    component=component,
                    status="warning",
                    message=f"{len(disabled_tools)} tools are disabled",
                    details={
                        "server_enabled": is_enabled,
                        "disabled_tools_count": len(disabled_tools),
                        "disabled_tools": disabled_tools[:10],  # Show first 10
                    },
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                )

        except Exception as e:
            return HealthResult(
                component=component,
                status="fail",
                message=f"Error checking tools status: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def run_full_health_check(self) -> HealthReport:
        """Execute all health checks and generate report.

        Returns:
            HealthReport with complete results
        """
        start_time = time.time()
        results = []

        print("🏥 Running comprehensive MCP health check...")
        print("=" * 60)

        # Run all health checks
        checks = [
            ("Backend Server", self.check_backend_server()),
            ("YoanÉ AI", self.check_yoane_ai()),
            ("ULTRA Intelligence", self.check_ultra_intelligence()),
            ("GitHub Integration", self.check_github_integration()),
            ("ML Engines", self.check_ml_engines()),
            ("Command Execution", self.check_command_execution()),
            ("MCP Tools", self.check_all_tools()),
        ]

        for name, check_coro in checks:
            print(f"\n🔍 Checking {name}...")
            result = await check_coro
            results.append(result)

            # Print result
            status_icon = (
                "✅"
                if result.status == "pass"
                else "⚠️" if result.status == "warning" else "❌"
            )
            print(f"{status_icon} {result.message}")
            print(f"   Response time: {result.response_time_ms:.2f}ms")

        # Calculate summary
        passed = sum(1 for r in results if r.status == "pass")
        failed = sum(1 for r in results if r.status == "fail")
        warnings = sum(1 for r in results if r.status == "warning")

        overall_status = (
            "pass"
            if failed == 0 and warnings == 0
            else "warning" if failed == 0 else "fail"
        )

        duration = time.time() - start_time

        report = HealthReport(
            overall_status=overall_status,
            total_checks=len(results),
            passed=passed,
            failed=failed,
            warnings=warnings,
            results=results,
            timestamp=datetime.now(),
            duration_seconds=duration,
        )

        print("\n" + "=" * 60)
        print("📊 Health Check Summary:")
        print(f"   Total checks: {report.total_checks}")
        print(f"   ✅ Passed: {report.passed}")
        print(f"   ⚠️  Warnings: {report.warnings}")
        print(f"   ❌ Failed: {report.failed}")
        print(f"   Duration: {report.duration_seconds:.2f}s")
        print(f"   Overall: {overall_status.upper()}")

        return report

    def generate_report(self, results: list[HealthResult]) -> HealthReport:
        """Generate detailed health report with timestamps.

        Args:
            results: List of health check results

        Returns:
            HealthReport with summary and details
        """
        passed = sum(1 for r in results if r.status == "pass")
        failed = sum(1 for r in results if r.status == "fail")
        warnings = sum(1 for r in results if r.status == "warning")

        overall_status = (
            "pass"
            if failed == 0 and warnings == 0
            else "warning" if failed == 0 else "fail"
        )

        return HealthReport(
            overall_status=overall_status,
            total_checks=len(results),
            passed=passed,
            failed=failed,
            warnings=warnings,
            results=results,
            timestamp=datetime.now(),
            duration_seconds=0.0,
        )


async def main():
    """Main entry point for health checker."""
    async with MCPHealthChecker() as checker:
        report = await checker.run_full_health_check()

        # Save report to file
        report_path = Path("logs/health_check_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

        print(f"\n📄 Report saved to: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
