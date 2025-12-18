"""Layer 4: Static Reasoning Library - Rule-Based Logic Templates.

When the tiny LLM cannot logically reason about something, we use
symbolic logic templates instead.

This eliminates hallucinations for:
    - Conditional logic
    - Multi-step task plans
    - Fallback planning
    - Static schemas for task trees
    - Deterministic chain-of-thought templates
    - Tool sequencing logic

The LLM is never asked to "think" - the rules do the thinking.

Project Creator: Herman Swanepoel
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReasoningType(Enum):
    """Types of reasoning templates."""

    CONDITIONAL = "conditional"  # If-then-else logic
    SEQUENTIAL = "sequential"  # Step-by-step plans
    COMPARATIVE = "comparative"  # Compare options
    DIAGNOSTIC = "diagnostic"  # Root cause analysis
    DECISION_TREE = "decision_tree"  # Tree-based decisions
    CHAIN_OF_THOUGHT = "chain_of_thought"  # Structured thinking
    FALLBACK = "fallback"  # Error recovery plans


@dataclass
class ReasoningStep:
    """A single step in a reasoning chain."""

    id: str
    description: str
    action: str | None = None  # Tool to call
    condition: str | None = None  # When to execute
    output_key: str | None = None  # Where to store result


@dataclass
class ReasoningTemplate:
    """A template for structured reasoning."""

    id: str
    name: str
    type: ReasoningType
    description: str
    steps: list[ReasoningStep] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the reasoning template with given context."""
        result = {"steps": [], "conclusion": None, "confidence": 0.0}

        for step in self.steps:
            # Check condition
            if step.condition and not _evaluate_condition(
                step.condition, context
            ):
                continue

            # Record step execution
            step_result = {
                "id": step.id,
                "description": step.description,
                "action": step.action,
            }

            # If there's an action, it should be executed externally
            if step.action:
                step_result["requires_tool"] = step.action

            # Store output if specified
            if step.output_key:
                step_result["output_key"] = step.output_key

            result["steps"].append(step_result)

        result["confidence"] = 0.9 if result["steps"] else 0.5
        return result


