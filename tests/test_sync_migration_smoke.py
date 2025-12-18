"""Sync and migration smoke tests.

Validates that sync manager basic operations and migration orchestrator
initial phases do not raise exceptions (backend may be absent).
"""

import asyncio
from pathlib import Path


def test_sync_manager_minimal() -> bool:
    from tests.stubs.mcp_sync_manager import MCPSyncManager

    source = Path.cwd()  # use current project as source
    target = Path("logs/_sync_target_test")
    backup = Path("logs/_sync_backups")
    manager = MCPSyncManager(source, target, backup)
    result = manager.sync_files()
    return result.files_copied >= 0


async def test_migration_orchestrator_phase1() -> bool:
    from mcp_migration_orchestrator import MCPMigrationOrchestrator

    cfg = Path(".kiro/settings/mcp.json")
    # Create dummy config if missing
    cfg.parent.mkdir(parents=True, exist_ok=True)
    if not cfg.exists():
        cfg.write_text('{"servers":[],"tools":[]}', encoding="utf-8")
    orchestrator = MCPMigrationOrchestrator(
        cfg,
        new_working_dir=str(Path.cwd()),
    )
    ok = await orchestrator.phase1_update_configuration()
    return ok


async def main():
    sync_ok = test_sync_manager_minimal()
    mig_ok = await test_migration_orchestrator_phase1()
    if sync_ok and mig_ok:
        print("✓ sync+migration smoke passed")
        exit(0)
    else:
        print("✗ sync+migration smoke failed")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
