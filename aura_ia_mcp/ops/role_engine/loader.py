"""Role Loader for ARE+ Role Engine.

Loads roles from JSON/YAML files and maintains a registry.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)

DEFAULT_ROLES_DIR = Path("ops/role_engine/roles")
DEFAULT_REGISTRY_FILE = Path("ops/role_engine/role_registry_v2.json")


@dataclass
class ScoringProfile:
    """Role scoring profile."""

    priority: int = 5  # 1-10
    confidence_weight: float = 0.5  # 0.0-1.0
    risk_factor: float = 0.5  # 0.0-1.0


@dataclass
class Role:
    """Role definition."""

    name: str
    purpose: str
    capabilities: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    behaviors: list[str] = field(default_factory=list)
    interactions: list[str] = field(default_factory=list)
    scoring_profile: ScoringProfile = field(default_factory=ScoringProfile)
    version: str = "1.0.0"
    metadata: dict[str, Any] = field(default_factory=dict)


class RoleRegistry:
    """Role registry with loading and caching."""

    def __init__(
        self, roles_dir: Path | None = None, registry_file: Path | None = None
    ):
        self.roles_dir = roles_dir or DEFAULT_ROLES_DIR
        self.registry_file = registry_file or DEFAULT_REGISTRY_FILE
        self.roles: dict[str, Role] = {}
        self.version = "2.0.0"
        self.loaded_at: str | None = None

    def load_from_json(self, file_path: Path) -> dict[str, Role]:
        """Load roles from JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Dictionary of role name to Role object
        """
        if not file_path.exists():
            logger.warning(f"JSON file not found: {file_path}")
            return {}

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            roles = {}
            roles_data = data.get("roles", {})

            for name, role_data in roles_data.items():
                # Extract scoring profile
                scoring_data = role_data.get("scoring_profile", {})
                scoring = ScoringProfile(
                    priority=scoring_data.get("priority", 5),
                    confidence_weight=scoring_data.get(
                        "confidence_weight", 0.5
                    ),
                    risk_factor=scoring_data.get("risk_factor", 0.5),
                )

                # Create role
                role = Role(
                    name=name,
                    purpose=role_data.get("purpose", ""),
                    capabilities=role_data.get("capabilities", []),
                    responsibilities=role_data.get("responsibilities", []),
                    behaviors=role_data.get("behaviors", []),
                    interactions=role_data.get("interactions", []),
                    scoring_profile=scoring,
                    version=role_data.get("version", "1.0.0"),
                    metadata=role_data.get("metadata", {}),
                )

                roles[name] = role

            logger.info(f"Loaded {len(roles)} roles from {file_path}")
            return roles

        except Exception as e:
            logger.exception(f"Error loading roles from JSON: {e}")
            return {}

    def load_from_yaml(self, file_path: Path) -> Role | None:
        """Load a single role from YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            Role object if successful, None otherwise
        """
        if not YAML_AVAILABLE:
            logger.error("PyYAML not installed, cannot load YAML files")
            return None

        if not file_path.exists():
            logger.warning(f"YAML file not found: {file_path}")
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Extract scoring profile
            scoring_data = data.get("scoring_profile", {})
            scoring = ScoringProfile(
                priority=scoring_data.get("priority", 5),
                confidence_weight=scoring_data.get("confidence_weight", 0.5),
                risk_factor=scoring_data.get("risk_factor", 0.5),
            )

            # Create role
            role = Role(
                name=data.get("name", file_path.stem),
                purpose=data.get("purpose", ""),
                capabilities=data.get("capabilities", []),
                responsibilities=data.get("responsibilities", []),
                behaviors=data.get("behaviors", []),
                interactions=data.get("interactions", []),
                scoring_profile=scoring,
                version=data.get("version", "1.0.0"),
                metadata=data.get("metadata", {}),
            )

            logger.info(f"Loaded role '{role.name}' from {file_path}")
            return role

        except Exception as e:
            logger.exception(f"Error loading role from YAML: {e}")
            return None

    def load_all(self) -> dict[str, Role]:
        """Load all roles from registry and YAML files.

        Returns:
            Dictionary of role name to Role object
        """
        all_roles = {}

        # Load from main registry JSON
        if self.registry_file.exists():
            json_roles = self.load_from_json(self.registry_file)
            all_roles.update(json_roles)

        # Load from individual YAML files
        if self.roles_dir.exists():
            for yaml_file in self.roles_dir.glob("*.yaml"):
                role = self.load_from_yaml(yaml_file)
                if role:
                    all_roles[role.name] = role

            for yml_file in self.roles_dir.glob("*.yml"):
                role = self.load_from_yaml(yml_file)
                if role:
                    all_roles[role.name] = role

        self.roles = all_roles
        self.loaded_at = datetime.utcnow().isoformat()
        logger.info(f"Total roles loaded: {len(all_roles)}")

        return all_roles

    def get_role(self, name: str) -> Role | None:
        """Get role by name.

        Args:
            name: Role name

        Returns:
            Role object if found, None otherwise
        """
        return self.roles.get(name)

    def list_roles(self) -> list[str]:
        """List all role names.

        Returns:
            List of role names
        """
        return list(self.roles.keys())

    def get_roles_by_capability(self, capability: str) -> list[Role]:
        """Get roles that have a specific capability.

        Args:
            capability: Capability name

        Returns:
            List of roles with that capability
        """
        return [
            role
            for role in self.roles.values()
            if capability in role.capabilities
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert registry to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "version": self.version,
            "loaded_at": self.loaded_at,
            "roles": {name: asdict(role) for name, role in self.roles.items()},
        }


# Global registry instance
_registry: RoleRegistry | None = None


def get_registry() -> RoleRegistry:
    """Get or create global role registry.

    Returns:
        RoleRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = RoleRegistry()
        _registry.load_all()
    return _registry


def load_role_registry() -> dict:
    """Legacy function for backward compatibility.

    Returns:
        Dictionary with roles and version
    """
    registry = get_registry()
    return {
        "roles": registry.list_roles(),
        "version": registry.version,
        "loaded_at": registry.loaded_at,
    }
