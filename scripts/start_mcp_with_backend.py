#!/usr/bin/env python3
"""
Startup script that launches both backend and MCP server together.

Project Creator: Herman Swanepoel
Version: 1.0

This script ensures the backend service is running before starting the MCP server.
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def check_backend_running(
    url: str = "http://127.0.0.1:9201/health", timeout: int = 2
) -> bool:
    """Check if backend is already running."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def start_backend() -> subprocess.Popen:
    """Start the backend server in background."""
    # PRODUCTION: Use real backend server
    backend_script = (
        Path(__file__).parent.parent
        / "src"
        / "mcp_server"
        / "real_backend_server.py"
    )

    # Set environment variables for the backend
    env = os.environ.copy()
    env["BACKEND_PORT"] = "9201"
    env["BACKEND_HOST"] = "127.0.0.1"

    # Start backend as subprocess
    process = subprocess.Popen(
        [sys.executable, str(backend_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform == "win32"
            else 0
        ),
    )

    return process


def main():
    """Main startup logic."""
    # Check if backend is already running
    if not check_backend_running():
        print("Starting backend service...", file=sys.stderr)
        backend_process = start_backend()

        # Wait for backend to be ready (max 10 seconds)
        for i in range(50):  # 50 * 0.2s = 10 seconds
            time.sleep(0.2)
            if check_backend_running():
                print("Backend service ready!", file=sys.stderr)
                break
        else:
            print("Warning: Backend service may not be ready", file=sys.stderr)
    else:
        print("Backend service already running", file=sys.stderr)

    # Now start the MCP server (this will run in foreground)
    print("Starting MCP server...", file=sys.stderr)

    # Set MCP environment variables
    os.environ["MCP_PORT"] = "9200"
    os.environ["IDE_AGENTS_BACKEND_URL"] = "http://127.0.0.1:9201"
    os.environ["MCP_TRANSPORT"] = "sse"

    # Import and run MCP server
    sys.path.insert(
        0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
    )
    from mcp_server.ide_agents_mcp_server import main as mcp_main

    mcp_main()


if __name__ == "__main__":
    main()
