"""
Role Taxonomy - Hierarchical Role Management System.

This module implements a structured role taxonomy that defines:
- Role hierarchy with inheritance
- Capability matrices
- Trust levels and escalation paths
- Dynamic role assignment based on context
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TrustLevel(Enum):
    """Trust levels for role hierarchy."""

    UNTRUSTED = 0
    BASIC = 1
    STANDARD = 2
    ELEVATED = 3
    PRIVILEGED = 4
    ADMIN = 5


class CapabilityCategory(Enum):
    """Categories of capabilities."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    APPROVE = "approve"
    DELETE = "delete"
    ADMIN = "admin"


@dataclass
class Capability:
    """A specific capability that can be granted to roles."""

    name: str
    category: CapabilityCategory
    description: str
    risk_score: float = 0.5
    requires_approval: bool = False
    audit_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "risk_score": self.risk_score,
            "requires_approval": self.requires_approval,
            "audit_required": self.audit_required,
        }


@dataclass
class ScoringProfile:
    """Scoring profile for role evaluation."""

    priority: int = 5
    confidence_weight: float = 0.5
    risk_factor: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority": self.priority,
            "confidence_weight": self.confidence_weight,
            "risk_factor": self.risk_factor,
        }


@dataclass
class Role:
    """A role in the taxonomy with capabilities and hierarchy."""

    name: str
    purpose: str
    trust_level: TrustLevel
    capabilities: list[str]
    parent_role: str | None = None
    child_roles: list[str] = field(default_factory=list)
    scoring_profile: ScoringProfile = field(default_factory=ScoringProfile)
    constraints: dict[str, Any] = field(default_factory=dict)
    behaviors: list[str] = field(default_factory=list)
    interactions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "trust_level": self.trust_level.value,
            "capabilities": self.capabilities,
            "parent_role": self.parent_role,
            "child_roles": self.child_roles,
            "scoring_profile": self.scoring_profile.to_dict(),
            "constraints": self.constraints,
            "behaviors": self.behaviors,
            "interactions": self.interactions,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Role":
        """Create Role from dictionary."""
        scoring_data = data.get("scoring_profile", {})
        scoring = ScoringProfile(
            priority=scoring_data.get("priority", 5),
            confidence_weight=scoring_data.get("confidence_weight", 0.5),
            risk_factor=scoring_data.get("risk_factor", 0.5),
        )

        return cls(
            name=data["name"],
            purpose=data.get("purpose", ""),
            trust_level=TrustLevel(data.get("trust_level", 2)),
            capabilities=data.get("capabilities", []),
            parent_role=data.get("parent_role"),
            child_roles=data.get("child_roles", []),
            scoring_profile=scoring,
            constraints=data.get("constraints", {}),
            behaviors=data.get("behaviors", []),
            interactions=data.get("interactions", []),
            metadata=data.get("metadata", {}),
        )


