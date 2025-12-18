"""MCP Migration Orchestrator

Coordinates the complete migration process for MCP server configuration.

Project Creator: Herman Swanepoel
Version: 1.0
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mcp_config_manager import MCPConfigurationManager
from mcp_health_checker import HealthReport, MCPHealthChecker


@dataclass
class MigrationResult:
    """Result of migration process."""

    success: bool
    phase_completed: str
    message: str
    health_report: HealthReport | None
    timestamp: datetime
    errors: list


class MCPMigrationOrchestrator:
    """Coordinates the complete MCP migration process."""

    def __init__(
        self,
        config_path: Path,
        new_working_dir: str,
        backend_url: str = "http://127.0.0.1:8001",
    ):
        """Initialize orchestrator.

        Args:
            config_path: Path to mcp.json configuration file
            new_working_dir: New working directory (NEW_KIRO_MCP path)
            backend_url: Backend server URL
        """
        self.config_manager = MCPConfigurationManager(config_path)
        self.health_checker = MCPHealthChecker(backend_url)
        self.new_working_dir = new_working_dir
        self.migration_log = []

    def log(self, message: str):
        """Log migration step."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.migration_log.append(log_entry)
        try:
            print(log_entry)
        except UnicodeEncodeError:
            # Fallback for Windows console encoding issues
            print(log_entry.encode("ascii", "replace").decode("ascii"))

    async def execute_migration(self) -> MigrationResult:
        """Execute complete migration process.

        Returns:
            MigrationResult with migration status
        """
        self.log("=" * 70)
        self.log("🚀 Starting MCP Migration Process")
        self.log("=" * 70)

        try:
            # Phase 1: Update Configuration
            self.log("\n📋 Phase 1: Configuration Migration")
            phase1_success = await self.phase1_update_configuration()

            if not phase1_success:
                return MigrationResult(
                    success=False,
                    phase_completed="Phase 1",
                    message="Configuration migration failed",
                    health_report=None,
                    timestamp=datetime.now(),
                    errors=["Configuration update failed"],
                )

            self.log("✅ Phase 1 completed successfully")

            # Phase 2: Verify Health
            self.log("\n🏥 Phase 2: Health Verification")
            self.log(
                "⚠️  Note: Backend server must be started manually or via IDE restart"
            )
            self.log("   Waiting for backend server to be available...")

            health_report = await self.phase2_verify_health()

            if health_report.overall_status == "fail":
                self.log("⚠️  Phase 2: Health checks failed")
                self.log(
                    "   This is expected if backend server is not running yet"
                )
                self.log(
                    "   Please restart Kiro IDE to start the backend server"
                )

                return MigrationResult(
                    success=False,
                    phase_completed="Phase 2",
                    message="Health verification failed - backend server not running",
                    health_report=health_report,
                    timestamp=datetime.now(),
                    errors=["Backend server not running - restart Kiro IDE"],
                )

            self.log("✅ Phase 2 completed successfully")

            # Phase 3: Initial Sync
            self.log("\n📦 Phase 3: Initial Sync to IDE Directory")
            phase3_success = await self.phase3_initial_sync()

            if not phase3_success:
                self.log("⚠️  Phase 3: Initial sync encountered issues")

                return MigrationResult(
                    success=False,
                    phase_completed="Phase 3",
                    message="Initial sync failed",
                    health_report=health_report,
                    timestamp=datetime.now(),
                    errors=["Initial sync to IDE directory failed"],
                )

            self.log("✅ Phase 3 completed successfully")

            # Migration complete
            self.log("\n" + "=" * 70)
            self.log("✅ MCP Migration Completed Successfully!")
            self.log("=" * 70)
            self.log("\n📝 Summary:")
            self.log("   ✅ Phase 1: Configuration updated")
            self.log("   ✅ Phase 2: Health checks passed")
            self.log("   ✅ Phase 3: Initial sync completed")
            self.log("\n📝 Next Steps:")
            self.log("   1. System is now fully operational")
            self.log("   2. Use CLI for ongoing sync operations")
            self.log("   3. Monitor logs for any issues")

            return MigrationResult(
                success=True,
                phase_completed="Complete",
                message="Migration completed successfully with initial sync",
                health_report=health_report,
                timestamp=datetime.now(),
                errors=[],
            )

        except Exception as e:
            self.log(f"❌ Migration failed with error: {e}")
            return MigrationResult(
                success=False,
                phase_completed="Error",
                message=f"Migration failed: {str(e)}",
                health_report=None,
                timestamp=datetime.now(),
                errors=[str(e)],
            )

    async def phase1_update_configuration(self) -> bool:
        """Update MCP configuration to point to NEW_KIRO_MCP.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.log("📄 Reading current configuration...")

            # Validate current config
            is_valid, errors = self.config_manager.validate_config()
            if errors:
                self.log("⚠️  Current configuration issues:")
                for error in errors:
                    self.log(f"   - {error}")

            # Backup current config
            self.log("💾 Creating configuration backup...")
            backup_path = self.config_manager.backup_config()
            self.log(f"   Backup saved to: {backup_path}")

            # Update working directory
            self.log(
                f"📁 Updating working directory to: {self.new_working_dir}"
            )
            if not self.config_manager.set_working_directory(
                self.new_working_dir
            ):
                self.log("❌ Failed to update working directory")
                return False

            # Enable server
            self.log("🔓 Enabling MCP server...")
            if not self.config_manager.enable_server():
                self.log("❌ Failed to enable server")
                return False

            # Enable all tools
            self.log("🔧 Enabling all MCP tools...")
            if not self.config_manager.enable_all_tools():
                self.log("❌ Failed to enable tools")
                return False

            # Validate updated config
            self.log("✅ Validating updated configuration...")
            is_valid, errors = self.config_manager.validate_config()

            if is_valid:
                self.log("✅ Configuration is valid and ready")
                return True
            else:
                self.log("⚠️  Configuration validation warnings:")
                for error in errors:
                    self.log(f"   - {error}")
                # Continue anyway if only warnings
                return True

        except Exception as e:
            self.log(f"❌ Error in Phase 1: {e}")
            return False

    async def phase3_initial_sync(self) -> bool:
        """Perform initial sync to IDE directory.

        Returns:
            True if successful, False otherwise
        """
        try:
            from pathlib import Path

            from mcp_sync_manager import MCPSyncManager

            # Import logging if available
            try:
                from mcp_logging import log_error, log_migration_phase

                logging_available = True
            except ImportError:
                logging_available = False

            self.log("📦 Starting Phase 3: Initial Sync to IDE Directory")

            # Define paths
            source = Path(r"F:\Kiro_Projects\NEW_KIRO_MCP")
            target = Path(
                r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\kiro_mcp"
            )
            backup = Path(
                r"C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\backups"
            )

            self.log(f"   Source: {source}")
            self.log(f"   Target: {target}")
            self.log(f"   Backup: {backup}")

            # Verify source exists
            if not source.exists():
                error_msg = f"Source directory does not exist: {source}"
                self.log(f"❌ {error_msg}")
                if logging_available:
                    log_error("phase3_sync", error_msg)
                return False

            # Create sync manager
            self.log("🔧 Initializing sync manager...")
            sync_manager = MCPSyncManager(source, target, backup)

            # Perform sync
            self.log("🚀 Starting initial sync operation...")
            self.log("   This may take a few moments...")

            result = sync_manager.sync_files()

            # Check result
            if result.success:
                self.log("🔍 Verifying sync integrity...")
                verified = sync_manager.verify_sync()

                if verified:
                    self.log("✅ Sync completed and verified successfully!")
                    self.log(f"   📊 Files copied: {result.files_copied}")
                    self.log(f"   ⏱️  Duration: {result.duration_seconds:.2f}s")
                    self.log(f"   💾 Backup: {result.backup_path}")

                    # Clean up old backups
                    self.log("🧹 Cleaning up old backups (keeping last 5)...")
                    sync_manager.cleanup_old_backups(keep_count=5)

                    # Log operation
                    sync_manager.log_sync_operation(result)

                    # Log to centralized logging
                    if logging_available:
                        log_migration_phase(
                            "phase3_initial_sync",
                            "success",
                            {
                                "files_copied": result.files_copied,
                                "duration": result.duration_seconds,
                                "backup_path": str(result.backup_path),
                                "verified": True,
                            },
                        )

                    return True
                else:
                    error_msg = (
                        "Sync verification failed - files may not match"
                    )
                    self.log(f"❌ {error_msg}")
                    if logging_available:
                        log_error(
                            "phase3_sync",
                            error_msg,
                            {
                                "files_copied": result.files_copied,
                                "verification": "failed",
                            },
                        )
                    return False
            else:
                error_msg = f"Sync failed with {len(result.errors)} errors"
                self.log(f"❌ {error_msg}")
                self.log("   First 5 errors:")
                for i, error in enumerate(result.errors[:5], 1):
                    self.log(f"   {i}. {error}")

                if logging_available:
                    log_error(
                        "phase3_sync",
                        error_msg,
                        {
                            "error_count": len(result.errors),
                            "errors": result.errors[:10],
                        },
                    )

                return False

        except Exception as e:
            error_msg = f"Error in Phase 3: {e}"
            self.log(f"❌ {error_msg}")

            try:
                from mcp_logging import log_error

                log_error("phase3_sync", error_msg, {"exception": str(e)})
            except:
                pass

            return False

    async def phase2_verify_health(self) -> HealthReport:
        """Run comprehensive health checks.

        Returns:
            HealthReport with verification results
        """
        try:
            self.log("🔍 Running comprehensive health checks...")

            # Wait a bit for backend to potentially start
            await asyncio.sleep(2)

            # Run health checks
            async with self.health_checker as checker:
                health_report = await checker.run_full_health_check()

            # Log results
            self.log("\n📊 Health Check Results:")
            self.log(f"   Total checks: {health_report.total_checks}")
            self.log(f"   ✅ Passed: {health_report.passed}")
            self.log(f"   ⚠️  Warnings: {health_report.warnings}")
            self.log(f"   ❌ Failed: {health_report.failed}")
            self.log(f"   Overall: {health_report.overall_status.upper()}")

            # Show failed checks
            if health_report.failed > 0:
                self.log("\n❌ Failed checks:")
                for result in health_report.results:
                    if result.status == "fail":
                        self.log(f"   - {result.component}: {result.message}")

            return health_report

        except Exception as e:
            self.log(f"❌ Error in Phase 2: {e}")
            # Return a failed health report
            from mcp_health_checker import HealthResult

            return HealthReport(
                overall_status="fail",
                total_checks=0,
                passed=0,
                failed=1,
                warnings=0,
                results=[
                    HealthResult(
                        component="Health Check",
                        status="fail",
                        message=f"Error running health checks: {str(e)}",
                        details={"error": str(e)},
                        timestamp=datetime.now(),
                        response_time_ms=0.0,
                    )
                ],
                timestamp=datetime.now(),
                duration_seconds=0.0,
            )

    def generate_migration_report(self) -> str:
        """Generate complete migration report.

        Returns:
            Formatted migration report
        """
        report = []
        report.append("=" * 70)
        report.append("MCP MIGRATION REPORT")
        report.append("=" * 70)
        report.append(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        report.append("")
        report.append("Migration Log:")
        report.append("-" * 70)

        for entry in self.migration_log:
            report.append(entry)

        report.append("")
        report.append("=" * 70)

        return "\n".join(report)


async def main():
    """Main entry point for migration."""
    # Configuration
    config_path = Path(".kiro/settings/mcp.json")
    new_working_dir = r"F:\Kiro_Projects\NEW_KIRO_MCP"

    # Create orchestrator
    orchestrator = MCPMigrationOrchestrator(
        config_path=config_path, new_working_dir=new_working_dir
    )

    # Execute migration
    result = await orchestrator.execute_migration()

    # Generate and save report
    report = orchestrator.generate_migration_report()

    report_path = Path("logs/migration_report.txt")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    try:
        print(f"\n📄 Migration report saved to: {report_path}")
    except UnicodeEncodeError:
        print(f"\nMigration report saved to: {report_path}")

    # Return exit code based on success
    return 0 if result.success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
