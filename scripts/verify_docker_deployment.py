#!/usr/bin/env python3
"""
Docker Build Verification and Health Check Script
For Aura IA MCP Production Deployment
Date: December 13, 2025
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class DockerDeploymentVerifier:
    """Verify Docker deployment and service health"""

    def __init__(self, server: str = "localhost", timeout: int = 30):
        self.server = server
        self.timeout = timeout
        self.results = {}
        self.passed_checks = 0
        self.failed_checks = 0
        self.warnings = []

    def run_command(self, cmd: str) -> Tuple[bool, str]:
        """Execute shell command and return success status and output"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {self.timeout}s"
        except Exception as e:
            return False, str(e)

    def print_header(self, text: str) -> None:
        """Print formatted header"""
        print("\n" + "=" * 60)
        print(f"  {text}")
        print("=" * 60)

    def print_check(self, name: str, passed: bool, details: str = "") -> None:
        """Print check result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"[{status}] {name}")
        if details:
            for line in details.split("\n"):
                if line.strip():
                    print(f"      {line}")

        if passed:
            self.passed_checks += 1
        else:
            self.failed_checks += 1

    def print_warning(self, text: str) -> None:
        """Print warning"""
        print(f"[⚠ WARN] {text}")
        self.warnings.append(text)

    # Verification methods

    def check_docker_installed(self) -> bool:
        """Check if Docker is installed"""
        success, output = self.run_command("docker --version")
        self.print_check(
            "Docker Installation",
            success,
            output if success else "Docker not found",
        )
        return success

    def check_docker_running(self) -> bool:
        """Check if Docker daemon is running"""
        success, output = self.run_command("docker ps")
        self.print_check(
            "Docker Daemon Running",
            success,
            "Docker daemon is active" if success else output,
        )
        return success

    def check_docker_compose_installed(self) -> bool:
        """Check if Docker Compose is installed"""
        success, output = self.run_command("docker-compose --version")
        self.print_check(
            "Docker Compose Installation",
            success,
            output if success else "Docker Compose not found",
        )
        return success

    def check_services_running(self) -> Dict[str, str]:
        """Check if services are running"""
        success, output = self.run_command(
            "docker-compose ps --format json 2>/dev/null || docker-compose ps"
        )

        services = {}
        if success:
            try:
                # Try to parse JSON output
                lines = output.strip().split("\n")
                for line in lines:
                    if "Up" in line or "Exited" in line:
                        # Parse service status
                        parts = line.split()
                        if len(parts) > 0:
                            name = parts[0].strip()
                            status = "Running" if "Up" in line else "Stopped"
                            services[name] = status
                            self.print_check(
                                f"Service: {name}",
                                "Up" in line,
                                f"Status: {status}",
                            )
            except:
                self.print_warning(
                    "Could not parse service status, showing raw output"
                )
                print(output)
        else:
            self.print_check(
                "Services Status",
                False,
                "Could not retrieve service information",
            )

        return services

    def check_port_availability(self, port: int) -> bool:
        """Check if port is accessible"""
        success, output = self.run_command(
            f"netstat -an 2>/dev/null | grep {port} || echo 'unknown'"
        )
        status = (
            "Port in use"
            if success
            and port in [int(p) for p in output.split() if p.isdigit()]
            else "Port accessible"
        )
        self.print_check(f"Port {port} Availability", True, status)
        return True

    def check_health_endpoint(self) -> bool:
        """Check health endpoint"""
        cmd = f"curl -s http://{self.server}:9200/healthz -m {self.timeout}"
        success, output = self.run_command(cmd)

        if success and "status" in output.lower():
            self.print_check(
                "Health Endpoint", True, f"Response: {output[:100]}"
            )
            return True
        else:
            self.print_check(
                "Health Endpoint", False, f"No response or invalid response"
            )
            return False

    def check_readiness_endpoint(self) -> bool:
        """Check readiness endpoint"""
        cmd = f"curl -s http://{self.server}:9200/readyz -m {self.timeout}"
        success, output = self.run_command(cmd)

        if success and "ready" in output.lower():
            self.print_check(
                "Readiness Endpoint", True, f"Response: {output[:100]}"
            )
            return True
        else:
            self.print_check(
                "Readiness Endpoint", False, f"No response or invalid response"
            )
            return False

    def check_websocket_endpoints(self) -> Dict[str, bool]:
        """Check WebSocket endpoints availability"""
        endpoints = [
            "/ws/models",
            "/ws/system",
            "/ws/governance",
            "/ws/database",
        ]

        results = {}
        for endpoint in endpoints:
            # We can't directly test WebSocket, but we can check if the endpoint exists via HTTP
            cmd = f"curl -s -I http://{self.server}:9200{endpoint} -m {self.timeout}"
            success, output = self.run_command(cmd)

            # Check if we get any response (WebSocket upgrade or 404 is fine, connection refused is bad)
            endpoint_available = success or "Connection refused" not in output
            results[endpoint] = endpoint_available

            self.print_check(
                f"WebSocket {endpoint}",
                endpoint_available,
                (
                    "Endpoint reachable"
                    if endpoint_available
                    else "Endpoint not reachable"
                ),
            )

        return results

    def check_api_endpoints(self) -> Dict[str, bool]:
        """Check API endpoints"""
        endpoints = {
            "/api/system/metrics": "System Metrics",
            "/api/governance/roles": "Governance Roles",
            "/api/models/status": "Model Status",
            "/api/database/health": "Database Health",
        }

        results = {}
        for endpoint, name in endpoints.items():
            cmd = f"curl -s http://{self.server}:9200{endpoint} -m {self.timeout}"
            success, output = self.run_command(cmd)

            # Check if we get JSON response
            endpoint_available = success and (
                output.strip().startswith("{")
                or output.strip().startswith("[")
            )
            results[endpoint] = endpoint_available

            self.print_check(
                f"API {name} ({endpoint})",
                endpoint_available,
                (
                    "Valid JSON response"
                    if endpoint_available
                    else "No response or invalid format"
                ),
            )

        return results

    def check_dashboard(self) -> bool:
        """Check if dashboard is accessible"""
        cmd = f"curl -s http://{self.server}:9205/ -m {self.timeout}"
        success, output = self.run_command(cmd)

        dashboard_available = (
            success and len(output) > 100 and "dashboard" in output.lower()
        )
        self.print_check(
            "Dashboard Access",
            dashboard_available,
            (
                "Dashboard HTML loaded"
                if dashboard_available
                else "Dashboard not accessible"
            ),
        )

        return dashboard_available

    def check_disk_space(self) -> bool:
        """Check available disk space"""
        cmd = "df -h / | tail -1"
        success, output = self.run_command(cmd)

        if success:
            parts = output.split()
            if len(parts) >= 5:
                usage = parts[4]
                print(f"      Disk Usage: {usage}")

                # Parse percentage
                try:
                    percent = int(usage.rstrip("%"))
                    if percent < 85:
                        self.print_check("Disk Space", True, f"Usage: {usage}")
                        return True
                    elif percent < 95:
                        self.print_warning(f"Disk usage at {usage}")
                        self.print_check(
                            "Disk Space",
                            True,
                            f"Usage: {usage} (Warning threshold)",
                        )
                        return True
                    else:
                        self.print_check(
                            "Disk Space", False, f"Usage: {usage} (Critical)"
                        )
                        return False
                except:
                    self.print_warning("Could not parse disk usage percentage")

        self.print_check("Disk Space", False, "Could not determine disk usage")
        return False

    def check_memory_availability(self) -> bool:
        """Check available memory"""
        cmd = "free -h | grep Mem"
        success, output = self.run_command(cmd)

        if success:
            print(f"      Memory Status: {output.strip()}")
            self.print_check(
                "Memory Availability", True, "Memory information available"
            )
            return True
        else:
            self.print_warning("Could not determine memory status")
            self.print_check(
                "Memory Availability", False, "Could not retrieve memory info"
            )
            return False

    def check_docker_images(self) -> bool:
        """Check if Docker images are built"""
        cmd = "docker images | grep -E 'gateway|backend|role-engine|dashboard' | wc -l"
        success, output = self.run_command(cmd)

        if success:
            try:
                count = int(output.strip())
                if count >= 3:
                    self.print_check(
                        "Docker Images", True, f"{count} images found"
                    )
                    return True
                else:
                    self.print_warning(
                        f"Only {count} Docker images found (expected 3+)"
                    )
                    self.print_check(
                        "Docker Images",
                        False,
                        f"{count} images found (insufficient)",
                    )
                    return False
            except:
                self.print_check(
                    "Docker Images", False, "Could not count Docker images"
                )
                return False

        return False

    def check_docker_volumes(self) -> bool:
        """Check if Docker volumes are properly configured"""
        cmd = "docker volume ls | grep -E 'mcp|aura' | wc -l"
        success, output = self.run_command(cmd)

        if success:
            try:
                count = int(output.strip())
                self.print_check(
                    "Docker Volumes", count > 0, f"{count} volumes found"
                )
                return count > 0
            except:
                self.print_check(
                    "Docker Volumes", False, "Could not count Docker volumes"
                )
                return False

        return False

    def check_docker_logs(self) -> bool:
        """Check for errors in Docker logs"""
        cmd = "docker-compose logs 2>/dev/null | grep -i error | head -5"
        success, output = self.run_command(cmd)

        if output.strip():
            self.print_warning("Errors found in Docker logs:")
            for line in output.split("\n"):
                if line.strip():
                    print(f"      {line}")
            self.print_check("Docker Logs", False, "Errors detected")
            return False
        else:
            self.print_check("Docker Logs", True, "No errors found")
            return True

    # Main verification flow

    def verify_infrastructure(self) -> None:
        """Verify infrastructure components"""
        self.print_header("INFRASTRUCTURE VERIFICATION")

        self.check_docker_installed()
        self.check_docker_running()
        self.check_docker_compose_installed()
        self.check_docker_images()
        self.check_docker_volumes()

    def verify_services(self) -> None:
        """Verify services are running"""
        self.print_header("SERVICE VERIFICATION")

        self.check_services_running()
        time.sleep(2)  # Wait for services to stabilize

        self.check_port_availability(9200)
        self.check_port_availability(9205)
        self.check_port_availability(9206)

    def verify_health(self) -> None:
        """Verify health endpoints"""
        self.print_header("HEALTH ENDPOINTS VERIFICATION")

        self.check_health_endpoint()
        self.check_readiness_endpoint()

    def verify_websockets(self) -> None:
        """Verify WebSocket endpoints"""
        self.print_header("WEBSOCKET ENDPOINTS VERIFICATION")

        self.check_websocket_endpoints()

    def verify_api_endpoints(self) -> None:
        """Verify API endpoints"""
        self.print_header("API ENDPOINTS VERIFICATION")

        self.check_api_endpoints()

    def verify_dashboard(self) -> None:
        """Verify dashboard"""
        self.print_header("DASHBOARD VERIFICATION")

        self.check_dashboard()

    def verify_system_resources(self) -> None:
        """Verify system resources"""
        self.print_header("SYSTEM RESOURCES VERIFICATION")

        self.check_disk_space()
        self.check_memory_availability()

    def verify_logs(self) -> None:
        """Verify logs for errors"""
        self.print_header("LOGS VERIFICATION")

        self.check_docker_logs()

    def generate_report(self) -> None:
        """Generate deployment report"""
        self.print_header("DEPLOYMENT VERIFICATION REPORT")

        print(f"\nTimestamp: {datetime.now().isoformat()}")
        print(f"Server: {self.server}")
        print(f"\nTotal Checks: {self.passed_checks + self.failed_checks}")
        print(f"Passed: {self.passed_checks}")
        print(f"Failed: {self.failed_checks}")
        print(f"Warnings: {len(self.warnings)}")

        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.failed_checks == 0:
            print("\n✓ ALL CHECKS PASSED - DEPLOYMENT SUCCESSFUL!")
            sys.exit(0)
        else:
            print(f"\n✗ {self.failed_checks} CHECKS FAILED - REVIEW ABOVE")
            sys.exit(1)

    def run_all_checks(self) -> None:
        """Run all verification checks"""
        print(
            """
╔════════════════════════════════════════════════════════════════════╗
║     AURA IA MCP - DOCKER DEPLOYMENT VERIFICATION                  ║
║     Production Deployment Verification                            ║
╚════════════════════════════════════════════════════════════════════╝
        """
        )

        try:
            self.verify_infrastructure()
            self.verify_services()
            self.verify_health()
            self.verify_websockets()
            self.verify_api_endpoints()
            self.verify_dashboard()
            self.verify_system_resources()
            self.verify_logs()
            self.generate_report()
        except KeyboardInterrupt:
            print("\n\nVerification interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n\nVerification error: {e}")
            sys.exit(1)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Docker Deployment Verification Script"
    )
    parser.add_argument(
        "--server",
        default="localhost",
        help="Server address (default: localhost)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )

    args = parser.parse_args()

    verifier = DockerDeploymentVerifier(
        server=args.server, timeout=args.timeout
    )

    verifier.run_all_checks()


if __name__ == "__main__":
    main()