# Standard capability definitions
STANDARD_CAPABILITIES: dict[str, Capability] = {
    # Read capabilities
    "read_code": Capability(
        "read_code",
        CapabilityCategory.READ,
        "Read source code files",
        0.1,
        False,
        True,
    ),
    "read_config": Capability(
        "read_config",
        CapabilityCategory.READ,
        "Read configuration files",
        0.2,
        False,
        True,
    ),
    "read_logs": Capability(
        "read_logs",
        CapabilityCategory.READ,
        "Read system logs",
        0.3,
        False,
        True,
    ),
    "read_secrets": Capability(
        "read_secrets",
        CapabilityCategory.READ,
        "Read secrets/credentials",
        0.9,
        True,
        True,
    ),
    # Write capabilities
    "write_code": Capability(
        "write_code",
        CapabilityCategory.WRITE,
        "Write/modify source code",
        0.6,
        False,
        True,
    ),
    "write_config": Capability(
        "write_config",
        CapabilityCategory.WRITE,
        "Write configuration files",
        0.5,
        False,
        True,
    ),
    "write_docs": Capability(
        "write_docs",
        CapabilityCategory.WRITE,
        "Write documentation",
        0.2,
        False,
        True,
    ),
    # Execute capabilities
    "execute_tests": Capability(
        "execute_tests",
        CapabilityCategory.EXECUTE,
        "Run test suites",
        0.3,
        False,
        True,
    ),
    "execute_scripts": Capability(
        "execute_scripts",
        CapabilityCategory.EXECUTE,
        "Run automation scripts",
        0.5,
        False,
        True,
    ),
    "execute_deploy": Capability(
        "execute_deploy",
        CapabilityCategory.EXECUTE,
        "Run deployment scripts",
        0.8,
        True,
        True,
    ),
    "execute_infra": Capability(
        "execute_infra",
        CapabilityCategory.EXECUTE,
        "Execute infrastructure changes",
        0.9,
        True,
        True,
    ),
    # Approval capabilities
    "approve_code": Capability(
        "approve_code",
        CapabilityCategory.APPROVE,
        "Approve code changes",
        0.6,
        False,
        True,
    ),
    "approve_deploy": Capability(
        "approve_deploy",
        CapabilityCategory.APPROVE,
        "Approve deployments",
        0.8,
        False,
        True,
    ),
    "approve_security": Capability(
        "approve_security",
        CapabilityCategory.APPROVE,
        "Approve security changes",
        0.9,
        False,
        True,
    ),
    # Delete capabilities
    "delete_files": Capability(
        "delete_files",
        CapabilityCategory.DELETE,
        "Delete files",
        0.7,
        True,
        True,
    ),
    "delete_resources": Capability(
        "delete_resources",
        CapabilityCategory.DELETE,
        "Delete cloud resources",
        0.9,
        True,
        True,
    ),
    # Admin capabilities
    "manage_roles": Capability(
        "manage_roles",
        CapabilityCategory.ADMIN,
        "Manage role assignments",
        0.8,
        True,
        True,
    ),
    "manage_policies": Capability(
        "manage_policies",
        CapabilityCategory.ADMIN,
        "Manage security policies",
        0.9,
        True,
        True,
    ),
    # Agent-specific capabilities
    "query": Capability(
        "query",
        CapabilityCategory.READ,
        "Query knowledge bases",
        0.2,
        False,
        True,
    ),
    "upsert_memory": Capability(
        "upsert_memory",
        CapabilityCategory.WRITE,
        "Update agent memory",
        0.4,
        False,
        True,
    ),
    "route": Capability(
        "route",
        CapabilityCategory.EXECUTE,
        "Route requests to agents",
        0.3,
        False,
        True,
    ),
    "delegate": Capability(
        "delegate",
        CapabilityCategory.EXECUTE,
        "Delegate tasks to other agents",
        0.4,
        False,
        True,
    ),
    "orchestrate": Capability(
        "orchestrate",
        CapabilityCategory.EXECUTE,
        "Orchestrate multi-agent workflows",
        0.6,
        False,
        True,
    ),
    "merge": Capability(
        "merge",
        CapabilityCategory.WRITE,
        "Merge code changes",
        0.7,
        True,
        True,
    ),
    "debug": Capability(
        "debug",
        CapabilityCategory.EXECUTE,
        "Debug and troubleshoot",
        0.4,
        False,
        True,
    ),
    "block_action": Capability(
        "block_action",
        CapabilityCategory.APPROVE,
        "Block risky actions",
        0.8,
        False,
        True,
    ),
}


