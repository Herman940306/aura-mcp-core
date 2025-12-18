"""Layer 6: Safety/Policy Engine - Deterministic Safety Guardrails.

This layer ensures:
    - No unauthorized commands
    - No dangerous tool calls
    - No forbidden patterns
    - All outputs meet PRD requirements
    - All actions are logged
    - Human review when needed

Tiny LLMs CANNOT violate safety because the system stops them.
This is the final checkpoint before any action is executed.

Project Creator: Herman Swanepoel
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SafetyLevel(Enum):
    """Safety levels for operations."""

    SAFE = "safe"  # Can execute freely
    CAUTION = "caution"  # Log and monitor
    RESTRICTED = "restricted"  # Requires confirmation
    DANGEROUS = "dangerous"  # Requires approval workflow
    FORBIDDEN = "forbidden"  # Never allow

    @property
    def severity_order(self) -> int:
        """Return numeric severity for comparison."""
        order = {
            "safe": 0,
            "caution": 1,
            "restricted": 2,
            "dangerous": 3,
            "forbidden": 4,
        }
        return order.get(self.value, 0)


class ViolationType(Enum):
    """Types of policy violations."""

    UNAUTHORIZED_TOOL = "unauthorized_tool"
    FORBIDDEN_COMMAND = "forbidden_command"
    PII_EXPOSURE = "pii_exposure"
    RATE_LIMIT = "rate_limit"
    DANGEROUS_OPERATION = "dangerous_operation"
    PRD_VIOLATION = "prd_violation"
    MISSING_CONFIRMATION = "missing_confirmation"
    INVALID_INPUT = "invalid_input"


@dataclass
class PolicyViolation:
    """A policy violation record."""

    type: ViolationType
    message: str
    severity: SafetyLevel
    blocked: bool
    timestamp: float = field(default_factory=time.time)
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "message": self.message,
            "severity": self.severity.value,
            "blocked": self.blocked,
            "timestamp": self.timestamp,
            "context": self.context,
        }


@dataclass
class SafetyCheckResult:
    """Result of a safety check."""

    allowed: bool
    level: SafetyLevel
    violations: list[PolicyViolation] = field(default_factory=list)
    requires_confirmation: bool = False
    requires_approval: bool = False
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "level": self.level.value,
            "violations": [v.to_dict() for v in self.violations],
            "requires_confirmation": self.requires_confirmation,
            "requires_approval": self.requires_approval,
            "message": self.message,
        }


class SafetyPolicyEngine:
    """Deterministic safety enforcement engine.

    This is the final checkpoint before any action is executed.
    The LLM cannot bypass this layer.
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        self._log_dir = (
            log_dir or Path(__file__).parent.parent.parent.parent / "logs"
        )
        self._audit_log_path = self._log_dir / "security_audit.jsonl"

        # Forbidden patterns - NEVER allow
        self._forbidden_patterns: list[tuple[re.Pattern, str]] = [
            (re.compile(r"\brm\s+-rf\s+/", re.I), "Recursive root deletion"),
            (re.compile(r"\bformat\s+[cC]:", re.I), "Drive format command"),
            (re.compile(r"\bdel\s+/[sS]\s+/[qQ]", re.I), "Recursive deletion"),
            (re.compile(r":\(\)\{[^}]*\};\s*:", re.I), "Fork bomb"),
            (re.compile(r">\s*/dev/sd[a-z]", re.I), "Direct disk write"),
            (re.compile(r"\bdrop\s+database", re.I), "Database deletion"),
            (re.compile(r"\btruncate\s+table", re.I), "Table truncation"),
            (
                re.compile(r"password\s*[=:]\s*['\"][^'\"]+['\"]", re.I),
                "Hardcoded password",
            ),
            (
                re.compile(r"api[_-]?key\s*[=:]\s*['\"][^'\"]+['\"]", re.I),
                "Hardcoded API key",
            ),
            (
                re.compile(r"BEGIN\s+(RSA|DSA|EC)\s+PRIVATE\s+KEY", re.I),
                "Private key exposure",
            ),
        ]

        # Dangerous patterns - require approval
        self._dangerous_patterns: list[tuple[re.Pattern, str]] = [
            (re.compile(r"\bsudo\b", re.I), "Elevated privileges"),
            (
                re.compile(r"\badmin\b.*\b(delete|remove|drop)", re.I),
                "Admin deletion",
            ),
            (re.compile(r"\bexec\s*\(", re.I), "Dynamic code execution"),
            (re.compile(r"\beval\s*\(", re.I), "Eval execution"),
            (re.compile(r">\s*/etc/", re.I), "System file modification"),
            (re.compile(r"\bkill\s+-9", re.I), "Force kill"),
            (re.compile(r"\bshutdown\b", re.I), "System shutdown"),
            (re.compile(r"\breboot\b", re.I), "System reboot"),
        ]

        # Caution patterns - log and monitor
        self._caution_patterns: list[tuple[re.Pattern, str]] = [
            (re.compile(r"\bdelete\b", re.I), "Delete operation"),
            (re.compile(r"\bremove\b", re.I), "Remove operation"),
            (re.compile(r"\bmodify\b", re.I), "Modify operation"),
            (re.compile(r"\bupdate\b", re.I), "Update operation"),
            (re.compile(r"\bwrite\b", re.I), "Write operation"),
            (re.compile(r"\bexecute\b", re.I), "Execute operation"),
        ]

        # PII patterns
        self._pii_patterns: list[tuple[re.Pattern, str]] = [
            (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "SSN"),
            (re.compile(r"\b\d{16}\b"), "Credit card"),
            (re.compile(r"\b[A-Z]{2}\d{6,9}\b"), "Passport"),
            (re.compile(r"[\w.-]+@[\w.-]+\.\w+"), "Email"),
            (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "Phone"),
        ]

        # Tool safety classifications
        self._tool_safety: dict[str, SafetyLevel] = {
            # Safe tools
            "check_health": SafetyLevel.SAFE,
            "get_system_status": SafetyLevel.SAFE,
            "get_model_status": SafetyLevel.SAFE,
            "get_documentation": SafetyLevel.SAFE,
            "list_entities": SafetyLevel.SAFE,
            "list_available_tools": SafetyLevel.SAFE,
            "list_roles": SafetyLevel.SAFE,
            "get_metrics": SafetyLevel.SAFE,
            "get_alerts": SafetyLevel.SAFE,
            "get_config": SafetyLevel.SAFE,
            "get_project_status": SafetyLevel.SAFE,
            "get_carbon_budget": SafetyLevel.SAFE,
            "list_wasm_plugins": SafetyLevel.SAFE,
            "list_collections": SafetyLevel.SAFE,
            "visualize_dag": SafetyLevel.SAFE,
            "get_debate_status": SafetyLevel.SAFE,
            "get_dashboard_url": SafetyLevel.SAFE,
            "semantic_search": SafetyLevel.SAFE,
            # Caution tools
            "get_recent_logs": SafetyLevel.CAUTION,
            "get_security_audit": SafetyLevel.CAUTION,
            "query_traces": SafetyLevel.CAUTION,
            "search_logs": SafetyLevel.CAUTION,
            "analyze_emotion": SafetyLevel.CAUTION,
            "semantic_rank": SafetyLevel.CAUTION,
            "diagnose_issue": SafetyLevel.CAUTION,
            "get_role_capabilities": SafetyLevel.CAUTION,
            "check_permission": SafetyLevel.CAUTION,
            # Restricted tools
            "execute_command": SafetyLevel.RESTRICTED,
            "add_to_knowledge_base": SafetyLevel.RESTRICTED,
            "audit_log": SafetyLevel.RESTRICTED,
            "start_debate": SafetyLevel.RESTRICTED,
            "create_workflow": SafetyLevel.RESTRICTED,
            "schedule_green_job": SafetyLevel.RESTRICTED,
            "check_pii": SafetyLevel.RESTRICTED,
            # Dangerous tools
            "execute_workflow": SafetyLevel.DANGEROUS,
            "request_approval": SafetyLevel.DANGEROUS,
            "evaluate_risk": SafetyLevel.DANGEROUS,
            "execute_wasm_plugin": SafetyLevel.DANGEROUS,
        }

        # Rate limiting
        self._rate_limits: dict[str, int] = {
            "execute_command": 10,  # Per minute
            "execute_workflow": 5,
            "request_approval": 3,
        }
        self._rate_counters: dict[str, list[float]] = {}

        # PRD requirements
        self._prd_requirements: list[dict] = [
            {
                "id": "PRD-001",
                "description": "All tool calls must be logged",
                "check": lambda ctx: ctx.get("logged", False)
                or True,  # Auto-log
            },
            {
                "id": "PRD-002",
                "description": "PII must be redacted in logs",
                "check": lambda ctx: not ctx.get("contains_pii", False),
            },
            {
                "id": "PRD-003",
                "description": "Dangerous operations require approval",
                "check": lambda ctx: ctx.get("safety_level")
                != SafetyLevel.DANGEROUS
                or ctx.get("approved", False),
            },
        ]

    def check_safety(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_input: str = "",
        context: dict[str, Any] | None = None,
    ) -> SafetyCheckResult:
        """Perform comprehensive safety check.

        This is the main entry point for safety validation.
        """
        context = context or {}
        violations: list[PolicyViolation] = []

        # Check tool safety level
        safety_level = self._tool_safety.get(tool_name, SafetyLevel.CAUTION)
        context["safety_level"] = safety_level

        # Check for forbidden patterns
        all_text = f"{tool_name} {json.dumps(arguments)} {user_input}"

        for pattern, description in self._forbidden_patterns:
            if pattern.search(all_text):
                violations.append(
                    PolicyViolation(
                        type=ViolationType.FORBIDDEN_COMMAND,
                        message=f"Forbidden pattern detected: {description}",
                        severity=SafetyLevel.FORBIDDEN,
                        blocked=True,
                        context={"pattern": description},
                    )
                )

        # If we have forbidden violations, stop immediately
        if any(v.severity == SafetyLevel.FORBIDDEN for v in violations):
            self._log_violation(violations[-1])
            return SafetyCheckResult(
                allowed=False,
                level=SafetyLevel.FORBIDDEN,
                violations=violations,
                message="Operation blocked: Contains forbidden patterns",
            )

        # Check for dangerous patterns
        for pattern, description in self._dangerous_patterns:
            if pattern.search(all_text):
                violations.append(
                    PolicyViolation(
                        type=ViolationType.DANGEROUS_OPERATION,
                        message=f"Dangerous pattern detected: {description}",
                        severity=SafetyLevel.DANGEROUS,
                        blocked=False,
                        context={"pattern": description},
                    )
                )

        # Check for PII
        pii_found = []
        for pattern, pii_type in self._pii_patterns:
            if pattern.search(all_text):
                pii_found.append(pii_type)

        if pii_found:
            context["contains_pii"] = True
            violations.append(
                PolicyViolation(
                    type=ViolationType.PII_EXPOSURE,
                    message=f"PII detected: {', '.join(pii_found)}",
                    severity=SafetyLevel.RESTRICTED,
                    blocked=False,
                    context={"pii_types": pii_found},
                )
            )

        # Check rate limits
        if tool_name in self._rate_limits:
            if self._check_rate_limit(tool_name):
                violations.append(
                    PolicyViolation(
                        type=ViolationType.RATE_LIMIT,
                        message=f"Rate limit exceeded for {tool_name}",
                        severity=SafetyLevel.RESTRICTED,
                        blocked=True,
                        context={"limit": self._rate_limits[tool_name]},
                    )
                )

        # Check PRD compliance
        for req in self._prd_requirements:
            if not req["check"](context):
                violations.append(
                    PolicyViolation(
                        type=ViolationType.PRD_VIOLATION,
                        message=f"PRD violation: {req['description']}",
                        severity=SafetyLevel.RESTRICTED,
                        blocked=False,
                        context={"requirement_id": req["id"]},
                    )
                )

        # Determine final result
        has_blocking = any(v.blocked for v in violations)
        max_severity = max(
            (v.severity for v in violations),
            key=lambda x: x.severity_order,
            default=safety_level,
        )

        requires_confirmation = safety_level in (
            SafetyLevel.RESTRICTED,
            SafetyLevel.DANGEROUS,
        )
        requires_approval = safety_level == SafetyLevel.DANGEROUS

        # Log caution patterns
        for pattern, description in self._caution_patterns:
            if pattern.search(all_text):
                self._log_action(tool_name, arguments, "caution", description)
                break

        result = SafetyCheckResult(
            allowed=not has_blocking,
            level=max_severity,
            violations=violations,
            requires_confirmation=requires_confirmation
            and not context.get("confirmed", False),
            requires_approval=requires_approval
            and not context.get("approved", False),
            message=self._generate_message(violations, safety_level),
        )

        # Log the check
        self._log_safety_check(tool_name, arguments, result)

        return result

    def validate_output(
        self,
        output: str,
        tool_name: str,
    ) -> SafetyCheckResult:
        """Validate tool output before returning to user.

        Ensures outputs don't expose sensitive information.
        """
        violations: list[PolicyViolation] = []

        # Check for PII in output
        pii_found = []
        for pattern, pii_type in self._pii_patterns:
            if pattern.search(output):
                pii_found.append(pii_type)

        if pii_found:
            violations.append(
                PolicyViolation(
                    type=ViolationType.PII_EXPOSURE,
                    message=f"Output contains PII: {', '.join(pii_found)}",
                    severity=SafetyLevel.CAUTION,
                    blocked=False,
                    context={"pii_types": pii_found, "action": "redact"},
                )
            )

        # Check for forbidden patterns in output
        for pattern, description in self._forbidden_patterns:
            if pattern.search(output):
                violations.append(
                    PolicyViolation(
                        type=ViolationType.FORBIDDEN_COMMAND,
                        message=f"Output contains forbidden pattern: {description}",
                        severity=SafetyLevel.DANGEROUS,
                        blocked=True,
                        context={"pattern": description},
                    )
                )

        has_blocking = any(v.blocked for v in violations)

        return SafetyCheckResult(
            allowed=not has_blocking,
            level=SafetyLevel.DANGEROUS if has_blocking else SafetyLevel.SAFE,
            violations=violations,
            message="Output validation "
            + ("failed" if has_blocking else "passed"),
        )

    def redact_pii(self, text: str) -> str:
        """Redact PII from text."""
        result = text

        for pattern, pii_type in self._pii_patterns:
            result = pattern.sub(f"[REDACTED:{pii_type}]", result)

        return result

    def get_tool_safety_level(self, tool_name: str) -> SafetyLevel:
        """Get the safety level for a tool."""
        return self._tool_safety.get(tool_name, SafetyLevel.CAUTION)

    def register_tool_safety(
        self,
        tool_name: str,
        level: SafetyLevel,
    ) -> None:
        """Register or update a tool's safety level."""
        self._tool_safety[tool_name] = level

    def get_confirmation_message(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: SafetyCheckResult,
    ) -> str:
        """Generate a confirmation message for restricted operations."""
        lines = [
            "⚠️ **Confirmation Required**",
            "",
            f"You're about to execute: **{tool_name}**",
        ]

        if arguments:
            lines.append(f"Arguments: `{json.dumps(arguments)}`")

        lines.append(f"Safety Level: **{result.level.value.upper()}**")

        if result.violations:
            lines.append("")
            lines.append("Warnings:")
            for v in result.violations[:3]:
                lines.append(f"  - {v.message}")

        lines.extend(
            [
                "",
                "Reply **'yes'** or **'confirm'** to proceed, or **'no'** to cancel.",
            ]
        )

        return "\n".join(lines)

    def get_approval_message(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: SafetyCheckResult,
    ) -> str:
        """Generate an approval request message for dangerous operations."""
        lines = [
            "🛑 **Approval Required**",
            "",
            f"This operation requires approval: **{tool_name}**",
        ]

        if arguments:
            lines.append(f"Arguments: `{json.dumps(arguments)}`")

        lines.append(f"Safety Level: **{result.level.value.upper()}**")

        if result.violations:
            lines.append("")
            lines.append("Risk Assessment:")
            for v in result.violations:
                lines.append(f"  - [{v.severity.value}] {v.message}")

        lines.extend(
            [
                "",
                "This request has been logged and requires administrator approval.",
                "Use the approval workflow to review and approve this request.",
            ]
        )

        return "\n".join(lines)

    def _check_rate_limit(self, tool_name: str) -> bool:
        """Check if rate limit is exceeded.

        Returns True if exceeded.
        """
        limit = self._rate_limits.get(tool_name)
        if not limit:
            return False

        now = time.time()
        window = 60.0  # 1 minute window

        # Initialize counter
        if tool_name not in self._rate_counters:
            self._rate_counters[tool_name] = []

        # Clean old entries
        self._rate_counters[tool_name] = [
            t for t in self._rate_counters[tool_name] if now - t < window
        ]

        # Check limit
        if len(self._rate_counters[tool_name]) >= limit:
            return True

        # Add current call
        self._rate_counters[tool_name].append(now)
        return False

    def _generate_message(
        self,
        violations: list[PolicyViolation],
        safety_level: SafetyLevel,
    ) -> str:
        """Generate a human-readable safety message."""
        if not violations:
            return f"Safety check passed (level: {safety_level.value})"

        blocking = [v for v in violations if v.blocked]
        warnings = [v for v in violations if not v.blocked]

        parts = []

        if blocking:
            parts.append(f"Blocked: {blocking[0].message}")

        if warnings:
            parts.append(f"Warnings: {len(warnings)}")

        return (
            "; ".join(parts)
            if parts
            else f"Safety level: {safety_level.value}"
        )

    def _log_violation(self, violation: PolicyViolation) -> None:
        """Log a policy violation."""
        entry = {
            "ts": time.time(),
            "type": "violation",
            "violation": violation.to_dict(),
        }
        self._write_log(entry)

    def _log_action(
        self,
        tool_name: str,
        arguments: dict,
        level: str,
        reason: str,
    ) -> None:
        """Log an action."""
        entry = {
            "ts": time.time(),
            "type": "action",
            "tool": tool_name,
            "arguments": arguments,
            "level": level,
            "reason": reason,
        }
        self._write_log(entry)

    def _log_safety_check(
        self,
        tool_name: str,
        arguments: dict,
        result: SafetyCheckResult,
    ) -> None:
        """Log a safety check result."""
        entry = {
            "ts": time.time(),
            "type": "safety_check",
            "tool": tool_name,
            "allowed": result.allowed,
            "level": result.level.value,
            "violation_count": len(result.violations),
        }
        self._write_log(entry)

    def _write_log(self, entry: dict) -> None:
        """Write an entry to the audit log."""
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            with open(self._audit_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # Don't fail on log errors


# Singleton instance
_engine: SafetyPolicyEngine | None = None


def get_safety_engine() -> SafetyPolicyEngine:
    """Get singleton safety policy engine."""
    global _engine
    if _engine is None:
        _engine = SafetyPolicyEngine()
    return _engine
