"""
Adaptive Risk Router - Dynamic Risk-Based Request Routing.

This module implements intelligent routing of requests based on:
- Risk assessment of the operation
- Role capabilities and trust levels
- System load and availability
- Historical performance data
- Policy constraints

Features:
- Multi-factor risk scoring
- Dynamic threshold adjustment
- Approval escalation paths
- Circuit breaking for high-risk operations
- Audit trail for compliance
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk classification levels."""

    MINIMAL = 1
    LOW = 2
    MODERATE = 3
    HIGH = 4
    CRITICAL = 5


class RouteDecision(Enum):
    """Routing decision types."""

    ALLOW = "allow"
    ALLOW_WITH_AUDIT = "allow_with_audit"
    REQUIRE_APPROVAL = "require_approval"
    ESCALATE = "escalate"
    DENY = "deny"
    DEFER = "defer"


class ApprovalStatus(Enum):
    """Status of approval requests."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    AUTO_APPROVED = "auto_approved"


@dataclass
class RiskFactors:
    """Factors contributing to risk assessment."""

    operation_risk: float = 0.5  # Inherent risk of the operation
    role_risk: float = 0.5  # Risk factor of the requesting role
    context_risk: float = 0.0  # Contextual risk (time, location, etc.)
    history_risk: float = 0.0  # Based on historical patterns
    load_risk: float = 0.0  # System load factor

    def total(self, weights: dict[str, float] | None = None) -> float:
        """Calculate weighted total risk score."""
        weights = weights or {
            "operation": 0.35,
            "role": 0.25,
            "context": 0.15,
            "history": 0.15,
            "load": 0.10,
        }

        return (
            self.operation_risk * weights["operation"]
            + self.role_risk * weights["role"]
            + self.context_risk * weights["context"]
            + self.history_risk * weights["history"]
            + self.load_risk * weights["load"]
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "operation_risk": self.operation_risk,
            "role_risk": self.role_risk,
            "context_risk": self.context_risk,
            "history_risk": self.history_risk,
            "load_risk": self.load_risk,
            "total": self.total(),
        }


@dataclass
class RouteRequest:
    """Request to be routed."""

    request_id: str
    operation: str
    role: str
    resource: str
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "operation": self.operation,
            "role": self.role,
            "resource": self.resource,
            "context": self.context,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class RouteResult:
    """Result of routing decision."""

    request_id: str
    decision: RouteDecision
    risk_level: RiskLevel
    risk_factors: RiskFactors
    reason: str
    approval_required: bool = False
    approval_id: str | None = None
    escalation_path: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    audit_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "decision": self.decision.value,
            "risk_level": self.risk_level.value,
            "risk_factors": self.risk_factors.to_dict(),
            "reason": self.reason,
            "approval_required": self.approval_required,
            "approval_id": self.approval_id,
            "escalation_path": self.escalation_path,
            "conditions": self.conditions,
            "audit_id": self.audit_id,
        }


@dataclass
class ApprovalRequest:
    """Request for approval of high-risk operation."""

    approval_id: str
    request: RouteRequest
    risk_result: RouteResult
    approvers: list[str]
    status: ApprovalStatus = ApprovalStatus.PENDING
    approver: str | None = None
    approval_time: float | None = None
    expiry_time: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "request": self.request.to_dict(),
            "risk_result": self.risk_result.to_dict(),
            "approvers": self.approvers,
            "status": self.status.value,
            "approver": self.approver,
            "approval_time": self.approval_time,
            "expiry_time": self.expiry_time,
            "notes": self.notes,
        }


# Operation risk definitions
OPERATION_RISKS: dict[str, float] = {
    # Read operations (low risk)
    "read": 0.1,
    "query": 0.1,
    "list": 0.1,
    "get": 0.1,
    "search": 0.15,
    # Write operations (moderate risk)
    "write": 0.4,
    "create": 0.3,
    "update": 0.4,
    "modify": 0.4,
    # Execute operations (higher risk)
    "execute": 0.5,
    "run": 0.5,
    "invoke": 0.5,
    "deploy": 0.7,
    # Delete operations (high risk)
    "delete": 0.7,
    "remove": 0.7,
    "purge": 0.8,
    # Admin operations (critical risk)
    "admin": 0.8,
    "configure": 0.6,
    "grant": 0.8,
    "revoke": 0.7,
    "escalate": 0.9,
    # Security operations (critical risk)
    "security": 0.9,
    "audit": 0.3,
    "approve": 0.7,
    "deny": 0.5,
}

# Resource sensitivity levels
RESOURCE_SENSITIVITY: dict[str, float] = {
    "public": 0.1,
    "internal": 0.3,
    "confidential": 0.6,
    "secret": 0.8,
    "top_secret": 1.0,
    # Specific resources
    "code": 0.4,
    "config": 0.5,
    "secrets": 0.9,
    "credentials": 0.95,
    "infrastructure": 0.7,
    "database": 0.6,
    "logs": 0.3,
    "metrics": 0.2,
}


class AdaptiveRiskRouter:
    """
    Intelligent router that makes decisions based on risk assessment.

    Features:
    - Multi-factor risk scoring
    - Dynamic thresholds based on system state
    - Approval workflow integration
    - Circuit breaking for repeated high-risk requests
    - Comprehensive audit logging
    """

    def __init__(
        self,
        role_taxonomy=None,
        audit_log_path: str | None = None,
    ):
        self.role_taxonomy = role_taxonomy
        self.audit_enabled = os.environ.get("RISK_ROUTER_AUDIT", "1") in (
            "1",
            "true",
        )
        self.audit_path = audit_log_path or os.environ.get(
            "RISK_ROUTER_AUDIT_PATH", "logs/risk_router_audit.jsonl"
        )

        # Risk thresholds
        self.thresholds = {
            "auto_approve": float(os.environ.get("RISK_AUTO_APPROVE", "0.3")),
            "require_approval": float(
                os.environ.get("RISK_REQUIRE_APPROVAL", "0.6")
            ),
            "deny": float(os.environ.get("RISK_DENY_THRESHOLD", "0.9")),
        }

        # Approval configuration
        self.approval_timeout = float(
            os.environ.get("APPROVAL_TIMEOUT_SECONDS", "3600")
        )
        self.approvals: dict[str, ApprovalRequest] = {}

        # Circuit breaker state
        self.failure_counts: dict[str, int] = {}
        self.circuit_threshold = int(
            os.environ.get("RISK_CIRCUIT_THRESHOLD", "5")
        )
        self.circuit_timeout = float(
            os.environ.get("RISK_CIRCUIT_TIMEOUT", "300")
        )
        self.circuit_opened_at: dict[str, float] = {}

        # Historical data for adaptive learning
        self.request_history: list[dict[str, Any]] = []
        self.max_history = 1000

        # Escalation paths by risk level
        self.escalation_paths = {
            RiskLevel.HIGH: ["Lead Engineer", "Security Officer"],
            RiskLevel.CRITICAL: ["Security Officer", "Administrator"],
        }

    def _generate_request_id(self, request: RouteRequest) -> str:
        """Generate unique request ID."""
        content = f"{request.operation}:{request.role}:{request.resource}:{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _generate_approval_id(self) -> str:
        """Generate unique approval ID."""
        return hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]

    def _generate_audit_id(self) -> str:
        """Generate unique audit ID."""
        return hashlib.sha256(str(time.time()).encode()).hexdigest()[:10]

    def _log_audit(self, result: RouteResult, request: RouteRequest) -> str:
        """Log routing decision for audit."""
        if not self.audit_enabled:
            return ""

        audit_id = self._generate_audit_id()

        try:
            Path(self.audit_path).parent.mkdir(parents=True, exist_ok=True)

            audit_entry = {
                "audit_id": audit_id,
                "timestamp": time.time(),
                "request": request.to_dict(),
                "result": result.to_dict(),
            }

            with open(self.audit_path, "a") as f:
                f.write(json.dumps(audit_entry) + "\n")

            return audit_id

        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")
            return ""

    def _get_operation_risk(self, operation: str) -> float:
        """Get risk score for an operation."""
        # Exact match
        if operation.lower() in OPERATION_RISKS:
            return OPERATION_RISKS[operation.lower()]

        # Partial match
        for op, risk in OPERATION_RISKS.items():
            if op in operation.lower():
                return risk

        # Default moderate risk for unknown operations
        return 0.5

    def _get_resource_sensitivity(self, resource: str) -> float:
        """Get sensitivity score for a resource."""
        # Exact match
        if resource.lower() in RESOURCE_SENSITIVITY:
            return RESOURCE_SENSITIVITY[resource.lower()]

        # Partial match
        for res, sensitivity in RESOURCE_SENSITIVITY.items():
            if res in resource.lower():
                return sensitivity

        # Default moderate sensitivity
        return 0.5

    def _get_role_risk(self, role: str) -> float:
        """Get risk factor for a role."""
        if self.role_taxonomy:
            role_obj = self.role_taxonomy.get_role(role)
            if role_obj:
                return role_obj.scoring_profile.risk_factor

        # Default fallback
        return 0.5

    def _get_context_risk(self, context: dict[str, Any]) -> float:
        """Calculate contextual risk factors."""
        risk = 0.0

        # Time-based risk (outside business hours)
        hour = context.get("hour", time.localtime().tm_hour)
        if hour < 6 or hour > 22:
            risk += 0.2

        # Weekend risk
        weekday = context.get("weekday", time.localtime().tm_wday)
        if weekday >= 5:
            risk += 0.15

        # Elevated if from external source
        if context.get("source") == "external":
            risk += 0.3

        # Elevated if automated
        if context.get("automated", False):
            risk += 0.1

        return min(1.0, risk)

    def _get_history_risk(self, role: str, operation: str) -> float:
        """Calculate risk based on historical patterns."""
        if not self.request_history:
            return 0.0

        # Look at recent requests from this role
        recent = [
            r for r in self.request_history[-100:] if r.get("role") == role
        ]

        if not recent:
            return 0.0

        # Check failure rate
        failures = sum(1 for r in recent if r.get("failed", False))
        failure_rate = failures / len(recent)

        # Check for unusual patterns (burst activity)
        recent_minute = [
            r for r in recent if time.time() - r.get("timestamp", 0) < 60
        ]
        burst_factor = (
            len(recent_minute) / 10.0
        )  # >10 requests/min is suspicious

        return min(1.0, failure_rate * 0.5 + burst_factor * 0.5)

    def _get_load_risk(self) -> float:
        """Get system load factor (stub - integrate with metrics)."""
        # TODO: Integrate with Prometheus metrics
        return 0.0

    def _is_circuit_open(self, key: str) -> bool:
        """Check if circuit breaker is open for a key."""
        if key not in self.circuit_opened_at:
            return False

        elapsed = time.time() - self.circuit_opened_at[key]
        if elapsed > self.circuit_timeout:
            # Reset circuit
            del self.circuit_opened_at[key]
            self.failure_counts[key] = 0
            return False

        return True

    def _record_failure(self, key: str) -> None:
        """Record a failure for circuit breaker."""
        self.failure_counts[key] = self.failure_counts.get(key, 0) + 1

        if self.failure_counts[key] >= self.circuit_threshold:
            self.circuit_opened_at[key] = time.time()
            logger.warning(f"Circuit breaker opened for: {key}")

    def _classify_risk_level(self, score: float) -> RiskLevel:
        """Classify risk score into level."""
        if score < 0.2:
            return RiskLevel.MINIMAL
        elif score < 0.4:
            return RiskLevel.LOW
        elif score < 0.6:
            return RiskLevel.MODERATE
        elif score < 0.8:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def assess_risk(self, request: RouteRequest) -> RiskFactors:
        """Perform comprehensive risk assessment."""
        # Calculate individual risk factors
        operation_risk = self._get_operation_risk(request.operation)
        resource_sensitivity = self._get_resource_sensitivity(request.resource)

        # Combine operation and resource risk
        combined_op_risk = (operation_risk + resource_sensitivity) / 2.0

        return RiskFactors(
            operation_risk=combined_op_risk,
            role_risk=self._get_role_risk(request.role),
            context_risk=self._get_context_risk(request.context),
            history_risk=self._get_history_risk(
                request.role, request.operation
            ),
            load_risk=self._get_load_risk(),
        )

    def route(self, request: RouteRequest) -> RouteResult:
        """
        Make routing decision for a request.

        Args:
            request: The request to route

        Returns:
            RouteResult with decision and supporting data
        """
        # Check circuit breaker
        circuit_key = f"{request.role}:{request.operation}"
        if self._is_circuit_open(circuit_key):
            return RouteResult(
                request_id=request.request_id,
                decision=RouteDecision.DENY,
                risk_level=RiskLevel.CRITICAL,
                risk_factors=RiskFactors(),
                reason="Circuit breaker open - too many recent failures",
            )

        # Assess risk
        risk_factors = self.assess_risk(request)
        total_risk = risk_factors.total()
        risk_level = self._classify_risk_level(total_risk)

        # Make decision based on thresholds
        decision: RouteDecision
        reason: str
        approval_required = False
        escalation_path: list[str] = []
        conditions: list[str] = []

        if total_risk >= self.thresholds["deny"]:
            decision = RouteDecision.DENY
            reason = f"Risk score {total_risk:.2f} exceeds deny threshold"
            self._record_failure(circuit_key)

        elif total_risk >= self.thresholds["require_approval"]:
            decision = RouteDecision.REQUIRE_APPROVAL
            reason = f"Risk score {total_risk:.2f} requires approval"
            approval_required = True
            escalation_path = self.escalation_paths.get(risk_level, [])

        elif total_risk >= self.thresholds["auto_approve"]:
            decision = RouteDecision.ALLOW_WITH_AUDIT
            reason = "Allowed with mandatory audit logging"
            conditions.append("audit_required")

        else:
            decision = RouteDecision.ALLOW
            reason = "Low risk - auto-approved"

        # Build result
        result = RouteResult(
            request_id=request.request_id,
            decision=decision,
            risk_level=risk_level,
            risk_factors=risk_factors,
            reason=reason,
            approval_required=approval_required,
            escalation_path=escalation_path,
            conditions=conditions,
        )

        # Log audit
        if self.audit_enabled:
            result.audit_id = self._log_audit(result, request)

        # Record in history
        self.request_history.append(
            {
                "timestamp": time.time(),
                "role": request.role,
                "operation": request.operation,
                "risk_score": total_risk,
                "decision": decision.value,
                "failed": decision == RouteDecision.DENY,
            }
        )

        # Trim history
        if len(self.request_history) > self.max_history:
            self.request_history = self.request_history[-self.max_history :]

        logger.info(
            f"Route decision: {request.operation} by {request.role} -> "
            f"{decision.value} (risk={total_risk:.2f})"
        )

        return result

    def create_approval_request(
        self,
        request: RouteRequest,
        result: RouteResult,
    ) -> ApprovalRequest:
        """Create an approval request for high-risk operation."""
        approval_id = self._generate_approval_id()

        approval = ApprovalRequest(
            approval_id=approval_id,
            request=request,
            risk_result=result,
            approvers=result.escalation_path,
            expiry_time=time.time() + self.approval_timeout,
        )

        self.approvals[approval_id] = approval

        logger.info(
            f"Approval request created: {approval_id} for {request.operation}"
        )

        return approval

    def approve(
        self,
        approval_id: str,
        approver: str,
        notes: str = "",
    ) -> bool:
        """Approve a pending approval request."""
        if approval_id not in self.approvals:
            logger.warning(f"Approval not found: {approval_id}")
            return False

        approval = self.approvals[approval_id]

        # Check expiry
        if time.time() > approval.expiry_time:
            approval.status = ApprovalStatus.EXPIRED
            logger.warning(f"Approval expired: {approval_id}")
            return False

        # Check if approver is authorized
        if approver not in approval.approvers:
            logger.warning(f"Unauthorized approver: {approver}")
            return False

        # Approve
        approval.status = ApprovalStatus.APPROVED
        approval.approver = approver
        approval.approval_time = time.time()
        approval.notes = notes

        logger.info(f"Approval granted: {approval_id} by {approver}")

        return True

    def deny(
        self,
        approval_id: str,
        approver: str,
        notes: str = "",
    ) -> bool:
        """Deny a pending approval request."""
        if approval_id not in self.approvals:
            return False

        approval = self.approvals[approval_id]

        if approver not in approval.approvers:
            return False

        approval.status = ApprovalStatus.DENIED
        approval.approver = approver
        approval.approval_time = time.time()
        approval.notes = notes

        logger.info(f"Approval denied: {approval_id} by {approver}")

        return True

    def get_approval_status(self, approval_id: str) -> ApprovalRequest | None:
        """Get status of an approval request."""
        return self.approvals.get(approval_id)

    def cleanup_expired_approvals(self) -> int:
        """Clean up expired approval requests."""
        now = time.time()
        expired = [
            aid
            for aid, a in self.approvals.items()
            if a.status == ApprovalStatus.PENDING and now > a.expiry_time
        ]

        for aid in expired:
            self.approvals[aid].status = ApprovalStatus.EXPIRED

        return len(expired)

    def get_statistics(self) -> dict[str, Any]:
        """Get router statistics."""
        total = len(self.request_history)
        if total == 0:
            return {"total_requests": 0}

        decisions = {}
        risk_levels = {}

        for entry in self.request_history:
            d = entry.get("decision", "unknown")
            decisions[d] = decisions.get(d, 0) + 1

        avg_risk = (
            sum(e.get("risk_score", 0) for e in self.request_history) / total
        )

        return {
            "total_requests": total,
            "decision_distribution": decisions,
            "average_risk_score": avg_risk,
            "pending_approvals": sum(
                1
                for a in self.approvals.values()
                if a.status == ApprovalStatus.PENDING
            ),
            "open_circuits": len(self.circuit_opened_at),
        }


# Global router instance
_router: AdaptiveRiskRouter | None = None


def get_router(role_taxonomy=None) -> AdaptiveRiskRouter:
    """Get global router instance."""
    global _router
    if _router is None:
        _router = AdaptiveRiskRouter(role_taxonomy=role_taxonomy)
    return _router
