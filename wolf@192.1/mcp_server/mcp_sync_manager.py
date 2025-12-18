"""MCP Sync Manager

Safe, reliable file synchronization with backup and rollback capabilities.

Project Creator: Herman Swanepoel
Version: 1.0
"""

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    files_copied: int
    files_failed: int
    backup_path: Path | None
    errors: list[str]
    timestamp: datetime
    duration_seconds: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["backup_path"] = (
            str(self.backup_path) if self.backup_path else None
        )
        result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass
class DirectoryComparison:
    """Comparison between source and target directories."""

    files_only_in_source: list[Path]
    files_only_in_target: list[Path]
    files_different: list[Path]
    files_same: list[Path]
    total_source_files: int
    total_target_files: int


class MCPSyncManager:
    """Manages safe file synchronization with backup and rollback."""

    # File patterns to include
    INCLUDE_EXTENSIONS = {
        ".py",
        ".json",
        ".md",
        ".txt",
        ".yml",
        ".yaml",
        ".toml",
        ".ini",
    }

    # Patterns to exclude
    EXCLUDE_PATTERNS = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        "node_modules",
        ".vscode",
        ".idea",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".DS_Store",
        "Thumbs.db",
    }

    # Directories to exclude from sync
    EXCLUDE_DIRS = {"logs", "htmlcov", ".coverage"}

    def __init__(self, source_dir: Path, target_dir: Path, backup_dir: Path):
        """Initialize sync manager.

        Args:
            source_dir: Source directory (NEW_KIRO_MCP)
            target_dir: Target directory (IDE MCP directory)
            backup_dir: Directory for backups
        """
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.backup_dir = Path(backup_dir)

        # Ensure directories exist
        self.source_dir = self.source_dir.resolve()
        if not self.source_dir.exists():
            raise ValueError(
                f"Source directory does not exist: {self.source_dir}"
            )

        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def should_include_file(self, file_path: Path) -> bool:
        """Check if file should be included in sync.

        Args:
            file_path: Path to check

        Returns:
            True if file should be included
        """
        # Check extension
        if file_path.suffix not in self.INCLUDE_EXTENSIONS:
            return False

        # Check exclude patterns
        path_str = str(file_path)
        for pattern in self.EXCLUDE_PATTERNS:
            if pattern in path_str:
                return False

        # Check if in excluded directory
        for part in file_path.parts:
            if part in self.EXCLUDE_DIRS:
                return False

        return True

    def get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file.

        Args:
            file_path: Path to file

        Returns:
            SHA256 hash as hex string
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def get_files_to_sync(self) -> list[Path]:
        """Get list of files to sync from source.

        Returns:
            List of file paths relative to source directory
        """
        files = []
        for file_path in self.source_dir.rglob("*"):
            if file_path.is_file() and self.should_include_file(file_path):
                relative_path = file_path.relative_to(self.source_dir)
                files.append(relative_path)
        return files

    def create_backup(self) -> Path:
        """Create timestamped backup of target directory.

        Returns:
            Path to backup directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"kiro_mcp_{timestamp}"

        print(f"📦 Creating backup: {backup_path}")

        if not self.target_dir.exists():
            print("⚠️  Target directory doesn't exist yet, skipping backup")
            backup_path.mkdir(parents=True, exist_ok=True)
            return backup_path

        try:
            shutil.copytree(
                self.target_dir,
                backup_path,
                ignore=shutil.ignore_patterns(*self.EXCLUDE_PATTERNS),
                dirs_exist_ok=True,
            )
            print("✅ Backup created successfully")
            return backup_path
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            raise

    def sync_files(self) -> SyncResult:
        """Copy all files from source to target.

        Returns:
            SyncResult with operation details
        """
        start_time = datetime.now()
        files_copied = 0
        files_failed = 0
        errors = []
        backup_path = None

        try:
            # Create backup first
            backup_path = self.create_backup()

            # Get files to sync
            files_to_sync = self.get_files_to_sync()
            print(f"\n📋 Files to sync: {len(files_to_sync)}")

            # Atomic staging: copy into temporary staging directory first
            staging_root = (
                self.backup_dir
                / f"staging_{start_time.strftime('%Y%m%d_%H%M%S')}"
            )
            staging_root.mkdir(parents=True, exist_ok=True)

            for relative_path in files_to_sync:
                source_file = self.source_dir / relative_path
                staging_file = staging_root / relative_path
                try:
                    staging_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, staging_file)
                    files_copied += 1
                    if files_copied % 10 == 0:
                        print(
                            f"   Staged {files_copied}/{len(files_to_sync)} files..."
                        )
                except Exception as e:
                    files_failed += 1
                    error_msg = f"Failed to stage {relative_path}: {e}"
                    errors.append(error_msg)
                    print(f"❌ {error_msg}")

            # Only promote if no failures
            if files_failed == 0:
                # Ensure target parent exists
                self.target_dir.mkdir(parents=True, exist_ok=True)
                # Remove existing target content for clean promotion
                if self.target_dir.exists():
                    for item in self.target_dir.iterdir():
                        try:
                            if item.is_file():
                                item.unlink()
                            else:
                                shutil.rmtree(item)
                        except Exception as e:
                            errors.append(
                                f"Failed to remove existing {item}: {e}"
                            )
                # Copy staged files to target
                for staged_file in staging_root.rglob("*"):
                    if staged_file.is_file():
                        rel = staged_file.relative_to(staging_root)
                        tgt = self.target_dir / rel
                        tgt.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(staged_file, tgt)
                print("✅ Atomic promotion completed")
            else:
                print("⚠️  Atomic promotion skipped due to staging failures")

            print(
                f"\n✅ Sync completed: {files_copied} files copied, {files_failed} failed"
            )

            duration = (datetime.now() - start_time).total_seconds()

            return SyncResult(
                success=files_failed == 0,
                files_copied=files_copied,
                files_failed=files_failed,
                backup_path=backup_path,
                errors=errors,
                timestamp=start_time,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = f"Sync operation failed: {e}"
            errors.append(error_msg)
            print(f"❌ {error_msg}")

            return SyncResult(
                success=False,
                files_copied=files_copied,
                files_failed=files_failed,
                backup_path=backup_path,
                errors=errors,
                timestamp=start_time,
                duration_seconds=duration,
            )

    def verify_sync(self) -> bool:
        """Verify file integrity using hash comparison.

        Returns:
            True if all files match, False otherwise
        """
        print("\n🔍 Verifying sync integrity...")

        files_to_check = self.get_files_to_sync()
        mismatches = []

        for relative_path in files_to_check:
            source_file = self.source_dir / relative_path
            target_file = self.target_dir / relative_path

            if not target_file.exists():
                mismatches.append(f"Missing: {relative_path}")
                continue

            try:
                source_hash = self.get_file_hash(source_file)
                target_hash = self.get_file_hash(target_file)

                if source_hash != target_hash:
                    mismatches.append(f"Hash mismatch: {relative_path}")
            except Exception as e:
                mismatches.append(f"Error checking {relative_path}: {e}")

        if mismatches:
            print(f"❌ Verification failed: {len(mismatches)} issues found")
            for mismatch in mismatches[:10]:  # Show first 10
                print(f"   - {mismatch}")
            return False
        else:
            print(
                f"✅ Verification passed: All {len(files_to_check)} files match"
            )
            return True

    def cleanup_old_backups(self, keep_count: int = 5) -> None:
        """Remove old backups, keep most recent N.

        Args:
            keep_count: Number of backups to keep
        """
        print(
            f"\n🧹 Cleaning up old backups (keeping {keep_count} most recent)..."
        )

        # Get all backup directories
        backups = sorted(
            [d for d in self.backup_dir.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        # Remove old backups
        removed = 0
        for backup in backups[keep_count:]:
            try:
                shutil.rmtree(backup)
                removed += 1
                print(f"   Removed: {backup.name}")
            except Exception as e:
                print(f"   Failed to remove {backup.name}: {e}")

        if removed > 0:
            print(f"✅ Removed {removed} old backup(s)")
        else:
            print("✅ No old backups to remove")

    def rollback(self, backup_path: Path) -> bool:
        """Restore from backup.

        Args:
            backup_path: Path to backup directory

        Returns:
            True if successful, False otherwise
        """
        print(f"\n🔄 Rolling back from: {backup_path}")

        if not backup_path.exists():
            print(f"❌ Backup not found: {backup_path}")
            return False

        try:
            # Remove current target directory
            if self.target_dir.exists():
                print("   Removing current target...")
                shutil.rmtree(self.target_dir)

            # Restore from backup
            print("   Restoring from backup...")
            shutil.copytree(backup_path, self.target_dir)

            print("✅ Rollback completed successfully")

            # Verify rollback
            if self.verify_rollback(backup_path):
                print("✅ Rollback verification passed")
                return True
            else:
                print("⚠️  Rollback verification failed")
                return False

        except Exception as e:
            print(f"❌ Rollback failed: {e}")
            return False

    def verify_rollback(self, backup_path: Path) -> bool:
        """Verify restored files match backup.

        Args:
            backup_path: Path to backup directory

        Returns:
            True if files match, False otherwise
        """
        print("   Verifying rollback...")

        # Get all files in backup
        backup_files = []
        for file_path in backup_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(backup_path)
                backup_files.append(relative_path)

        mismatches = []
        for relative_path in backup_files:
            backup_file = backup_path / relative_path
            target_file = self.target_dir / relative_path

            if not target_file.exists():
                mismatches.append(f"Missing: {relative_path}")
                continue

            try:
                backup_hash = self.get_file_hash(backup_file)
                target_hash = self.get_file_hash(target_file)

                if backup_hash != target_hash:
                    mismatches.append(f"Hash mismatch: {relative_path}")
            except Exception as e:
                mismatches.append(f"Error: {relative_path}: {e}")

        return len(mismatches) == 0

    def generate_sync_report(self, result: SyncResult) -> str:
        """Generate detailed sync report.

        Args:
            result: SyncResult to report on

        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 70)
        report.append("SYNC OPERATION REPORT")
        report.append("=" * 70)
        report.append(
            f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        report.append(f"Duration: {result.duration_seconds:.2f} seconds")
        report.append(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        report.append("")
        report.append(f"Files copied: {result.files_copied}")
        report.append(f"Files failed: {result.files_failed}")
        report.append(f"Backup path: {result.backup_path}")
        report.append("")

        if result.errors:
            report.append("Errors:")
            for error in result.errors:
                report.append(f"  - {error}")
        else:
            report.append("No errors")

        report.append("=" * 70)

        return "\n".join(report)

    def compare_directories(self) -> DirectoryComparison:
        """Compare source and target directories.

        Returns:
            DirectoryComparison with differences
        """
        source_files = set(self.get_files_to_sync())

        target_files = set()
        if self.target_dir.exists():
            for file_path in self.target_dir.rglob("*"):
                if file_path.is_file() and self.should_include_file(file_path):
                    relative_path = file_path.relative_to(self.target_dir)
                    target_files.add(relative_path)

        only_in_source = list(source_files - target_files)
        only_in_target = list(target_files - source_files)

        # Check files that exist in both
        common_files = source_files & target_files
        different = []
        same = []

        for relative_path in common_files:
            source_file = self.source_dir / relative_path
            target_file = self.target_dir / relative_path

            try:
                source_hash = self.get_file_hash(source_file)
                target_hash = self.get_file_hash(target_file)

                if source_hash != target_hash:
                    different.append(relative_path)
                else:
                    same.append(relative_path)
            except Exception:
                different.append(relative_path)

        return DirectoryComparison(
            files_only_in_source=only_in_source,
            files_only_in_target=only_in_target,
            files_different=different,
            files_same=same,
            total_source_files=len(source_files),
            total_target_files=len(target_files),
        )

    def log_sync_operation(self, result: SyncResult) -> None:
        """Log sync operation to history file.

        Args:
            result: SyncResult to log
        """
        history_file = self.source_dir / "logs" / "sync_history.json"
        history_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing history
        history = []
        if history_file.exists():
            try:
                with open(history_file, encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        # Add new entry
        history.append(result.to_dict())

        # Save history
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

        print(f"📝 Sync operation logged to: {history_file}")


if __name__ == "__main__":
    # Example usage
    source = Path(r"F:\Kiro_Projects\NEW_KIRO_MCP")
    target = Path(
        r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\kiro_mcp"
    )
    backup = Path(
        r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\backups"
    )

    manager = MCPSyncManager(source, target, backup)

    print("=== MCP Sync Manager ===\n")
    print(f"Source: {manager.source_dir}")
    print(f"Target: {manager.target_dir}")
    print(f"Backup: {manager.backup_dir}")

    # Compare directories
    print("\n--- Directory Comparison ---")
    comparison = manager.compare_directories()
    print(f"Source files: {comparison.total_source_files}")
    print(f"Target files: {comparison.total_target_files}")
    print(f"Only in source: {len(comparison.files_only_in_source)}")
    print(f"Only in target: {len(comparison.files_only_in_target)}")
    print(f"Different: {len(comparison.files_different)}")
    print(f"Same: {len(comparison.files_same)}")
