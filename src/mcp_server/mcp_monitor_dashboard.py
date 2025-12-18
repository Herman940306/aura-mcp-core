"""MCP Monitor Dashboard - Real-time monitoring for KIRO_MCP Server

This dashboard provides live monitoring of:
- MCP Server health and status
- Backend AI service connectivity
- Tool invocation statistics
- Telemetry data analysis
- ULTRA intelligence metrics
- System resource usage

**Project Creator:** Herman Swanepoel
**Version:** 1.0
**Last Updated:** 2025-11-15
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil
    import requests
except ImportError:
    print("Installing required packages...")
    os.system("pip install requests psutil")
    import psutil
    import requests


# Configuration
MCP_HOST = os.getenv("IDE_AGENTS_BACKEND_URL", "http://127.0.0.1:8001")
HEALTH_ENDPOINT = f"{MCP_HOST}/health"
AI_STATUS_ENDPOINT = f"{MCP_HOST}/ai/intelligence/status"
TELEMETRY_FILE = Path("logs/mcp_tool_spans.jsonl")
REFRESH_INTERVAL = 5  # seconds
TIMEOUT = 3


class Colors:
    """ANSI color codes for terminal output"""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def clear_screen():
    """Clear the terminal screen"""
    os.system("cls" if os.name == "nt" else "clear")


def print_header():
    """Print dashboard header"""
    print(f"{Colors.HEADER}{Colors.BOLD}")
    print("=" * 80)
    print("  🚀 KIRO_MCP MONITOR DASHBOARD - GODMODE")
    print("=" * 80)
    print(f"{Colors.ENDC}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Backend: {MCP_HOST}")
    print()


def check_mcp_server() -> dict:
    """Check MCP server health"""
    try:
        r = requests.get(HEALTH_ENDPOINT, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            return {
                "status": "online",
                "data": data,
                "response_time": r.elapsed.total_seconds() * 1000,
            }
        else:
            return {"status": "error", "code": r.status_code}
    except requests.exceptions.ConnectionError:
        return {"status": "offline", "error": "Connection refused"}
    except requests.exceptions.Timeout:
        return {"status": "timeout", "error": "Request timeout"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_ai_system() -> dict:
    """Check AI intelligence system status"""
    try:
        r = requests.get(AI_STATUS_ENDPOINT, timeout=TIMEOUT)
        if r.status_code == 200:
            return {"status": "operational", "data": r.json()}
        else:
            return {"status": "error", "code": r.status_code}
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}


def get_telemetry_stats() -> dict:
    """Analyze telemetry data"""
    if not TELEMETRY_FILE.exists():
        return {"total": 0, "success": 0, "failed": 0, "tools": {}}

    stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "tools": {},
        "avg_duration": 0,
        "recent": [],
    }

    try:
        with open(TELEMETRY_FILE) as f:
            lines = f.readlines()
            total_duration = 0

            for line in lines[-100:]:  # Last 100 entries
                try:
                    span = json.loads(line)
                    stats["total"] += 1

                    if span.get("success", False):
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1

                    tool_name = span.get("tool_name", "unknown")
                    if tool_name not in stats["tools"]:
                        stats["tools"][tool_name] = {
                            "count": 0,
                            "success": 0,
                            "failed": 0,
                        }

                    stats["tools"][tool_name]["count"] += 1
                    if span.get("success", False):
                        stats["tools"][tool_name]["success"] += 1
                    else:
                        stats["tools"][tool_name]["failed"] += 1

                    duration = span.get("duration_ms", 0)
                    total_duration += duration

                except json.JSONDecodeError:
                    continue

            if stats["total"] > 0:
                stats["avg_duration"] = total_duration / stats["total"]

            # Get recent entries
            for line in lines[-5:]:
                try:
                    stats["recent"].append(json.loads(line))
                except:
                    pass

    except Exception as e:
        stats["error"] = str(e)

    return stats


def get_system_resources() -> dict:
    """Get system resource usage"""
    try:
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": (
                psutil.disk_usage("/").percent
                if os.name != "nt"
                else psutil.disk_usage("C:\\").percent
            ),
        }
    except Exception as e:
        return {"error": str(e)}


def print_status_section(title: str, status: dict):
    """Print a status section"""
    print(f"{Colors.BOLD}{title}{Colors.ENDC}")
    print("-" * 80)

    if (
        status.get("status") == "online"
        or status.get("status") == "operational"
    ):
        print(f"{Colors.OKGREEN}✅ ONLINE{Colors.ENDC}")
        if "response_time" in status:
            print(f"   Response Time: {status['response_time']:.2f}ms")
        if "data" in status:
            for key, value in status["data"].items():
                if isinstance(value, dict):
                    print(f"   {key}:")
                    for k, v in value.items():
                        print(f"      {k}: {v}")
                else:
                    print(f"   {key}: {value}")
    elif status.get("status") == "offline":
        print(f"{Colors.FAIL}❌ OFFLINE{Colors.ENDC}")
        print(f"   Error: {status.get('error', 'Unknown')}")
    elif status.get("status") == "timeout":
        print(f"{Colors.WARNING}⏱️  TIMEOUT{Colors.ENDC}")
        print(f"   Error: {status.get('error', 'Request timeout')}")
    elif status.get("status") == "unavailable":
        print(f"{Colors.WARNING}⚠️  UNAVAILABLE{Colors.ENDC}")
        print(f"   Error: {status.get('error', 'Service unavailable')}")
    else:
        print(f"{Colors.FAIL}❌ ERROR{Colors.ENDC}")
        print(f"   Error: {status.get('error', 'Unknown error')}")

    print()


def print_telemetry_section(stats: dict):
    """Print telemetry statistics"""
    print(f"{Colors.BOLD}📊 TELEMETRY STATISTICS{Colors.ENDC}")
    print("-" * 80)

    if stats.get("error"):
        print(
            f"{Colors.WARNING}⚠️  Error reading telemetry: {stats['error']}{Colors.ENDC}"
        )
        print()
        return

    total = stats.get("total", 0)
    success = stats.get("success", 0)
    failed = stats.get("failed", 0)

    if total == 0:
        print(f"{Colors.WARNING}No telemetry data available{Colors.ENDC}")
        print()
        return

    success_rate = (success / total * 100) if total > 0 else 0

    print(f"   Total Invocations: {total}")
    print(
        f"   Success: {Colors.OKGREEN}{success}{Colors.ENDC} | Failed: {Colors.FAIL}{failed}{Colors.ENDC}"
    )
    print(f"   Success Rate: {success_rate:.1f}%")
    print(f"   Avg Duration: {stats.get('avg_duration', 0):.2f}ms")
    print()

    # Top tools
    tools = stats.get("tools", {})
    if tools:
        print(f"   {Colors.BOLD}Top Tools:{Colors.ENDC}")
        sorted_tools = sorted(
            tools.items(), key=lambda x: x[1]["count"], reverse=True
        )[:5]
        for tool_name, tool_stats in sorted_tools:
            tool_success_rate = (
                (tool_stats["success"] / tool_stats["count"] * 100)
                if tool_stats["count"] > 0
                else 0
            )
            print(
                f"      {tool_name}: {tool_stats['count']} calls ({tool_success_rate:.0f}% success)"
            )

    print()


def print_system_resources(resources: dict):
    """Print system resource usage"""
    print(f"{Colors.BOLD}💻 SYSTEM RESOURCES{Colors.ENDC}")
    print("-" * 80)

    if resources.get("error"):
        print(f"{Colors.WARNING}⚠️  Error: {resources['error']}{Colors.ENDC}")
        print()
        return

    cpu = resources.get("cpu_percent", 0)
    memory = resources.get("memory_percent", 0)
    disk = resources.get("disk_percent", 0)

    cpu_color = (
        Colors.OKGREEN
        if cpu < 50
        else Colors.WARNING if cpu < 80 else Colors.FAIL
    )
    memory_color = (
        Colors.OKGREEN
        if memory < 70
        else Colors.WARNING if memory < 85 else Colors.FAIL
    )
    disk_color = (
        Colors.OKGREEN
        if disk < 80
        else Colors.WARNING if disk < 90 else Colors.FAIL
    )

    print(f"   CPU: {cpu_color}{cpu:.1f}%{Colors.ENDC}")
    print(f"   Memory: {memory_color}{memory:.1f}%{Colors.ENDC}")
    print(f"   Disk: {disk_color}{disk:.1f}%{Colors.ENDC}")
    print()


def print_footer():
    """Print dashboard footer"""
    print("-" * 80)
    print(
        f"{Colors.OKCYAN}Press Ctrl+C to exit | Refreshing every {REFRESH_INTERVAL}s{Colors.ENDC}"
    )
    print()


def run_dashboard():
    """Run the monitoring dashboard"""
    print(
        f"{Colors.OKGREEN}Starting KIRO_MCP Monitor Dashboard...{Colors.ENDC}"
    )
    time.sleep(1)

    try:
        while True:
            clear_screen()
            print_header()

            # Check MCP Server
            mcp_status = check_mcp_server()
            print_status_section("🚀 MCP SERVER STATUS", mcp_status)

            # Check AI System
            ai_status = check_ai_system()
            print_status_section("🧠 AI INTELLIGENCE SYSTEM", ai_status)

            # Telemetry Stats
            telemetry_stats = get_telemetry_stats()
            print_telemetry_section(telemetry_stats)

            # System Resources
            resources = get_system_resources()
            print_system_resources(resources)

            print_footer()

            time.sleep(REFRESH_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n{Colors.OKGREEN}Dashboard stopped by user.{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.FAIL}Error: {e}{Colors.ENDC}")
        sys.exit(1)


if __name__ == "__main__":
    run_dashboard()
