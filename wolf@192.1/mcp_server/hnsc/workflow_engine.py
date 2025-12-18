"""Layer 3: Workflow Engine - Deterministic Multi-Step Pipelines.

The Workflow Engine manages multi-step operations as pre-defined DAGs.
This eliminates the need for the LLM to reason about task ordering.

Key workflows:
    - edit → lint → test
    - search → modify → validate
    - read → extract → write
    - generate → check → refine
    - diagnose → analyze → fix → verify

All workflows are deterministic and pre-defined.

Project Creator: Herman Swanepoel
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkflowStatus(Enum):
    """Status of a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Status of a workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """A single step in a workflow."""

    id: str
    name: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)  # Step IDs
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None

    # Conditional execution
    condition: str | None = None  # Expression to evaluate
    skip_on_failure: bool = False  # Skip if dependencies failed

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "tool": self.tool_name,
            "arguments": self.arguments,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "duration_ms": (
                int((self.completed_at - self.started_at) * 1000)
                if self.started_at and self.completed_at
                else None
            ),
        }


@dataclass
class Workflow:
    """A complete workflow definition."""

    id: str
    name: str
    description: str
    steps: list[WorkflowStep] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    context: dict[str, Any] = field(
        default_factory=dict
    )  # Shared data between steps

    def get_next_steps(self) -> list[WorkflowStep]:
        """Get steps that are ready to execute."""
        ready = []
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue

            # Check all dependencies are completed
            deps_ok = True
            for dep_id in step.dependencies:
                dep_step = self.get_step(dep_id)
                if not dep_step or dep_step.status != StepStatus.COMPLETED:
                    deps_ok = False
                    break

            if deps_ok:
                ready.append(step)

        return ready

    def get_step(self, step_id: str) -> WorkflowStep | None:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def is_complete(self) -> bool:
        """Check if all steps are done."""
        return all(
            s.status
            in (StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.FAILED)
            for s in self.steps
        )

    def has_failures(self) -> bool:
        """Check if any steps failed."""
        return any(s.status == StepStatus.FAILED for s in self.steps)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "context_keys": list(self.context.keys()),
        }

    def to_mermaid(self) -> str:
        """Generate Mermaid diagram for the workflow."""
        lines = ["graph TD"]

        for step in self.steps:
            # Node with status color
            status_class = {
                StepStatus.PENDING: "",
                StepStatus.RUNNING: ":::running",
                StepStatus.COMPLETED: ":::completed",
                StepStatus.FAILED: ":::failed",
                StepStatus.SKIPPED: ":::skipped",
            }.get(step.status, "")

            lines.append(f"    {step.id}[{step.name}]{status_class}")

            # Edges from dependencies
            for dep_id in step.dependencies:
                lines.append(f"    {dep_id} --> {step.id}")

        # Style definitions
        lines.extend(
            [
                "",
                "    classDef running fill:#ffd700,stroke:#333",
                "    classDef completed fill:#90ee90,stroke:#333",
                "    classDef failed fill:#ff6b6b,stroke:#333",
                "    classDef skipped fill:#d3d3d3,stroke:#333",
            ]
        )

        return "\n".join(lines)