# Default role taxonomy
DEFAULT_TAXONOMY: dict[str, dict[str, Any]] = {
    "Root": {
        "purpose": "System root role",
        "trust_level": 5,
        "capabilities": list(STANDARD_CAPABILITIES.keys()),
        "parent_role": None,
        "child_roles": ["Administrator", "Lead Engineer", "Security Officer"],
    },
    "Administrator": {
        "purpose": "System administration",
        "trust_level": 5,
        "capabilities": [
            "manage_roles",
            "manage_policies",
            "read_secrets",
            "execute_infra",
            "delete_resources",
        ],
        "parent_role": "Root",
        "child_roles": [],
    },
    "Lead Engineer": {
        "purpose": "Technical leadership and automation",
        "trust_level": 4,
        "capabilities": [
            "orchestrate",
            "write_code",
            "execute_deploy",
            "approve_code",
            "execute_tests",
            "merge",
            "debug",
            "read_code",
            "read_config",
        ],
        "parent_role": "Root",
        "child_roles": [
            "Senior Architect",
            "Full-Stack Guru",
            "DevOps Engineer",
        ],
        "scoring_profile": {
            "priority": 9,
            "confidence_weight": 0.9,
            "risk_factor": 0.9,
        },
    },
    "Security Officer": {
        "purpose": "Security and compliance oversight",
        "trust_level": 5,
        "capabilities": [
            "approve_security",
            "block_action",
            "read_logs",
            "read_secrets",
            "manage_policies",
            "approve_deploy",
        ],
        "parent_role": "Root",
        "child_roles": [],
        "scoring_profile": {
            "priority": 10,
            "confidence_weight": 0.95,
            "risk_factor": 1.0,
        },
    },
    "Senior Architect": {
        "purpose": "Architecture design and strategy",
        "trust_level": 4,
        "capabilities": [
            "write_code",
            "read_code",
            "write_docs",
            "approve_code",
            "execute_tests",
            "debug",
        ],
        "parent_role": "Lead Engineer",
        "child_roles": ["Developer"],
        "scoring_profile": {
            "priority": 9,
            "confidence_weight": 0.85,
            "risk_factor": 0.8,
        },
    },
    "Full-Stack Guru": {
        "purpose": "Full-stack development and integration",
        "trust_level": 4,
        "capabilities": [
            "write_code",
            "read_code",
            "merge",
            "debug",
            "execute_tests",
            "write_config",
        ],
        "parent_role": "Lead Engineer",
        "child_roles": ["Developer"],
        "scoring_profile": {
            "priority": 8,
            "confidence_weight": 0.9,
            "risk_factor": 0.9,
        },
    },
    "DevOps Engineer": {
        "purpose": "Infrastructure and deployment automation",
        "trust_level": 4,
        "capabilities": [
            "execute_deploy",
            "execute_infra",
            "execute_scripts",
            "write_config",
            "read_logs",
            "debug",
        ],
        "parent_role": "Lead Engineer",
        "child_roles": [],
        "scoring_profile": {
            "priority": 8,
            "confidence_weight": 0.8,
            "risk_factor": 0.85,
        },
    },
    "Developer": {
        "purpose": "Software development",
        "trust_level": 3,
        "capabilities": [
            "write_code",
            "read_code",
            "execute_tests",
            "debug",
            "write_docs",
        ],
        "parent_role": "Senior Architect",
        "child_roles": ["Junior Developer"],
        "scoring_profile": {
            "priority": 6,
            "confidence_weight": 0.7,
            "risk_factor": 0.6,
        },
    },
    "Junior Developer": {
        "purpose": "Entry-level development",
        "trust_level": 2,
        "capabilities": ["read_code", "execute_tests", "write_docs"],
        "parent_role": "Developer",
        "child_roles": [],
        "scoring_profile": {
            "priority": 4,
            "confidence_weight": 0.5,
            "risk_factor": 0.3,
        },
    },
    "Researcher": {
        "purpose": "Research, analysis, and RAG operations",
        "trust_level": 2,
        "capabilities": [
            "query",
            "upsert_memory",
            "read_code",
            "read_logs",
            "write_docs",
        ],
        "parent_role": None,
        "child_roles": [],
        "scoring_profile": {
            "priority": 4,
            "confidence_weight": 0.5,
            "risk_factor": 0.2,
        },
    },
    "Product Owner": {
        "purpose": "Requirements and acceptance criteria",
        "trust_level": 3,
        "capabilities": ["approve_code", "read_code", "write_docs", "query"],
        "parent_role": None,
        "child_roles": [],
        "scoring_profile": {
            "priority": 7,
            "confidence_weight": 0.6,
            "risk_factor": 0.6,
        },
    },
    "Knowledge Curator": {
        "purpose": "Documentation and memory management",
        "trust_level": 2,
        "capabilities": ["write_docs", "upsert_memory", "query", "read_code"],
        "parent_role": None,
        "child_roles": [],
        "scoring_profile": {
            "priority": 3,
            "confidence_weight": 0.4,
            "risk_factor": 0.1,
        },
    },
    "Coordinator": {
        "purpose": "Multi-agent coordination and routing",
        "trust_level": 3,
        "capabilities": ["route", "delegate", "query", "read_logs"],
        "parent_role": None,
        "child_roles": [],
        "scoring_profile": {
            "priority": 6,
            "confidence_weight": 0.6,
            "risk_factor": 0.5,
        },
    },
    "UX Designer": {
        "purpose": "User experience and interface design",
        "trust_level": 2,
        "capabilities": ["read_code", "write_docs", "write_code"],
        "parent_role": None,
        "child_roles": [],
        "scoring_profile": {
            "priority": 2,
            "confidence_weight": 0.3,
            "risk_factor": 0.1,
        },
    },
}


