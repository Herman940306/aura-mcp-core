"""Test Sync Trigger System

Project Creator: Herman Swanepoel
"""

import os
import sys
from pathlib import Path

# Add src to path for module imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src", "mcp_server")
)

try:
    from mcp_sync_manager import MCPSyncManager
    from mcp_sync_trigger import SyncTriggerSystem
except ImportError as e:
    # Skip test if modules not available
    import pytest

    pytest.skip(
        f"Required modules not available: {e}", allow_module_level=True
    )

# Configuration
source = Path(r"F:\Kiro_Projects\NEW_KIRO_MCP")
target = Path(
    r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\kiro_mcp"
)
backup = Path(
    r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\backups"
)

print("=" * 70)
print("SYNC TRIGGER SYSTEM TEST")
print("=" * 70)

# Create managers
mgr = MCPSyncManager(source, target, backup)
trigger = SyncTriggerSystem(mgr)

# Test command parsing
print("\n--- Testing Command Parsing ---")
test_commands = [
    "sync mcp",
    "update IDE MCP",
    "sync mcp files",
    "end of day",
    "log off",
    "eod sync",
    "random command",
    "hello world",
]

for cmd in test_commands:
    result = trigger.parse_user_command(cmd)
    should_trigger = trigger.should_trigger_sync(cmd)
    status = "✅" if result else "❌"
    print(f'{status} "{cmd}" -> {result} (trigger: {should_trigger})')

print("\n✅ Trigger System Test Complete!")
print("=" * 70)
