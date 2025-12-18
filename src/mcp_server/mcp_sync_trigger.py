"""MCP Sync Trigger System

Handles manual and automatic sync triggers.

Project Creator: Herman Swanepoel
Version: 1.0
"""

import re
from pathlib import Path

from mcp_sync_manager import MCPSyncManager, SyncResult


class SyncTriggerSystem:
    """Handles manual and automatic sync triggers."""

    # Trigger patterns
    MANUAL_SYNC_PATTERNS = [
        r"sync\s+mcp",
        r"update\s+ide\s+mcp",
        r"sync\s+mcp\s+files",
        r"synchronize\s+mcp",
        r"mcp\s+sync",
    ]

    END_OF_DAY_PATTERNS = [
        r"end\s+of\s+day",
        r"log\s+off",
        r"eod\s+sync",
        r"day\s+end",
        r"finish\s+day",
    ]

    def __init__(self, sync_manager: MCPSyncManager):
        """Initialize trigger system.

        Args:
            sync_manager: MCPSyncManager instance
        """
        self.sync_manager = sync_manager

    def parse_user_command(self, command: str) -> str | None:
        """Parse user commands for sync triggers.

        Args:
            command: User command string

        Returns:
            Trigger type ('manual', 'eod') or None
        """
        command_lower = command.lower().strip()

        # Check manual sync patterns
        for pattern in self.MANUAL_SYNC_PATTERNS:
            if re.search(pattern, command_lower):
                return "manual"

        # Check end-of-day patterns
        for pattern in self.END_OF_DAY_PATTERNS:
            if re.search(pattern, command_lower):
                return "eod"

        return None

    def should_trigger_sync(self, command: str) -> bool:
        """Determine if command should trigger sync.

        Args:
            command: User command string

        Returns:
            True if sync should be triggered
        """
        return self.parse_user_command(command) is not None

    def manual_sync(self, confirm: bool = True) -> SyncResult:
        """Execute manual sync with optional confirmation.

        Args:
            confirm: Whether to prompt for confirmation

        Returns:
            SyncResult with operation details
        """
        print("=" * 70)
        print("MANUAL MCP SYNC")
        print("=" * 70)
        print()
        print(f"Source: {self.sync_manager.source_dir}")
        print(f"Target: {self.sync_manager.target_dir}")
        print()

        # Show what will be synced
        comparison = self.sync_manager.compare_directories()
        print("Files to sync:")
        print(f"  - New files: {len(comparison.files_only_in_source)}")
        print(f"  - Modified files: {len(comparison.files_different)}")
        print(f"  - Unchanged files: {len(comparison.files_same)}")
        print(f"  - Total to copy: {comparison.total_source_files}")
        print()

        if confirm:
            response = input("Proceed with sync? (yes/no): ").lower().strip()
            if response not in ["yes", "y"]:
                print("❌ Sync cancelled by user")
                from datetime import datetime

                return SyncResult(
                    success=False,
                    files_copied=0,
                    files_failed=0,
                    backup_path=None,
                    errors=["Cancelled by user"],
                    timestamp=datetime.now(),
                    duration_seconds=0.0,
                )

        # Perform sync
        print("\n🚀 Starting sync...")
        result = self.sync_manager.sync_files()

        # Verify sync
        if result.success:
            print("\n🔍 Verifying sync...")
            verified = self.sync_manager.verify_sync()
            if not verified:
                result.success = False
                result.errors.append("Verification failed")

        # Display summary
        print("\n" + "=" * 70)
        print("SYNC SUMMARY")
        print("=" * 70)
        print(f"Status: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
        print(f"Files copied: {result.files_copied}")
        print(f"Files failed: {result.files_failed}")
        print(f"Duration: {result.duration_seconds:.2f}s")
        print(f"Backup: {result.backup_path}")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors[:5]:
                print(f"  - {error}")

        # Clean up old backups
        if result.success:
            print("\n🧹 Cleaning up old backups...")
            self.sync_manager.cleanup_old_backups(keep_count=5)

        # Log operation
        self.sync_manager.log_sync_operation(result)

        print("\n" + "=" * 70)

        return result

    def end_of_day_sync(self) -> SyncResult:
        """Execute automatic end-of-day sync.

        Returns:
            SyncResult with operation details
        """
        print("=" * 70)
        print("END-OF-DAY AUTOMATIC SYNC")
        print("=" * 70)
        print()
        print("🌙 Performing automatic end-of-day sync...")
        print(f"Source: {self.sync_manager.source_dir}")
        print(f"Target: {self.sync_manager.target_dir}")
        print()

        # Perform sync without confirmation
        result = self.sync_manager.sync_files()

        # Verify sync
        if result.success:
            verified = self.sync_manager.verify_sync()
            if not verified:
                result.success = False
                result.errors.append("Verification failed")

        # Display summary
        print("\n" + "=" * 70)
        print("END-OF-DAY SYNC SUMMARY")
        print("=" * 70)
        print(f"Status: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
        print(f"Files copied: {result.files_copied}")
        print(f"Duration: {result.duration_seconds:.2f}s")

        if result.errors:
            print(f"\nErrors: {len(result.errors)}")
            for error in result.errors[:3]:
                print(f"  - {error}")
        else:
            print("✅ All files synced successfully")

        # Clean up old backups
        if result.success:
            self.sync_manager.cleanup_old_backups(keep_count=5)

        # Log operation
        self.sync_manager.log_sync_operation(result)

        print("\n💤 End-of-day sync complete. Have a great evening!")
        print("=" * 70)

        return result

    def handle_command(
        self, command: str, auto_confirm: bool = False
    ) -> SyncResult | None:
        """Handle user command and trigger appropriate sync.

        Args:
            command: User command string
            auto_confirm: Skip confirmation prompts

        Returns:
            SyncResult if sync was triggered, None otherwise
        """
        trigger_type = self.parse_user_command(command)

        if trigger_type == "manual":
            return self.manual_sync(confirm=not auto_confirm)
        elif trigger_type == "eod":
            return self.end_of_day_sync()
        else:
            return None


def main():
    """Main entry point for sync trigger system."""
    import sys

    # Configuration
    source = Path(r"F:\Kiro_Projects\NEW_KIRO_MCP")
    target = Path(
        r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\kiro_mcp"
    )
    backup = Path(
        r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\backups"
    )

    # Create managers
    sync_manager = MCPSyncManager(source, target, backup)
    trigger_system = SyncTriggerSystem(sync_manager)

    # Parse command line arguments
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])

        # Check if it's a sync command
        if trigger_system.should_trigger_sync(command):
            result = trigger_system.handle_command(command)
            sys.exit(0 if result and result.success else 1)
        else:
            print(f"❌ Unknown command: {command}")
            print("\nSupported commands:")
            print("  - sync mcp")
            print("  - update IDE MCP")
            print("  - end of day")
            print("  - log off")
            sys.exit(1)
    else:
        # Interactive mode
        print("=" * 70)
        print("MCP SYNC TRIGGER SYSTEM")
        print("=" * 70)
        print()
        print("Commands:")
        print("  1. sync mcp          - Manual sync with confirmation")
        print("  2. update IDE MCP    - Manual sync with confirmation")
        print("  3. end of day        - Automatic end-of-day sync")
        print("  4. log off           - Automatic end-of-day sync")
        print("  5. exit              - Exit")
        print()

        while True:
            try:
                command = input("Enter command: ").strip()

                if command.lower() in ["exit", "quit", "q"]:
                    print("👋 Goodbye!")
                    break

                if trigger_system.should_trigger_sync(command):
                    result = trigger_system.handle_command(command)
                    if result:
                        print(
                            f"\n{'✅' if result.success else '❌'} Sync {'completed' if result.success else 'failed'}"
                        )
                else:
                    print("❌ Unknown command. Try 'sync mcp' or 'end of day'")

                print()
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
