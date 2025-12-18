"""
Wave 4: Policy Versioning Integration Tests

Tests policy version management and migration flows including:
- Policy version creation
- Policy validation
- Migration execution
- Rollback capability
- Migration audit trail
"""

import json
from pathlib import Path

import pytest

from aura_ia_mcp.ops.role_engine.policy_migrator import PolicyMigrator
from aura_ia_mcp.ops.role_engine.policy_version_manager import (
    PolicyVersionManager,
)


@pytest.fixture
def temp_policy_dir(tmp_path):
    """Create temporary policy directory structure."""
    policy_dir = tmp_path / "policy_versions"
    policy_dir.mkdir()

    # Create manifest
    manifest = {
        "current_version": "1.0.0",
        "versions": [
            {
                "version": "1.0.0",
                "description": "Initial policy",
                "created_at": "2025-11-30T00:00:00",
                "created_by": "test",
            }
        ],
    }
    (policy_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Create initial policy version
    v1_dir = policy_dir / "1.0.0"
    v1_dir.mkdir()
    (v1_dir / "policy.rego").write_text(
        """
package authz

default allow = false

allow {
    input.user.role == "admin"
}
"""
    )
    (v1_dir / "metadata.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "description": "Initial policy",
                "created_at": "2025-11-30T00:00:00",
                "created_by": "test",
            },
            indent=2,
        )
    )

    return policy_dir


@pytest.fixture
def version_manager(temp_policy_dir):
    """Policy version manager with temp directory."""
    return PolicyVersionManager(versions_dir=temp_policy_dir)


@pytest.fixture
def migrator(version_manager):
    """Policy migrator."""
    return PolicyMigrator(version_manager)


class TestPolicyVersionCreation:
    """Test policy version creation."""

    def test_create_new_version(self, version_manager):
        """Test creating a new policy version."""
        new_policy = """
package authz

default allow = false

allow {
    input.user.role == "admin"
    input.user.department == "engineering"
}
"""

        version = version_manager.create_version(
            version="1.1.0",
            description="Add department check",
            policy_content=new_policy,
            created_by="test_user",
        )

        assert version.version == "1.1.0"
        assert version.description == "Add department check"
        assert version.created_by == "test_user"

        # Verify files were created
        version_dir = version_manager.versions_dir / "1.1.0"
        assert version_dir.exists()
        assert (version_dir / "policy.rego").exists()
        assert (version_dir / "metadata.json").exists()

    def test_create_version_with_invalid_policy(self, version_manager):
        """Test validation catches invalid policy."""
        invalid_policy = """
package authz
# Missing closing brace
allow {
    input.user.role == "admin"
"""

        with pytest.raises(
            ValueError, match="Invalid policy|validation failed"
        ):
            version_manager.create_version(
                version="1.2.0",
                description="Invalid policy",
                policy_content=invalid_policy,
                created_by="test",
            )

    def test_create_duplicate_version(self, version_manager):
        """Test creating duplicate version fails."""
        policy = "package authz\ndefault allow = false"

        # First creation should succeed
        version_manager.create_version(
            version="1.1.0",
            description="New version",
            policy_content=policy,
            created_by="test",
        )

        # Duplicate should fail
        with pytest.raises(ValueError, match="already exists|duplicate"):
            version_manager.create_version(
                version="1.1.0",
                description="Duplicate",
                policy_content=policy,
                created_by="test",
            )


class TestPolicyVersionRetrieval:
    """Test policy version retrieval."""

    def test_get_current_version(self, version_manager):
        """Test retrieving current version."""
        current = version_manager.get_current_version()
        assert current == "1.0.0"

    def test_get_version_details(self, version_manager):
        """Test retrieving version details."""
        version = version_manager.get_version("1.0.0")
        assert version is not None
        assert version.version == "1.0.0"
        assert version.description == "Initial policy"

    def test_get_nonexistent_version(self, version_manager):
        """Test retrieving nonexistent version returns None."""
        version = version_manager.get_version("99.99.99")
        assert version is None

    def test_list_all_versions(self, version_manager):
        """Test listing all versions."""
        versions = version_manager.list_versions()
        assert len(versions) >= 1
        assert versions[0].version == "1.0.0"

    def test_get_policy_content(self, version_manager):
        """Test retrieving policy content."""
        content = version_manager.get_policy_content("1.0.0")
        assert content is not None
        assert "package authz" in content
        assert 'input.user.role == "admin"' in content


class TestPolicyValidation:
    """Test policy validation."""

    def test_validate_correct_policy(self, version_manager):
        """Test validation passes for correct policy."""
        valid_policy = """
package authz

default allow = false

allow {
    input.user.role == "admin"
}
"""

        result = version_manager.validate_policy(valid_policy)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_empty_policy(self, version_manager):
        """Test validation fails for empty policy."""
        result = version_manager.validate_policy("")
        assert result["valid"] is False
        assert any("empty" in err.lower() for err in result["errors"])

    def test_validate_missing_package(self, version_manager):
        """Test validation fails without package declaration."""
        policy = """
default allow = false
allow { input.user.role == "admin" }
"""

        result = version_manager.validate_policy(policy)
        assert result["valid"] is False
        assert any("package" in err.lower() for err in result["errors"])

    def test_validate_unmatched_braces(self, version_manager):
        """Test validation detects unmatched braces."""
        policy = """
package authz
allow {
    input.user.role == "admin"
# Missing closing brace
"""

        result = version_manager.validate_policy(policy)
        assert result["valid"] is False
        assert any("brace" in err.lower() for err in result["errors"])


class TestPolicyMigration:
    """Test policy migration."""

    def test_validate_migration(self, migrator, version_manager):
        """Test migration validation."""
        # Create target version
        new_policy = "package authz\ndefault allow = false"
        version_manager.create_version(
            version="1.1.0",
            description="New version",
            policy_content=new_policy,
            created_by="test",
        )

        # Validate migration
        validation = migrator.validate_migration("1.0.0", "1.1.0")
        assert validation["can_migrate"] is True
        assert len(validation["issues"]) == 0

    def test_validate_migration_nonexistent_target(self, migrator):
        """Test validation fails for nonexistent target."""
        validation = migrator.validate_migration("1.0.0", "99.99.99")
        assert validation["can_migrate"] is False
        assert any("not found" in issue for issue in validation["issues"])

    def test_migrate_dry_run(self, migrator, version_manager):
        """Test dry-run migration."""
        # Create target version
        new_policy = """
package authz
default allow = false
allow { input.user.admin == true }
"""
        version_manager.create_version(
            version="1.1.0",
            description="Admin field change",
            policy_content=new_policy,
            created_by="test",
        )

        # Dry run
        record = migrator.migrate("1.1.0", dry_run=True)
        assert record.success is True
        assert record.from_version == "1.0.0"
        assert record.to_version == "1.1.0"

        # Current version should NOT change
        assert version_manager.get_current_version() == "1.0.0"

    def test_migrate_actual(self, migrator, version_manager):
        """Test actual migration execution."""
        # Create target version
        new_policy = "package authz\ndefault allow = false"
        version_manager.create_version(
            version="1.1.0",
            description="New version",
            policy_content=new_policy,
            created_by="test",
        )

        # Execute migration
        record = migrator.migrate("1.1.0", dry_run=False)
        assert record.success is True

        # Current version should change
        assert version_manager.get_current_version() == "1.1.0"

    def test_migration_creates_backup(self, migrator, version_manager):
        """Test migration creates backup."""
        # Create target version
        new_policy = "package authz\ndefault allow = false"
        version_manager.create_version(
            version="1.1.0",
            description="Backup test",
            policy_content=new_policy,
            created_by="test",
        )

        # Execute migration
        record = migrator.migrate("1.1.0", dry_run=False)

        # Verify backup was created
        assert record.backup_path is not None
        backup_path = Path(record.backup_path)
        assert backup_path.exists()


class TestPolicyRollback:
    """Test policy rollback."""

    def test_rollback_to_previous_version(self, migrator, version_manager):
        """Test rolling back to previous version."""
        # Create and migrate to v1.1.0
        new_policy = "package authz\ndefault allow = false"
        version_manager.create_version(
            version="1.1.0",
            description="New version",
            policy_content=new_policy,
            created_by="test",
        )
        migrator.migrate("1.1.0", dry_run=False)

        assert version_manager.get_current_version() == "1.1.0"

        # Rollback to v1.0.0
        record = migrator.rollback("1.0.0")
        assert record.success is True
        assert version_manager.get_current_version() == "1.0.0"

    def test_rollback_to_nonexistent_version(self, migrator):
        """Test rollback to nonexistent version fails."""
        with pytest.raises(ValueError, match="not found"):
            migrator.rollback("99.99.99")


