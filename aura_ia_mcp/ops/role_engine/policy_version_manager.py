"""Policy versioning and migration framework."""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class PolicyVersion:
    """Policy version metadata."""

    version: str
    description: str
    created_at: str
    created_by: str
    # Optional for backward-compatibility with legacy manifests
    checksum: str | None = None
    migration_script: str | None = None


class PolicyVersionManager:
    """Manage policy versions and migrations."""

    def __init__(
        self, versions_dir: str = "aura_ia_mcp/ops/role_engine/policy_versions"
    ):
        self.versions_dir = Path(versions_dir)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_file = self.versions_dir / "manifest.json"
        self._load_manifest()

    def _load_manifest(self) -> None:
        """Load the version manifest."""
        if self.manifest_file.exists():
            with open(self.manifest_file) as f:
                self.manifest = json.load(f)
        else:
            self.manifest = {"current_version": None, "versions": []}

    def _save_manifest(self) -> None:
        """Save the version manifest."""
        with open(self.manifest_file, "w") as f:
            json.dump(self.manifest, f, indent=2)

    def _calculate_checksum(self, policy_content: str) -> str:
        """Calculate SHA-256 checksum of policy content."""
        return hashlib.sha256(policy_content.encode()).hexdigest()

    def create_version(
        self,
        version: str,
        description: str,
        policy_content: str,
        created_by: str = "system",
        migration_script: str | None = None,
    ) -> PolicyVersion:
        """
        Create a new policy version.

        Args:
            version: Version identifier (e.g., "1.0.0")
            description: Human-readable description
            policy_content: The actual policy (Rego) content
            created_by: Who created this version
            migration_script: Optional migration script

        Returns:
            PolicyVersion object
        """
        # Validate policy before creating
        validation = self.validate_policy(policy_content)
        if not validation["valid"]:
            raise ValueError(
                f"Invalid policy: {'; '.join(validation['errors'])}"
            )

        # Check duplicate version
        if any(v.get("version") == version for v in self.manifest["versions"]):
            raise ValueError(f"Version {version} already exists")

        checksum = self._calculate_checksum(policy_content)

        policy_version = PolicyVersion(
            version=version,
            description=description,
            created_at=datetime.utcnow().isoformat(),
            created_by=created_by,
            checksum=checksum,
            migration_script=migration_script,
        )

        # Save policy content
        version_dir = self.versions_dir / version
        version_dir.mkdir(exist_ok=True)

        policy_file = version_dir / "policy.rego"
        with open(policy_file, "w") as f:
            f.write(policy_content)

        # Save metadata
        metadata_file = version_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(asdict(policy_version), f, indent=2)

        # Save migration script if provided
        if migration_script:
            migration_file = version_dir / "migration.py"
            with open(migration_file, "w") as f:
                f.write(migration_script)

        # Update manifest (do not change current_version here)
        self.manifest["versions"].append(asdict(policy_version))
        self._save_manifest()

        return policy_version

    def get_version(self, version: str) -> PolicyVersion | None:
        """Get metadata for a specific version."""
        for v in self.manifest["versions"]:
            if v.get("version") == version:
                # Fill missing checksum if needed
                if "checksum" not in v or v.get("checksum") in (None, ""):
                    content = self.get_policy_content(version)
                    v = {**v}
                    v["checksum"] = (
                        self._calculate_checksum(content) if content else None
                    )
                return PolicyVersion(**v)
        return None

    def get_current_version(self) -> str | None:
        """Get the current active version."""
        return self.manifest.get("current_version")

    def list_versions(self) -> list[PolicyVersion]:
        """List all versions."""
        result: list[PolicyVersion] = []
        for v in self.manifest["versions"]:
            vv = {**v}
            if "checksum" not in vv or vv.get("checksum") in (None, ""):
                content = self.get_policy_content(vv.get("version", ""))
                vv["checksum"] = (
                    self._calculate_checksum(content) if content else None
                )
            result.append(PolicyVersion(**vv))
        return result

    def get_policy_content(self, version: str) -> str | None:
        """Load policy content for a specific version."""
        policy_file = self.versions_dir / version / "policy.rego"
        if policy_file.exists():
            return policy_file.read_text()
        return None

    def validate_policy(self, policy_content: str) -> dict[str, Any]:
        """
        Validate policy syntax and structure.

        Returns:
            Validation result with 'valid' boolean and 'errors' list
        """
        errors = []

        # Basic validation checks
        if not policy_content.strip():
            errors.append("Policy content is empty")

        if "package " not in policy_content:
            errors.append("Missing package declaration")

        # Check for common syntax patterns
        if policy_content.count("{") != policy_content.count("}"):
            errors.append("Unmatched braces")

        if policy_content.count("[") != policy_content.count("]"):
            errors.append("Unmatched brackets")

        return {"valid": len(errors) == 0, "errors": errors}