class WorkflowEngine:
    """Engine for executing pre-defined workflows.

    This eliminates LLM reasoning about task ordering.
    """

    def __init__(self) -> None:
        self._workflows: dict[str, Workflow] = {}
        self._templates: dict[str, Callable[..., Workflow]] = {}
        self._tool_executor: Callable | None = None
        self._register_builtin_templates()

    def set_tool_executor(self, executor: Callable) -> None:
        """Set the function used to execute tools."""
        self._tool_executor = executor

    def _register_builtin_templates(self) -> None:
        """Register built-in workflow templates."""

        # Diagnostic workflow
        self._templates["diagnose"] = self._create_diagnose_workflow

        # Full system check
        self._templates["system_check"] = self._create_system_check_workflow

        # Security audit
        self._templates["security_audit"] = (
            self._create_security_audit_workflow
        )

        # Debug workflow
        self._templates["debug"] = self._create_debug_workflow

        # Generate and validate
        self._templates["generate_validate"] = (
            self._create_generate_validate_workflow
        )

        # Analysis pipeline
        self._templates["analyze"] = self._create_analyze_workflow

    def _create_diagnose_workflow(
        self,
        symptom: str = "",
        **kwargs,
    ) -> Workflow:
        """Create a diagnostic workflow."""
        workflow_id = f"diag_{int(time.time())}"

        return Workflow(
            id=workflow_id,
            name="Diagnostic Workflow",
            description=f"Diagnose issue: {symptom[:50]}...",
            steps=[
                WorkflowStep(
                    id="health",
                    name="Check Health",
                    tool_name="check_health",
                ),
                WorkflowStep(
                    id="status",
                    name="Get System Status",
                    tool_name="get_system_status",
                    dependencies=["health"],
                ),
                WorkflowStep(
                    id="logs",
                    name="Get Recent Logs",
                    tool_name="get_recent_logs",
                    arguments={"service": "all", "lines": 20},
                    dependencies=["health"],
                ),
                WorkflowStep(
                    id="diagnose",
                    name="Diagnose Issue",
                    tool_name="diagnose_issue",
                    arguments={"symptom": symptom},
                    dependencies=["status", "logs"],
                ),
            ],
            context={"symptom": symptom},
        )

    def _create_system_check_workflow(self, **kwargs) -> Workflow:
        """Create a full system check workflow."""
        workflow_id = f"check_{int(time.time())}"

        return Workflow(
            id=workflow_id,
            name="System Check",
            description="Comprehensive system health check",
            steps=[
                WorkflowStep(
                    id="health",
                    name="Backend Health",
                    tool_name="check_health",
                ),
                WorkflowStep(
                    id="models",
                    name="ML Model Status",
                    tool_name="get_model_status",
                ),
                WorkflowStep(
                    id="metrics",
                    name="Get Metrics",
                    tool_name="get_metrics",
                    arguments={"service": "all"},
                ),
                WorkflowStep(
                    id="alerts",
                    name="Check Alerts",
                    tool_name="get_alerts",
                ),
                WorkflowStep(
                    id="status",
                    name="System Status",
                    tool_name="get_system_status",
                    dependencies=["health", "models", "metrics", "alerts"],
                ),
            ],
        )

    def _create_security_audit_workflow(self, **kwargs) -> Workflow:
        """Create a security audit workflow."""
        workflow_id = f"sec_{int(time.time())}"

        return Workflow(
            id=workflow_id,
            name="Security Audit",
            description="Comprehensive security audit",
            steps=[
                WorkflowStep(
                    id="audit_logs",
                    name="Get Security Audit Logs",
                    tool_name="get_security_audit",
                    arguments={"limit": 50},
                ),
                WorkflowStep(
                    id="roles",
                    name="List Roles",
                    tool_name="list_roles",
                ),
                WorkflowStep(
                    id="config",
                    name="Get Config",
                    tool_name="get_config",
                    arguments={"section": "all"},
                ),
                WorkflowStep(
                    id="risk",
                    name="Evaluate Risk",
                    tool_name="evaluate_risk",
                    arguments={"operation": "security_audit"},
                    dependencies=["audit_logs", "roles", "config"],
                ),
            ],
        )

    def _create_debug_workflow(
        self,
        symptom: str = "",
        **kwargs,
    ) -> Workflow:
        """Create a debug workflow."""
        workflow_id = f"debug_{int(time.time())}"

        return Workflow(
            id=workflow_id,
            name="Debug Workflow",
            description=f"Debug: {symptom[:50]}...",
            steps=[
                WorkflowStep(
                    id="health",
                    name="Check Health",
                    tool_name="check_health",
                ),
                WorkflowStep(
                    id="logs",
                    name="Get Logs",
                    tool_name="get_recent_logs",
                    arguments={"service": "all", "lines": 50},
                ),
                WorkflowStep(
                    id="traces",
                    name="Query Traces",
                    tool_name="query_traces",
                    arguments={"duration_ms_min": 1000},  # Slow queries
                    dependencies=["health"],
                ),
                WorkflowStep(
                    id="metrics",
                    name="Get Metrics",
                    tool_name="get_metrics",
                    dependencies=["health"],
                ),
                WorkflowStep(
                    id="diagnose",
                    name="Diagnose",
                    tool_name="diagnose_issue",
                    arguments={"symptom": symptom},
                    dependencies=["logs", "traces", "metrics"],
                ),
            ],
            context={"symptom": symptom},
        )

    def _create_generate_validate_workflow(
        self,
        content: str = "",
        **kwargs,
    ) -> Workflow:
        """Create a generate-and-validate workflow."""
        workflow_id = f"gen_{int(time.time())}"

        return Workflow(
            id=workflow_id,
            name="Generate & Validate",
            description="Generate content and validate it",
            steps=[
                WorkflowStep(
                    id="risk",
                    name="Evaluate Risk",
                    tool_name="evaluate_risk",
                    arguments={"operation": "generate_content"},
                ),
                WorkflowStep(
                    id="pii",
                    name="Check PII",
                    tool_name="check_pii",
                    arguments={"text": content},
                    dependencies=["risk"],
                ),
                WorkflowStep(
                    id="audit",
                    name="Audit Log",
                    tool_name="audit_log",
                    arguments={"action": "content_generated"},
                    dependencies=["pii"],
                ),
            ],
            context={"content": content},
        )

    def _create_analyze_workflow(
        self,
        query: str = "",
        **kwargs,
    ) -> Workflow:
        """Create an analysis workflow."""
        workflow_id = f"analyze_{int(time.time())}"

        return Workflow(
            id=workflow_id,
            name="Analysis Pipeline",
            description=f"Analyze: {query[:50]}...",
            steps=[
                WorkflowStep(
                    id="search",
                    name="Semantic Search",
                    tool_name="semantic_search",
                    arguments={"query": query},
                ),
                WorkflowStep(
                    id="docs",
                    name="Get Documentation",
                    tool_name="get_documentation",
                ),
                WorkflowStep(
                    id="project",
                    name="Project Status",
                    tool_name="get_project_status",
                ),
            ],
            context={"query": query},
        )

    def create_workflow(
        self,
        template_name: str,
        **kwargs,
    ) -> Workflow | None:
        """Create a workflow from a template."""
        if template_name not in self._templates:
            return None

        workflow = self._templates[template_name](**kwargs)
        self._workflows[workflow.id] = workflow
        return workflow

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        """Get a workflow by ID."""
        return self._workflows.get(workflow_id)

    def list_templates(self) -> list[str]:
        """List available workflow templates."""
        return list(self._templates.keys())

    async def execute_workflow(
        self,
        workflow: Workflow,
        max_concurrent: int = 3,
    ) -> Workflow:
        """Execute a workflow.

        Steps are executed in parallel where dependencies allow.
        """
        if not self._tool_executor:
            raise RuntimeError("Tool executor not set")

        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = time.time()

        try:
            while not workflow.is_complete():
                # Get steps ready to execute
                ready_steps = workflow.get_next_steps()

                if not ready_steps:
                    # No steps ready - might be stuck
                    if any(
                        s.status == StepStatus.PENDING for s in workflow.steps
                    ):
                        # There are pending steps but none are ready - dependency issue
                        workflow.status = WorkflowStatus.FAILED
                        break
                    continue

                # Execute ready steps in parallel (up to max_concurrent)
                batch = ready_steps[:max_concurrent]
                tasks = [self._execute_step(workflow, step) for step in batch]
                await asyncio.gather(*tasks)

            # Determine final status
            if workflow.has_failures():
                workflow.status = WorkflowStatus.FAILED
            else:
                workflow.status = WorkflowStatus.COMPLETED

        except Exception:
            workflow.status = WorkflowStatus.FAILED

        finally:
            workflow.completed_at = time.time()

        return workflow

    async def _execute_step(
        self,
        workflow: Workflow,
        step: WorkflowStep,
    ) -> None:
        """Execute a single workflow step."""
        step.status = StepStatus.RUNNING
        step.started_at = time.time()

        try:
            # Check condition if present
            if step.condition and not self._evaluate_condition(
                step.condition, workflow.context
            ):
                step.status = StepStatus.SKIPPED
                step.completed_at = time.time()
                return

            # Merge workflow context into arguments
            args = {**step.arguments}
            for key, value in workflow.context.items():
                if f"${key}" in str(args):
                    # Simple template replacement
                    for arg_key, arg_val in args.items():
                        if isinstance(arg_val, str):
                            args[arg_key] = arg_val.replace(
                                f"${key}", str(value)
                            )

            # Execute the tool
            result = await self._tool_executor(step.tool_name, args)

            step.result = result
            step.status = StepStatus.COMPLETED

            # Store result in workflow context
            workflow.context[f"step_{step.id}_result"] = result

        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)

        finally:
            step.completed_at = time.time()

    def _evaluate_condition(self, condition: str, context: dict) -> bool:
        """Evaluate a simple condition expression.

        Supported:
        - $var == "value"
        - $var != "value"
        - $var exists
        - true / false
        """
        condition = condition.strip()

        if condition.lower() == "true":
            return True
        if condition.lower() == "false":
            return False

        # Variable exists check
        if condition.endswith(" exists"):
            var_name = condition[:-7].strip().lstrip("$")
            return var_name in context

        # Equality check
        if "==" in condition:
            parts = condition.split("==")
            if len(parts) == 2:
                var_name = parts[0].strip().lstrip("$")
                expected = parts[1].strip().strip("\"'")
                return str(context.get(var_name, "")) == expected

        # Inequality check
        if "!=" in condition:
            parts = condition.split("!=")
            if len(parts) == 2:
                var_name = parts[0].strip().lstrip("$")
                expected = parts[1].strip().strip("\"'")
                return str(context.get(var_name, "")) != expected

        return True  # Default: condition met

    def detect_workflow(
        self, intent_category: str, user_input: str
    ) -> str | None:
        """Detect which workflow template matches the user's intent.

        Returns template name or None.
        """
        input_lower = user_input.lower()

        # Debug/diagnose -> debug workflow
        if any(
            word in input_lower
            for word in ["debug", "diagnose", "troubleshoot", "fix"]
        ):
            return "debug"

        # Security/audit -> security_audit workflow
        if any(
            word in input_lower
            for word in ["security", "audit", "vulnerability"]
        ):
            return "security_audit"

        # Full check/status -> system_check workflow
        if any(
            word in input_lower
            for word in ["full check", "system check", "comprehensive"]
        ):
            return "system_check"

        # Analyze/research -> analyze workflow
        if any(
            word in input_lower
            for word in ["analyze", "research", "investigate", "look into"]
        ):
            return "analyze"

        # Generate/create with validation
        if any(word in input_lower for word in ["generate", "create"]) and any(
            word in input_lower for word in ["validate", "check", "verify"]
        ):
            return "generate_validate"

        return None

    def list_workflows(self) -> list[dict]:
        """List all available workflow templates.

        Returns a list of workflow info dictionaries for HNSC Controller.
        """
        result = []
        for name in self._templates.keys():
            result.append(
                {
                    "id": name,
                    "description": f"Workflow template: {name}",
                    "available": True,
                }
            )
        # Also add any running/completed workflows
        for wf_id, wf in self._workflows.items():
            result.append(
                {
                    "id": wf_id,
                    "description": wf.description,
                    "status": (
                        wf.status.value
                        if hasattr(wf.status, "value")
                        else str(wf.status)
                    ),
                    "steps": len(wf.steps),
                }
            )
        return result

    def match_workflow(
        self,
        intent: str,
        tool_name: str | None = None,
        context: dict | None = None,
    ) -> dict | None:
        """Match user intent to a workflow.

        Used by HNSC Controller to find multi-step pipelines.

        Args:
            intent: The classified intent category (e.g., "debug", "security")
            tool_name: Optional tool name that triggered routing
            context: Additional context for matching

        Returns:
            Workflow dict with id, steps, etc., or None if no match.
        """
        context = context or {}

        # Use detect_workflow with dummy user input based on intent
        user_hint = context.get("user_input", intent)
        template_name = self.detect_workflow(intent, user_hint)

        if not template_name:
            return None

        # Try to create workflow from template
        try:
            workflow = self.create_from_template(template_name, **context)
            if workflow:
                return {
                    "id": workflow.id,
                    "template": template_name,
                    "description": workflow.description,
                    "steps": [
                        {
                            "tool": step.tool_name,
                            "parameters": step.arguments,
                            "condition": step.condition,
                        }
                        for step in workflow.steps
                    ],
                }
        except Exception:
            pass

        return None


# Singleton instance
_engine: WorkflowEngine | None = None


def get_workflow_engine() -> WorkflowEngine:
    """Get singleton workflow engine."""
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine
