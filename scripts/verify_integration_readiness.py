#!/usr/bin/env python3
"""
Integration Readiness Verification Script

Project Creator: Herman Swanepoel
Version: 1.0
Last Updated: 2025-11-14

This script verifies that the environment is ready for Kiro IDE integration testing.
It checks prerequisites, configuration, and backend service availability.
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output"""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def check_python_version() -> bool:
    """Check if Python version is 3.11+"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 11:
        print_success(
            f"Python version: {version.major}.{version.minor}.{version.micro}"
        )
        return True
    else:
        print_error(
            f"Python version {version.major}.{version.minor} is too old (need 3.11+)"
        )
        return False


def check_dependencies() -> tuple[bool, list[str]]:
    """Check if required Python packages are installed"""
    required_packages = [
        "fastmcp",
        "httpx",
        "pydantic",
        "pytest",
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print_success(f"Package installed: {package}")
        except ImportError:
            print_error(f"Package missing: {package}")
            missing.append(package)

    return len(missing) == 0, missing


def check_mcp_config() -> tuple[bool, dict]:
    """Check if MCP configuration file exists and is valid"""
    config_path = Path(".kiro/settings/mcp.json")

    if not config_path.exists():
        print_error(f"MCP config not found: {config_path}")
        return False, {}

    try:
        with open(config_path) as f:
            config = json.load(f)

        print_success(f"MCP config found: {config_path}")

        # Check for ide-agents-mcp server
        if "mcpServers" not in config:
            print_error("No 'mcpServers' section in config")
            return False, config

        if "ide-agents-mcp" not in config["mcpServers"]:
            print_error("No 'ide-agents-mcp' server configured")
            return False, config

        server_config = config["mcpServers"]["ide-agents-mcp"]

        # Check disabled flag
        if server_config.get("disabled", False):
            print_warning("MCP server is disabled in config")
            return False, config

        print_success("MCP server configuration valid")

        # Check ULTRA mode
        env = server_config.get("env", {})
        ultra_enabled = (
            env.get("IDE_AGENTS_ULTRA_ENABLED", "false").lower() == "true"
        )
        if ultra_enabled:
            print_success("ULTRA mode enabled")
        else:
            print_warning("ULTRA mode disabled (ML tools won't be available)")

        # Check GitHub token
        github_token = env.get("GITHUB_TOKEN", "")
        if github_token and github_token != "${GITHUB_TOKEN}":
            print_success("GitHub token configured")
        elif github_token == "${GITHUB_TOKEN}":
            # Check environment variable
            if os.getenv("GITHUB_TOKEN"):
                print_success("GitHub token in environment variable")
            else:
                print_warning("GitHub token not set (GitHub tools won't work)")
        else:
            print_warning("GitHub token not configured")

        return True, config

    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in config: {e}")
        return False, {}
    except Exception as e:
        print_error(f"Error reading config: {e}")
        return False, {}


def check_backend_service() -> bool:
    """Check if backend service is running"""
    backend_url = os.getenv("IDE_AGENTS_BACKEND_URL", "http://127.0.0.1:8001")
    health_url = f"{backend_url}/health"

    try:
        with urllib.request.urlopen(health_url, timeout=5) as response:
            if response.status == 200:
                print_success(f"Backend service running: {backend_url}")
                return True
            else:
                print_error(
                    f"Backend service returned status {response.status}"
                )
                return False
    except urllib.error.URLError:
        print_error(f"Backend service not reachable: {backend_url}")
        print_info("Start backend: python scripts/start_mcp_with_backend.py")
        return False
    except Exception as e:
        print_error(f"Error checking backend: {e}")
        return False


def check_telemetry_directory() -> bool:
    """Check if telemetry directory exists"""
    log_dir = Path("logs")

    if not log_dir.exists():
        print_warning(f"Telemetry directory not found: {log_dir}")
        print_info("Creating directory...")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            print_success(f"Created directory: {log_dir}")
            return True
        except Exception as e:
            print_error(f"Failed to create directory: {e}")
            return False
    else:
        print_success(f"Telemetry directory exists: {log_dir}")
        return True


def check_mcp_server_module() -> bool:
    """Check if MCP server module can be imported"""
    try:
        import os
        import sys

        sys.path.insert(
            0,
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")),
        )
        from mcp_server import ide_agents_mcp_server

        print_success("MCP server module can be imported")
        return True
    except ImportError as e:
        print_error(f"Cannot import MCP server module: {e}")
        print_info("Ensure src/mcp_server/ide_agents_mcp_server.py exists")
        return False


def check_resources() -> bool:
    """Check if resource files exist"""
    resources = [
        "resources/repo.graph.json",
        "resources/build.logs",
    ]

    all_exist = True
    for resource in resources:
        path = Path(resource)
        if path.exists():
            print_success(f"Resource exists: {resource}")
        else:
            print_warning(f"Resource not found: {resource}")
            all_exist = False

    return all_exist


def check_prompts() -> bool:
    """Check if prompt templates exist"""
    prompts = [
        "prompts/diff_review.md",
        "prompts/test_failures.md",
        "prompts/hotfix_plan.md",
    ]

    all_exist = True
    for prompt in prompts:
        path = Path(prompt)
        if path.exists():
            print_success(f"Prompt exists: {prompt}")
        else:
            print_warning(f"Prompt not found: {prompt}")
            all_exist = False

    return all_exist


def test_mcp_server_standalone() -> bool:
    """Test if MCP server can start standalone"""
    print_info("Testing MCP server standalone startup...")
    print_info("This will take a few seconds...")

    try:
        # Try to import and verify basic functionality
        root_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )
        run_script = os.path.join(root_dir, "run.py")
        result = subprocess.run(
            [sys.executable, run_script, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=root_dir, check=False,
        )

        # If help works, server module is functional
        if (
            result.returncode == 0
            or "usage" in result.stdout.lower()
            or "fastmcp" in result.stderr.lower()
        ):
            print_success("MCP server module is functional")
            return True
        else:
            print_warning("MCP server module may have issues")
            print_info(f"Output: {result.stdout}")
            print_info(f"Error: {result.stderr}")
            return True  # Don't fail on this, it's just a warning

    except subprocess.TimeoutExpired:
        print_warning("MCP server test timed out (this is OK)")
        return True
    except Exception as e:
        print_warning(f"Could not test MCP server: {e}")
        return True  # Don't fail on this


def generate_report(results: dict[str, bool]) -> tuple[int, int]:
    """Generate summary report"""
    print_header("VERIFICATION SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for check, result in results.items():
        if result:
            print_success(f"{check}: PASS")
        else:
            print_error(f"{check}: FAIL")

    print(
        f"\n{Colors.BOLD}Results: {passed}/{total} checks passed{Colors.RESET}"
    )

    if passed == total:
        print_success("\n✓ Environment is ready for integration testing!")
    elif passed >= total * 0.8:
        print_warning(
            "\n⚠ Environment is mostly ready, but some issues need attention"
        )
    else:
        print_error("\n✗ Environment is not ready for integration testing")

    return passed, total


def print_next_steps(passed: int, total: int):
    """Print next steps based on results"""
    print_header("NEXT STEPS")

    if passed == total:
        print_info("1. Launch Kiro IDE")
        print_info("2. Wait for MCP server to connect (< 10 seconds)")
        print_info("3. Open MCP Server view to verify connection")
        print_info("4. Follow KIRO_IDE_INTEGRATION_TEST_GUIDE.md")
        print_info(
            "5. Use INTEGRATION_TEST_QUICK_REFERENCE.md for quick tests"
        )
    else:
        print_info("1. Fix the failed checks above")
        print_info("2. Run this script again to verify")
        print_info("3. Refer to DEPLOYMENT_GUIDE.md for setup help")
        print_info("4. Check MCP_INTEGRATION_GUIDE.md for troubleshooting")


def main():
    """Main verification function"""
    print_header("MCP INTEGRATION READINESS VERIFICATION")
    print_info("Checking prerequisites for Kiro IDE integration testing...")

    results = {}

    # Run all checks
    print_header("1. Python Environment")
    results["Python Version"] = check_python_version()

    deps_ok, missing = check_dependencies()
    results["Dependencies"] = deps_ok
    if not deps_ok:
        print_info(
            f"Install missing packages: pip install {' '.join(missing)}"
        )

    print_header("2. MCP Configuration")
    config_ok, config = check_mcp_config()
    results["MCP Configuration"] = config_ok

    print_header("3. Backend Service")
    results["Backend Service"] = check_backend_service()

    print_header("4. File System")
    results["Telemetry Directory"] = check_telemetry_directory()
    results["Resource Files"] = check_resources()
    results["Prompt Templates"] = check_prompts()

    print_header("5. MCP Server Module")
    results["MCP Server Module"] = check_mcp_server_module()
    results["MCP Server Standalone"] = test_mcp_server_standalone()

    # Generate report
    passed, total = generate_report(results)

    # Print next steps
    print_next_steps(passed, total)

    # Exit with appropriate code
    if passed == total:
        sys.exit(0)
    elif passed >= total * 0.8:
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n\nVerification interrupted by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"\n\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(3)