class RoleTaxonomy:
    """
    Manages the role hierarchy and capability assignments.

    Provides:
    - Role lookup and inheritance resolution
    - Capability checking with hierarchy traversal
    - Trust level evaluation
    - Dynamic role assignment suggestions
    """

    def __init__(
        self,
        registry_path: str | None = None,
        auto_load: bool = True,
    ):
        self.registry_path = registry_path or os.environ.get(
            "ROLE_REGISTRY_PATH", "ops/role_engine/role_taxonomy.json"
        )
        self.roles: dict[str, Role] = {}
        self.capabilities = STANDARD_CAPABILITIES.copy()
        self.version = "2.0.0"
        self.loaded_at: float | None = None

        if auto_load:
            self._load_or_init()

    def _load_or_init(self) -> None:
        """Load registry from file or initialize with defaults."""
        try:
            if Path(self.registry_path).exists():
                self._load_from_file()
            else:
                self._init_default_taxonomy()
        except Exception as e:
            logger.warning(f"Failed to load taxonomy, using defaults: {e}")
            self._init_default_taxonomy()

    def _load_from_file(self) -> None:
        """Load taxonomy from JSON file."""
        with open(self.registry_path) as f:
            data = json.load(f)

        self.version = data.get("meta", {}).get("version", "2.0.0")

        roles_data = data.get("roles", {})
        for name, role_data in roles_data.items():
            role_data["name"] = name
            self.roles[name] = Role.from_dict(role_data)

        self.loaded_at = time.time()
        logger.info(
            f"Loaded {len(self.roles)} roles from {self.registry_path}"
        )

    def _init_default_taxonomy(self) -> None:
        """Initialize with default taxonomy."""
        for name, data in DEFAULT_TAXONOMY.items():
            data["name"] = name
            self.roles[name] = Role.from_dict(data)

        self.loaded_at = time.time()
        logger.info(
            f"Initialized default taxonomy with {len(self.roles)} roles"
        )

    def save(self) -> None:
        """Save taxonomy to file."""
        data = {
            "meta": {
                "version": self.version,
                "updated_at": time.time(),
            },
            "roles": {
                name: role.to_dict() for name, role in self.roles.items()
            },
        }

        Path(self.registry_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved taxonomy to {self.registry_path}")

    def get_role(self, name: str) -> Role | None:
        """Get role by name."""
        return self.roles.get(name)

    def list_roles(self) -> list[str]:
        """List all role names."""
        return list(self.roles.keys())

    def get_effective_capabilities(self, role_name: str) -> set[str]:
        """
        Get all effective capabilities for a role, including inherited ones.

        Traverses the role hierarchy upward to collect inherited capabilities.
        """
        role = self.get_role(role_name)
        if not role:
            return set()

        capabilities = set(role.capabilities)

        # Traverse parent hierarchy
        current = role
        while current.parent_role:
            parent = self.get_role(current.parent_role)
            if not parent:
                break
            capabilities.update(parent.capabilities)
            current = parent

        return capabilities

    def has_capability(self, role_name: str, capability: str) -> bool:
        """Check if role has a specific capability (including inherited)."""
        return capability in self.get_effective_capabilities(role_name)

    def get_trust_level(self, role_name: str) -> TrustLevel:
        """Get trust level for a role."""
        role = self.get_role(role_name)
        return role.trust_level if role else TrustLevel.UNTRUSTED

    def can_escalate_to(self, from_role: str, to_role: str) -> bool:
        """Check if escalation from one role to another is permitted."""
        from_r = self.get_role(from_role)
        to_r = self.get_role(to_role)

        if not from_r or not to_r:
            return False

        # Can only escalate to roles with equal or lower trust
        if to_r.trust_level.value > from_r.trust_level.value:
            return False

        # Check if target is a descendant in hierarchy
        return self._is_descendant(from_role, to_role)

    def _is_descendant(self, ancestor: str, descendant: str) -> bool:
        """Check if descendant is in the hierarchy under ancestor."""
        role = self.get_role(ancestor)
        if not role:
            return False

        if descendant in role.child_roles:
            return True

        for child in role.child_roles:
            if self._is_descendant(child, descendant):
                return True

        return False

    def suggest_role_for_task(
        self,
        task_description: str,
        required_capabilities: list[str],
        min_trust_level: TrustLevel = TrustLevel.BASIC,
    ) -> list[tuple[str, float]]:
        """
        Suggest suitable roles for a task.

        Returns list of (role_name, score) tuples, sorted by score descending.
        """
        suggestions = []

        for name, role in self.roles.items():
            # Check trust level
            if role.trust_level.value < min_trust_level.value:
                continue

            # Calculate capability match score
            effective_caps = self.get_effective_capabilities(name)
            matched = len(set(required_capabilities) & effective_caps)
            total = len(required_capabilities)
            cap_score = matched / total if total > 0 else 0.0

            # Weight by priority
            priority_weight = role.scoring_profile.priority / 10.0

            # Final score
            score = cap_score * 0.7 + priority_weight * 0.3

            if score > 0:
                suggestions.append((name, score))

        return sorted(suggestions, key=lambda x: x[1], reverse=True)

    def evaluate_action_risk(
        self, role_name: str, capability: str
    ) -> dict[str, Any]:
        """
        Evaluate the risk of a role performing a capability.

        Returns risk assessment with approval requirements.
        """
        role = self.get_role(role_name)
        cap = self.capabilities.get(capability)

        if not role or not cap:
            return {
                "allowed": False,
                "risk_score": 1.0,
                "requires_approval": True,
                "reason": "Unknown role or capability",
            }

        # Check if role has capability
        has_cap = self.has_capability(role_name, capability)

        if not has_cap:
            return {
                "allowed": False,
                "risk_score": 1.0,
                "requires_approval": True,
                "reason": f"Role '{role_name}' lacks capability '{capability}'",
            }

        # Calculate combined risk
        combined_risk = (
            cap.risk_score + role.scoring_profile.risk_factor
        ) / 2.0

        # Determine if approval needed
        requires_approval = (
            cap.requires_approval
            or combined_risk > 0.7
            or role.trust_level.value < TrustLevel.ELEVATED.value
        )

        return {
            "allowed": True,
            "risk_score": combined_risk,
            "requires_approval": requires_approval,
            "audit_required": cap.audit_required,
            "capability_risk": cap.risk_score,
            "role_risk": role.scoring_profile.risk_factor,
            "trust_level": role.trust_level.value,
        }

    def add_role(self, role: Role) -> bool:
        """Add or update a role in the taxonomy."""
        self.roles[role.name] = role
        logger.info(f"Added/updated role: {role.name}")
        return True

    def remove_role(self, name: str) -> bool:
        """Remove a role from the taxonomy."""
        if name in self.roles:
            # Remove from parent's child list
            role = self.roles[name]
            if role.parent_role:
                parent = self.get_role(role.parent_role)
                if parent and name in parent.child_roles:
                    parent.child_roles.remove(name)

            del self.roles[name]
            logger.info(f"Removed role: {name}")
            return True
        return False


# Global taxonomy instance
_taxonomy: RoleTaxonomy | None = None


def get_taxonomy() -> RoleTaxonomy:
    """Get global taxonomy instance."""
    global _taxonomy
    if _taxonomy is None:
        _taxonomy = RoleTaxonomy()
    return _taxonomy
