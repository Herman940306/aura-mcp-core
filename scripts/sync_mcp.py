"""MCP Sync Command-Line Tool

Command-line interface for manual MCP synchronization operations.

Project Creator: Herman Swanepoel
Version: 1.0
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
)

from mcp_server.mcp_sync_manager import MCPSyncManager

# Import logging if available
try:
    from mcp_server.mcp_logging import (
        get_logger,
        log_error,
        log_sync_operation,
    )

    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False


class SyncCLI:
    """Command-line interface for MCP sync operations."""

    def __init__(
        self,
        source: Path,
        target: Path,
        backup_dir: Path,
        verbose: bool = False,
    ):
        """Initialize sync CLI.

        Args:
            source: Source directory path
            target: Target directory path
            backup_dir: Backup directory path
            verbose: Enable verbose output
        """
        self.source = source
        self.target = target
        self.backup_dir = backup_dir
        self.verbose = verbose
        self.sync_manager = MCPSyncManager(source, target, backup_dir)

    def log(self, message: str, level: str = "info") -> None:
        """Log message to console.

        Args:
            message: Message to log
            level: Log level (info, warning, error, success)
        """
        icons = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "success": "✅"}
        icon = icons.get(level, "•")
        print(f"{icon} {message}")

    def confirm(self, message: str) -> bool:
        """Prompt user for confirmation.

        Args:
            message: Confirmation message

        Returns:
            True if user confirms, False otherwise
        """
        response = input(f"\n{message} (y/n): ").strip().lower()
        return response in ["y", "yes"]

    def manual_sync(self, force: bool = False) -> int:
        """Perform manual sync operation.

        Args:
            force: Skip confirmation prompt

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        self.log("=" * 70)
        self.log("MCP Manual Sync Operation", "info")
        self.log("=" * 70)

        # Display paths
        self.log(f"Source: {self.source}")
        self.log(f"Target: {self.target}")
        self.log(f"Backup: {self.backup_dir}")

        # Verify source exists
        if not self.source.exists():
            self.log(
                f"Source directory does not exist: {self.source}", "error"
            )
            if LOGGING_AVAILABLE:
                log_error("sync_cli", f"Source not found: {self.source}")
            return 1

        # Confirmation prompt
        if not force:
            self.log("\nThis will sync all files from source to target.")
            self.log("A backup will be created before syncing.")

            if not self.confirm("Do you want to proceed?"):
                self.log("Sync operation cancelled by user.", "warning")
                return 0

        # Perform sync
        self.log("\n🚀 Starting sync operation...", "info")

        try:
            result = self.sync_manager.sync_files()

            if result.success:
                self.log("\n🔍 Verifying sync integrity...", "info")
                verified = self.sync_manager.verify_sync()

                if verified:
                    self.log("\n" + "=" * 70, "success")
                    self.log("Sync Completed Successfully!", "success")
                    self.log("=" * 70, "success")
                    self.log(f"Files copied: {result.files_copied}")
                    self.log(f"Duration: {result.duration_seconds:.2f}s")
                    self.log(f"Backup: {result.backup_path}")

                    # Verbose output
                    if self.verbose:
                        self.log("\nDetailed Results:")
                        self.log(f"  Timestamp: {result.timestamp}")
                        self.log(f"  Files failed: {result.files_failed}")

                    # Log operation
                    if LOGGING_AVAILABLE:
                        log_sync_operation(
                            "manual_sync",
                            {
                                "files_copied": result.files_copied,
                                "duration": result.duration_seconds,
                                "verified": True,
                                "cli": True,
                            },
                        )

                    return 0
                else:
                    self.log("Sync verification failed!", "error")
                    if LOGGING_AVAILABLE:
                        log_error("sync_cli", "Verification failed")
                    return 1
            else:
                self.log(
                    f"\nSync failed with {len(result.errors)} errors", "error"
                )
                self.log("\nFirst 5 errors:")
                for i, error in enumerate(result.errors[:5], 1):
                    self.log(f"  {i}. {error}", "error")

                if LOGGING_AVAILABLE:
                    log_error(
                        "sync_cli",
                        "Sync failed",
                        {
                            "error_count": len(result.errors),
                            "errors": result.errors[:10],
                        },
                    )

                return 1

        except Exception as e:
            self.log(f"Sync operation failed: {e}", "error")
            if LOGGING_AVAILABLE:
                log_error("sync_cli", str(e))
            return 1

    def eod_sync(self) -> int:
        """Perform end-of-day sync operation.

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        self.log("=" * 70)
        self.log("MCP End-of-Day Sync", "info")
        self.log("=" * 70)

        self.log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"Source: {self.source}")
        self.log(f"Target: {self.target}")

        # Verify source exists
        if not self.source.exists():
            self.log(
                f"Source directory does not exist: {self.source}", "error"
            )
            return 1

        # Perform sync without confirmation
        self.log("\n🚀 Starting end-of-day sync...", "info")

        try:
            result = self.sync_manager.sync_files()

            if result.success:
                verified = self.sync_manager.verify_sync()

                if verified:
                    self.log("\n✅ End-of-day sync completed!", "success")
                    self.log(f"Files synced: {result.files_copied}")
                    self.log(f"Duration: {result.duration_seconds:.2f}s")

                    # Log operation
                    if LOGGING_AVAILABLE:
                        log_sync_operation(
                            "eod_sync",
                            {
                                "files_copied": result.files_copied,
                                "duration": result.duration_seconds,
                                "verified": True,
                                "cli": True,
                            },
                        )

                    return 0
                else:
                    self.log("Verification failed!", "error")
                    return 1
            else:
                self.log(f"Sync failed: {len(result.errors)} errors", "error")
                return 1

        except Exception as e:
            self.log(f"End-of-day sync failed: {e}", "error")
            if LOGGING_AVAILABLE:
                log_error("sync_cli", f"EOD sync failed: {e}")
            return 1

    def rollback(self, backup_name: str | None = None) -> int:
        """Perform rollback operation.

        Args:
            backup_name: Specific backup to restore (None for latest)

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        self.log("=" * 70)
        self.log("MCP Rollback Operation", "info")
        self.log("=" * 70)

        # List available backups
        backups = sorted(
            self.backup_dir.glob("kiro_mcp_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not backups:
            self.log("No backups available for rollback.", "error")
            return 1

        self.log(f"\nAvailable backups ({len(backups)}):")
        for i, backup in enumerate(backups[:10], 1):
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            self.log(
                f"  {i}. {backup.name} ({mtime.strftime('%Y-%m-%d %H:%M:%S')})"
            )

        # Select backup
        if backup_name:
            backup_path = self.backup_dir / backup_name
            if not backup_path.exists():
                self.log(f"Backup not found: {backup_name}", "error")
                return 1
        else:
            backup_path = backups[0]
            self.log(f"\nUsing latest backup: {backup_path.name}")

        # Confirmation
        if not self.confirm(f"\nRestore from backup '{backup_path.name}'?"):
            self.log("Rollback cancelled by user.", "warning")
            return 0

        # Perform rollback
        self.log("\n🔄 Starting rollback operation...", "info")

        try:
            result = self.sync_manager.rollback(backup_path)

            if result.success:
                self.log("\n✅ Rollback completed successfully!", "success")
                self.log(f"Files restored: {result.files_copied}")
                self.log(f"Duration: {result.duration_seconds:.2f}s")

                # Log operation
                if LOGGING_AVAILABLE:
                    log_sync_operation(
                        "rollback",
                        {
                            "files_restored": result.files_copied,
                            "duration": result.duration_seconds,
                            "backup_used": str(backup_path),
                            "cli": True,
                        },
                    )

                return 0
            else:
                self.log(
                    f"Rollback failed: {len(result.errors)} errors", "error"
                )
                return 1

        except Exception as e:
            self.log(f"Rollback operation failed: {e}", "error")
            if LOGGING_AVAILABLE:
                log_error("sync_cli", f"Rollback failed: {e}")
            return 1

    def status(self) -> int:
        """Display sync status and history.

        Returns:
            Exit code (0 for success)
        """
        self.log("=" * 70)
        self.log("MCP Sync Status", "info")
        self.log("=" * 70)

        # Display paths
        self.log(f"\nSource: {self.source}")
        self.log(f"  Exists: {'Yes' if self.source.exists() else 'No'}")

        self.log(f"\nTarget: {self.target}")
        self.log(f"  Exists: {'Yes' if self.target.exists() else 'No'}")

        self.log(f"\nBackup Directory: {self.backup_dir}")
        self.log(f"  Exists: {'Yes' if self.backup_dir.exists() else 'No'}")

        # Count backups
        if self.backup_dir.exists():
            backups = list(self.backup_dir.glob("kiro_mcp_*"))
            self.log(f"  Backups: {len(backups)}")

        # Display recent sync history
        if LOGGING_AVAILABLE:
            logger = get_logger()
            history = logger.get_sync_history(limit=5)

            if history:
                self.log("\nRecent Sync Operations:")
                for entry in history:
                    timestamp = entry.get("timestamp", "Unknown")
                    op_type = entry.get("operation_type", "Unknown")
                    details = entry.get("details", {})
                    files = details.get("files_copied", 0)
                    self.log(f"  {timestamp} - {op_type} ({files} files)")
            else:
                self.log("\nNo sync history available.")

        return 0


def main():
    """Main entry point for sync CLI."""
    parser = argparse.ArgumentParser(
        description="MCP Sync Command-Line Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Manual sync with confirmation
  python sync_mcp.py --manual

  # Manual sync without confirmation
  python sync_mcp.py --manual --force

  # End-of-day sync
  python sync_mcp.py --eod

  # Rollback to latest backup
  python sync_mcp.py --rollback

  # Rollback to specific backup
  python sync_mcp.py --rollback --backup kiro_mcp_20251117_133046

  # Display status
  python sync_mcp.py --status

  # Verbose output
  python sync_mcp.py --manual --verbose
        """,
    )

    # Operation modes
    parser.add_argument(
        "--manual", action="store_true", help="Perform manual sync operation"
    )
    parser.add_argument(
        "--eod", action="store_true", help="Perform end-of-day sync operation"
    )
    parser.add_argument(
        "--rollback", action="store_true", help="Rollback to previous backup"
    )
    parser.add_argument(
        "--status", action="store_true", help="Display sync status and history"
    )

    # Options
    parser.add_argument(
        "--force", action="store_true", help="Skip confirmation prompts"
    )
    parser.add_argument(
        "--backup", type=str, help="Specific backup name for rollback"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose output"
    )

    # Path overrides
    parser.add_argument(
        "--source",
        type=str,
        default=r"F:\Kiro_Projects\NEW_KIRO_MCP",
        help="Source directory path",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\kiro_mcp",
        help="Target directory path",
    )
    parser.add_argument(
        "--backup-dir",
        type=str,
        default=r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\backups",
        help="Backup directory path",
    )

    args = parser.parse_args()

    # Validate that at least one operation is specified
    if not any([args.manual, args.eod, args.rollback, args.status]):
        parser.print_help()
        return 1

    # Create CLI instance
    cli = SyncCLI(
        source=Path(args.source),
        target=Path(args.target),
        backup_dir=Path(args.backup_dir),
        verbose=args.verbose,
    )

    # Execute operation
    try:
        if args.manual:
            return cli.manual_sync(force=args.force)
        elif args.eod:
            return cli.eod_sync()
        elif args.rollback:
            return cli.rollback(backup_name=args.backup)
        elif args.status:
            return cli.status()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user.")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