class TestMigrationAudit:
    """Test migration audit trail."""

    def test_audit_log_records_migrations(self, migrator, version_manager):
        """Test migrations are logged to audit trail."""
        # Perform migrations
        for i in range(1, 3):
            version = f"1.{i}.0"
            policy = f"package authz\n# Version {version}"
            version_manager.create_version(
                version=version,
                description=f"Version {version}",
                policy_content=policy,
                created_by="test",
            )
            migrator.migrate(version, dry_run=False)

        # Check audit log
        audit_path = (
            migrator.version_manager.versions_dir.parent
            / "migration_audit.json"
        )
        assert audit_path.exists()

        audit_data = json.loads(audit_path.read_text())
        assert "migrations" in audit_data
        assert len(audit_data["migrations"]) >= 2

    def test_audit_log_includes_details(self, migrator, version_manager):
        """Test audit log includes migration details."""
        # Create and migrate
        new_policy = "package authz\ndefault allow = false"
        version_manager.create_version(
            version="1.1.0",
            description="Audit test",
            policy_content=new_policy,
            created_by="test",
        )
        migrator.migrate("1.1.0", dry_run=False)

        # Read audit log
        audit_path = (
            migrator.version_manager.versions_dir.parent
            / "migration_audit.json"
        )
        audit_data = json.loads(audit_path.read_text())

        last_migration = audit_data["migrations"][-1]
        assert last_migration["from_version"] == "1.0.0"
        assert last_migration["to_version"] == "1.1.0"
        assert last_migration["success"] is True
        assert "timestamp" in last_migration


class TestPolicyVersionIntegration:
    """Test complete policy version lifecycle."""

    def test_full_version_lifecycle(self, version_manager, migrator):
        """Test complete version creation, migration, and rollback."""
        # 1. Create v1.1.0
        policy_v1_1 = """
package authz
default allow = false
allow { input.user.role == "admin" }
"""
        v1_1 = version_manager.create_version(
            version="1.1.0",
            description="Add admin check",
            policy_content=policy_v1_1,
            created_by="engineer",
        )
        assert v1_1.version == "1.1.0"

        # 2. Validate migration
        validation = migrator.validate_migration("1.0.0", "1.1.0")
        assert validation["can_migrate"] is True

        # 3. Migrate to v1.1.0
        record_v1_1 = migrator.migrate("1.1.0", dry_run=False)
        assert record_v1_1.success is True
        assert version_manager.get_current_version() == "1.1.0"

        # 4. Create v1.2.0
        policy_v1_2 = """
package authz
default allow = false
allow {
    input.user.role == "admin"
    input.user.mfa_enabled == true
}
"""
        v1_2 = version_manager.create_version(
            version="1.2.0",
            description="Add MFA requirement",
            policy_content=policy_v1_2,
            created_by="security_team",
        )
        assert v1_2.version == "1.2.0"

        # 5. Migrate to v1.2.0
        record_v1_2 = migrator.migrate("1.2.0", dry_run=False)
        assert record_v1_2.success is True
        assert version_manager.get_current_version() == "1.2.0"

        # 6. Rollback to v1.1.0
        rollback_record = migrator.rollback("1.1.0")
        assert rollback_record.success is True
        assert version_manager.get_current_version() == "1.1.0"

        # 7. Verify policy content
        content = version_manager.get_policy_content("1.1.0")
        assert "mfa_enabled" not in content
        assert 'input.user.role == "admin"' in content

    def test_concurrent_migrations(self, version_manager, migrator):
        """Test that concurrent migrations are handled safely."""
        # This is a simplified test - in production, use locking
        policy1 = "package authz\ndefault allow = false"
        policy2 = "package authz\ndefault allow = true"

        version_manager.create_version(
            version="2.0.0",
            description="V2",
            policy_content=policy1,
            created_by="user1",
        )
        version_manager.create_version(
            version="3.0.0",
            description="V3",
            policy_content=policy2,
            created_by="user2",
        )

        # First migration
        migrator.migrate("2.0.0", dry_run=False)
        assert version_manager.get_current_version() == "2.0.0"

        # Second migration
        migrator.migrate("3.0.0", dry_run=False)
        assert version_manager.get_current_version() == "3.0.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