class StaticReasoningLibrary:
    """Library of deterministic reasoning templates.

    This replaces LLM reasoning with rule-based logic.
    """

    def __init__(self) -> None:
        self._templates: dict[str, ReasoningTemplate] = {}
        self._decision_trees: dict[str, dict] = {}
        self._cot_templates: dict[str, list[str]] = {}
        self._register_builtin_templates()

    def _register_builtin_templates(self) -> None:
        """Register built-in reasoning templates."""

        # Diagnostic reasoning
        self._templates["diagnose_error"] = ReasoningTemplate(
            id="diagnose_error",
            name="Error Diagnosis",
            type=ReasoningType.DIAGNOSTIC,
            description="Diagnose system errors",
            steps=[
                ReasoningStep(
                    id="check_health",
                    description="First, check if the system is healthy",
                    action="check_health",
                    output_key="health_status",
                ),
                ReasoningStep(
                    id="check_logs",
                    description="Review recent error logs",
                    action="get_recent_logs",
                    condition="health_status.status != 'healthy'",
                    output_key="logs",
                ),
                ReasoningStep(
                    id="identify_pattern",
                    description="Look for error patterns in logs",
                    condition="logs exists",
                ),
                ReasoningStep(
                    id="suggest_fix",
                    description="Based on patterns, suggest a fix",
                    action="diagnose_issue",
                    output_key="diagnosis",
                ),
            ],
        )

        # Permission check reasoning
        self._templates["check_permission"] = ReasoningTemplate(
            id="check_permission",
            name="Permission Check",
            type=ReasoningType.CONDITIONAL,
            description="Check if an action is permitted",
            steps=[
                ReasoningStep(
                    id="identify_role",
                    description="Identify the current user's role",
                    action="list_roles",
                    output_key="roles",
                ),
                ReasoningStep(
                    id="check_capability",
                    description="Check if role has required capability",
                    action="check_permission",
                    output_key="permission",
                ),
                ReasoningStep(
                    id="evaluate_risk",
                    description="Evaluate risk of the action",
                    action="evaluate_risk",
                    condition="permission.permitted == true",
                    output_key="risk",
                ),
            ],
        )

        # Security audit reasoning
        self._templates["security_analysis"] = ReasoningTemplate(
            id="security_analysis",
            name="Security Analysis",
            type=ReasoningType.SEQUENTIAL,
            description="Analyze security posture",
            steps=[
                ReasoningStep(
                    id="get_audit",
                    description="Retrieve security audit logs",
                    action="get_security_audit",
                    output_key="audit_logs",
                ),
                ReasoningStep(
                    id="check_pii",
                    description="Check for PII exposure",
                    action="check_pii",
                    output_key="pii_status",
                ),
                ReasoningStep(
                    id="evaluate_risk",
                    description="Evaluate overall security risk",
                    action="evaluate_risk",
                    output_key="risk_assessment",
                ),
            ],
        )

        # Decision trees
        self._decision_trees["tool_selection"] = {
            "question": "What does the user want to do?",
            "branches": {
                "check_status": {
                    "keywords": ["status", "health", "check", "how is"],
                    "tool": "get_system_status",
                },
                "get_logs": {
                    "keywords": ["logs", "errors", "recent", "what happened"],
                    "tool": "get_recent_logs",
                },
                "debug": {
                    "keywords": [
                        "debug",
                        "fix",
                        "diagnose",
                        "problem",
                        "issue",
                    ],
                    "tool": "diagnose_issue",
                },
                "security": {
                    "keywords": ["security", "audit", "pii", "vulnerability"],
                    "tool": "get_security_audit",
                },
                "metrics": {
                    "keywords": [
                        "metrics",
                        "performance",
                        "latency",
                        "requests",
                    ],
                    "tool": "get_metrics",
                },
                "docs": {
                    "keywords": ["docs", "documentation", "help", "how to"],
                    "tool": "get_documentation",
                },
                "roles": {
                    "keywords": ["roles", "permissions", "access", "who can"],
                    "tool": "list_roles",
                },
                "config": {
                    "keywords": ["config", "settings", "configuration"],
                    "tool": "get_config",
                },
            },
        }

        # Chain-of-thought templates
        self._cot_templates["analyze_problem"] = [
            "1. First, let me understand what you're asking about: {problem}",
            "2. I'll check the relevant system status to gather information.",
            "3. Based on the data, I can identify potential causes.",
            "4. Here are my findings and recommendations:",
        ]

        self._cot_templates["execute_workflow"] = [
            "1. I'll execute this as a multi-step workflow.",
            "2. Step {current}/{total}: {step_name}",
            "3. Result: {step_result}",
            "4. Moving to next step...",
            "5. Workflow complete. Summary: {summary}",
        ]

        self._cot_templates["safety_check"] = [
            "1. Let me verify this operation is safe.",
            "2. Checking risk level: {risk_level}",
            "3. Checking permissions: {permission_status}",
            "4. Safety verdict: {verdict}",
        ]

    def get_template(self, template_id: str) -> ReasoningTemplate | None:
        """Get a reasoning template by ID."""
        return self._templates.get(template_id)

    def list_templates(self) -> list[str]:
        """List available template IDs."""
        return list(self._templates.keys())

    def traverse_decision_tree(
        self,
        tree_id: str,
        user_input: str,
    ) -> dict[str, Any]:
        """Traverse a decision tree to find the best action.

        Returns:
            {
                "tool": str | None,
                "confidence": float,
                "matched_branch": str | None,
                "reasoning": str,
            }
        """
        tree = self._decision_trees.get(tree_id)
        if not tree:
            return {
                "tool": None,
                "confidence": 0.0,
                "matched_branch": None,
                "reasoning": f"Decision tree '{tree_id}' not found",
            }

        input_lower = user_input.lower()
        best_match = None
        best_score = 0

        for branch_name, branch_config in tree.get("branches", {}).items():
            keywords = branch_config.get("keywords", [])
            score = sum(1 for kw in keywords if kw in input_lower)

            if score > best_score:
                best_score = score
                best_match = (branch_name, branch_config)

        if best_match:
            branch_name, branch_config = best_match
            confidence = min(best_score / 3.0, 1.0)  # Normalize score
            return {
                "tool": branch_config.get("tool"),
                "confidence": confidence,
                "matched_branch": branch_name,
                "reasoning": f"Matched '{branch_name}' with score {best_score}",
            }

        return {
            "tool": None,
            "confidence": 0.0,
            "matched_branch": None,
            "reasoning": "No matching branch found in decision tree",
        }

    def generate_chain_of_thought(
        self,
        template_id: str,
        variables: dict[str, Any],
    ) -> list[str]:
        """Generate a chain-of-thought response.

        This is deterministic - the LLM doesn't need to "think".
        """
        template = self._cot_templates.get(template_id, [])
        result = []

        for step in template:
            # Simple variable substitution
            formatted = step
            for key, value in variables.items():
                formatted = formatted.replace(f"{{{key}}}", str(value))
            result.append(formatted)

        return result

    def plan_task_sequence(
        self,
        task_type: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Plan a sequence of tasks based on type.

        This is fully deterministic - no LLM reasoning needed.
        """
        plans = {
            "diagnose": [
                {
                    "step": 1,
                    "action": "check_health",
                    "reason": "Verify system is reachable",
                },
                {
                    "step": 2,
                    "action": "get_system_status",
                    "reason": "Get detailed status",
                },
                {
                    "step": 3,
                    "action": "get_recent_logs",
                    "reason": "Check for errors",
                },
                {
                    "step": 4,
                    "action": "diagnose_issue",
                    "reason": "Analyze the problem",
                },
            ],
            "security_audit": [
                {
                    "step": 1,
                    "action": "get_security_audit",
                    "reason": "Review audit logs",
                },
                {
                    "step": 2,
                    "action": "check_pii",
                    "reason": "Check for data exposure",
                },
                {
                    "step": 3,
                    "action": "list_roles",
                    "reason": "Review access controls",
                },
                {
                    "step": 4,
                    "action": "evaluate_risk",
                    "reason": "Assess overall risk",
                },
            ],
            "performance_check": [
                {
                    "step": 1,
                    "action": "get_metrics",
                    "reason": "Get performance metrics",
                },
                {
                    "step": 2,
                    "action": "query_traces",
                    "reason": "Find slow requests",
                },
                {
                    "step": 3,
                    "action": "get_recent_logs",
                    "reason": "Check for errors",
                },
                {
                    "step": 4,
                    "action": "get_alerts",
                    "reason": "Check active alerts",
                },
            ],
            "generate_content": [
                {
                    "step": 1,
                    "action": "evaluate_risk",
                    "reason": "Assess generation risk",
                },
                {
                    "step": 2,
                    "action": "check_pii",
                    "reason": "Check for PII in input",
                },
                {
                    "step": 3,
                    "action": "audit_log",
                    "reason": "Log the generation request",
                },
            ],
            "query_data": [
                {
                    "step": 1,
                    "action": "semantic_search",
                    "reason": "Search knowledge base",
                },
                {
                    "step": 2,
                    "action": "get_documentation",
                    "reason": "Get relevant docs",
                },
            ],
        }

        return plans.get(
            task_type,
            [
                {
                    "step": 1,
                    "action": "get_system_status",
                    "reason": "Start with status check",
                },
            ],
        )

    def get_fallback_plan(
        self,
        failed_action: str,
        error: str,
    ) -> list[dict[str, Any]]:
        """Get a fallback plan when an action fails.

        This is deterministic error recovery.
        """
        # Connection errors
        if "connection" in error.lower() or "unreachable" in error.lower():
            return [
                {
                    "action": "check_health",
                    "reason": "Verify backend is running",
                },
                {"action": "get_config", "reason": "Check configuration"},
                {
                    "suggestion": "The backend service may be down. Try restarting it."
                },
            ]

        # Permission errors
        if "permission" in error.lower() or "denied" in error.lower():
            return [
                {"action": "list_roles", "reason": "Check available roles"},
                {"action": "check_permission", "reason": "Verify permissions"},
                {
                    "suggestion": "You may need elevated permissions for this action."
                },
            ]

        # Not found errors
        if "not found" in error.lower():
            return [
                {
                    "action": "list_available_tools",
                    "reason": "Check available tools",
                },
                {
                    "action": "get_documentation",
                    "reason": "Review documentation",
                },
                {"suggestion": "The requested resource may not exist."},
            ]

        # Generic fallback
        return [
            {"action": "diagnose_issue", "reason": "Analyze the failure"},
            {
                "action": "get_recent_logs",
                "reason": "Check for related errors",
            },
        ]

    def evaluate_conditional(
        self,
        condition_type: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate a conditional logic pattern.

        Returns deterministic result based on rules.
        """
        if condition_type == "risk_threshold":
            risk_score = parameters.get("risk_score", 0)
            thresholds = {
                "low": 0.3,
                "medium": 0.6,
                "high": 0.8,
            }

            if risk_score >= thresholds["high"]:
                return {
                    "decision": "deny",
                    "reason": "Risk score too high",
                    "requires_approval": True,
                }
            elif risk_score >= thresholds["medium"]:
                return {
                    "decision": "caution",
                    "reason": "Medium risk - proceed with care",
                    "requires_approval": False,
                }
            else:
                return {
                    "decision": "allow",
                    "reason": "Low risk operation",
                    "requires_approval": False,
                }

        elif condition_type == "permission_check":
            role = parameters.get("role", "")
            action = parameters.get("action", "")

            # Simple role hierarchy
            admin_roles = ["admin", "administrator", "root"]
            write_roles = admin_roles + [
                "developer",
                "operator",
                "lead engineer",
            ]
            read_roles = write_roles + ["observer", "viewer", "analyst"]

            if "delete" in action or "admin" in action:
                return {"permitted": role.lower() in admin_roles}
            elif "write" in action or "modify" in action:
                return {"permitted": role.lower() in write_roles}
            else:
                return {"permitted": role.lower() in read_roles}

        elif condition_type == "workflow_selection":
            intent = parameters.get("intent", "")

            if "debug" in intent or "diagnose" in intent:
                return {
                    "workflow": "debug",
                    "reason": "Debugging task detected",
                }
            elif "security" in intent or "audit" in intent:
                return {
                    "workflow": "security_audit",
                    "reason": "Security task detected",
                }
            elif "check" in intent or "status" in intent:
                return {
                    "workflow": "system_check",
                    "reason": "Status check detected",
                }
            else:
                return {
                    "workflow": None,
                    "reason": "No specific workflow needed",
                }

        return {"result": "unknown", "reason": "Unrecognized condition type"}


def _evaluate_condition(condition: str, context: dict) -> bool:
    """Evaluate a simple condition string."""
    condition = condition.strip()

    if condition.lower() in ("true", "yes"):
        return True
    if condition.lower() in ("false", "no"):
        return False

    # Handle "var exists" pattern
    if condition.endswith(" exists"):
        var_name = condition[:-7].strip()
        return var_name in context

    # Handle "var.field == value" pattern
    if "==" in condition:
        parts = condition.split("==")
        if len(parts) == 2:
            left = parts[0].strip()
            right = parts[1].strip().strip("'\"")

            # Navigate nested fields
            value = context
            for field in left.split("."):
                if isinstance(value, dict):
                    value = value.get(field)
                else:
                    value = None
                    break

            return str(value) == right

    # Handle "var.field != value" pattern
    if "!=" in condition:
        parts = condition.split("!=")
        if len(parts) == 2:
            left = parts[0].strip()
            right = parts[1].strip().strip("'\"")

            value = context
            for field in left.split("."):
                if isinstance(value, dict):
                    value = value.get(field)
                else:
                    value = None
                    break

            return str(value) != right

    return True


# Singleton instance
_library: StaticReasoningLibrary | None = None


def get_reasoning_library() -> StaticReasoningLibrary:
    """Get singleton reasoning library."""
    global _library
    if _library is None:
        _library = StaticReasoningLibrary()
    return _library
