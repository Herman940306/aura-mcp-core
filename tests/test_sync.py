"""Test script for Sync Manager

Project Creator: Herman Swanepoel
"""

from pathlib import Path

from tests.stubs.mcp_sync_manager import MCPSyncManager

# Configuration
source = Path(r"F:\Kiro_Projects\NEW_KIRO_MCP")
target = Path(
    r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\kiro_mcp"
)
backup = Path(
    r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\backups"
)

print("=" * 70)
print("SYNC MANAGER TEST")
print("=" * 70)

# Create sync manager
mgr = MCPSyncManager(source, target, backup)

print(f"\nSource: {mgr.source_dir}")
print(f"Target: {mgr.target_dir}")
print(f"Backup: {mgr.backup_dir}")

# Compare directories before sync
print("\n" + "=" * 70)
print("DIRECTORY COMPARISON (BEFORE SYNC)")
print("=" * 70)
comparison = mgr.compare_directories()
print(f"Source files: {comparison.total_source_files}")
print(f"Target files: {comparison.total_target_files}")
print(f"Only in source: {len(comparison.files_only_in_source)}")
print(f"Only in target: {len(comparison.files_only_in_target)}")
print(f"Different: {len(comparison.files_different)}")
print(f"Same: {len(comparison.files_same)}")

# Perform sync
print("\n" + "=" * 70)
print("PERFORMING SYNC")
print("=" * 70)
result = mgr.sync_files()

# Display results
print("\n" + "=" * 70)
print("SYNC RESULTS")
print("=" * 70)
print(f"Success: {result.success}")
print(f"Files Copied: {result.files_copied}")
print(f"Files Failed: {result.files_failed}")
print(f"Duration: {result.duration_seconds:.2f}s")
print(f"Backup Path: {result.backup_path}")

if result.errors:
    print(f"\nErrors ({len(result.errors)}):")
    for error in result.errors[:5]:  # Show first 5
        print(f"  - {error}")

# Verify sync
print("\n" + "=" * 70)
print("VERIFYING SYNC")
print("=" * 70)
verified = mgr.verify_sync()
print(f"Verification: {'✅ PASSED' if verified else '❌ FAILED'}")

# Clean up old backups
print("\n" + "=" * 70)
print("BACKUP MANAGEMENT")
print("=" * 70)
mgr.cleanup_old_backups(keep_count=5)

# Log sync operation
print("\n" + "=" * 70)
print("LOGGING SYNC OPERATION")
print("=" * 70)
mgr.log_sync_operation(result)

# Generate report
print("\n" + "=" * 70)
print("SYNC REPORT")
print("=" * 70)
report = mgr.generate_sync_report(result)
print(report)

print("\n" + "=" * 70)
print("✅ SYNC MANAGER TEST COMPLETE")
print("=" * 70)
