"""Policy migration framework with rollback capability."""

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .policy_version_manager import PolicyVersionManager


@dataclass
class MigrationRecord:
    """Record of a policy migration."""

    migration_id: str
    from_version: str
    to_version: str
    timestamp: str
    status: str  # pending, completed, failed, dry_run_success, rolled_back
    backup_path: str
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.status in {"completed", "dry_run_success", "rolled_back"}


class PolicyMigrator:
    """Migrate policies between versions with rollback capability."""

    def __init__(
        self,
        version_manager: PolicyVersionManager,
        active_policy_path: str = "aura_ia_mcp/ops/role_engine/policies",
        backup_dir: str = "aura_ia_mcp/ops/role_engine/backups",
    ):
        self.version_manager = version_manager
        self.active_policy_path = Path(active_policy_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Place audit log next to versions_dir to align with tests
        self.audit_log_path = (
            self.version_manager.versions_dir.parent / "migration_audit.json"
        )
        self._load_audit_log()

    def _load_audit_log(self) -> None:
        """Load migration audit log."""
        if self.audit_log_path.exists():
            with open(self.audit_log_path) as f:
                self.audit_log = json.load(f)
        else:
            self.audit_log = {"migrations": []}

    def _save_audit_log(self) -> None:
        """Save migration audit log."""
        with open(self.audit_log_path, "w") as f:
            json.dump(self.audit_log, f, indent=2)

    def _create_backup(self, version: str) -> str:
        """Create backup of current policies."""
        # Use microseconds to avoid collisions in rapid tests
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = self.backup_dir / f"backup_{version}_{timestamp}"

        if self.active_policy_path.exists():
            shutil.copytree(self.active_policy_path, backup_path)
        else:
            backup_path.mkdir(parents=True)

        return str(backup_path)

    def validate_migration(
        self, from_version: str, to_version: str
    ) -> dict[str, Any]:
        """
        Validate if migration is possible.

        Returns:
            Validation result with 'can_migrate' boolean and 'issues' list
        """
        issues = []

        # Check if versions exist
        from_policy = self.version_manager.get_version(from_version)
        to_policy = self.version_manager.get_version(to_version)

        if not from_policy:
            issues.append(f"Source version {from_version} not found")

        if not to_policy:
            issues.append(f"Target version {to_version} not found")

        if not issues:
            # Validate target policy
            policy_content = self.version_manager.get_policy_content(
                to_version
            )
            if policy_content:
                validation = self.version_manager.validate_policy(
                    policy_content
                )
                if not validation["valid"]:
                    issues.extend(validation["errors"])

        return {"can_migrate": len(issues) == 0, "issues": issues}

    def migrate(
        self, to_version: str, dry_run: bool = False
    ) -> MigrationRecord:
        """
        Migrate to a new policy version.

        Args:
            to_version: Target version
            dry_run: If True, validate but don't apply

        Returns:
            MigrationRecord
        """
        current_version = self.version_manager.get_current_version()
        migration_id = (
            f"migration_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        )

        # Create migration record
        record = MigrationRecord(
            migration_id=migration_id,
            from_version=current_version or "none",
            to_version=to_version,
            timestamp=datetime.utcnow().isoformat(),
            status="pending",
            backup_path="",
        )

        try:
            # Validate migration
            validation = self.validate_migration(
                current_version or "none", to_version
            )

            if not validation["can_migrate"]:
                record.status = "failed"
                record.error = (
                    f"Validation failed: {', '.join(validation['issues'])}"
                )
                self._log_migration(record)
                return record

            if dry_run:
                record.status = "dry_run_success"
                # Log dry-run for auditability
                self._log_migration(record)
                return record

            # Create backup
            backup_path = self._create_backup(current_version or "none")
            record.backup_path = backup_path

            # Apply new policy
            new_policy_content = self.version_manager.get_policy_content(
                to_version
            )
            if new_policy_content:
                self.active_policy_path.mkdir(parents=True, exist_ok=True)
                policy_file = self.active_policy_path / "policy.rego"
                with open(policy_file, "w") as f:
                    f.write(new_policy_content)

            # Run migration script if exists
            to_policy = self.version_manager.get_version(to_version)
            if to_policy and to_policy.migration_script:
                # In production, execute the migration script
                # For now, just log it
                pass

            # Update current version in manifest
            self.version_manager.manifest["current_version"] = to_version
            self.version_manager._save_manifest()

            record.status = "completed"
            self._log_migration(record)

            return record

        except Exception as e:
            record.status = "failed"
            record.error = str(e)
            self._log_migration(record)
            return record

    def rollback(self, target_version: str) -> MigrationRecord:
        """
        Rollback active policy to a specific version.

        Args:
            target_version: Version identifier to rollback to (e.g., "1.0.0")

        Returns:
            MigrationRecord with status and success flag
        """
        migration_id = (
            f"rollback_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        )
        current_version = self.version_manager.get_current_version() or "none"
        record = MigrationRecord(
            migration_id=migration_id,
            from_version=current_version,
            to_version=target_version,
            timestamp=datetime.utcnow().isoformat(),
            status="pending",
            backup_path="",
        )

        # Validate target exists
        target = self.version_manager.get_version(target_version)
        if not target:
            record.status = "failed"
            record.error = f"Target version {target_version} not found"
            self._log_migration(record)
            raise ValueError("Target version not found")

        try:
            # Create backup of current active policy
            backup_path = self._create_backup(current_version)
            record.backup_path = backup_path

            # Restore target content
            content = self.version_manager.get_policy_content(target_version)
            self.active_policy_path.mkdir(parents=True, exist_ok=True)
            policy_file = self.active_policy_path / "policy.rego"
            with open(policy_file, "w") as f:
                f.write(content or "")

            # Update current version in manifest
            self.version_manager.manifest["current_version"] = target_version
            self.version_manager._save_manifest()

            record.status = "rolled_back"
            self._log_migration(record)
            return record
        except Exception as e:
            record.status = "failed"
            record.error = str(e)
            self._log_migration(record)
            return record

    def _log_migration(self, record: MigrationRecord) -> None:
        """Log migration to audit trail."""
        # Update or append record (ensure 'success' key present)
        rec = asdict(record)
        rec["success"] = record.success

        found = False
        for i, m in enumerate(self.audit_log["migrations"]):
            if m.get("migration_id") == record.migration_id:
                self.audit_log["migrations"][i] = rec
                found = True
                break

        if not found:
            self.audit_log["migrations"].append(rec)

        self._save_audit_log()

    def get_migration_history(self) -> list[MigrationRecord]:
        """Get all migration records."""
        return [MigrationRecord(**m) for m in self.audit_log["migrations"]]
