"""
DAG Orchestration Engine - Multi-Agent Workflow Management.

This module implements a Directed Acyclic Graph (DAG) based orchestration
system for coordinating multiple agents in complex workflows.

Features:
- DAG-based workflow definition
- Parallel and sequential task execution
- Dependency management
- Error handling and retry logic
- Progress tracking and visualization
- Audit trail for compliance
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a workflow task."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Priority levels for tasks."""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class TaskResult:
    """Result from a task execution."""

    task_id: str
    status: TaskStatus
    output: Any = None
    error: str | None = None
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_ms: float = 0.0
    retries: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
            "metadata": self.metadata,
        }


@dataclass
class Task:
    """A task node in the workflow DAG."""

    id: str
    name: str
    agent_role: str
    handler: Callable[..., Coroutine[Any, Any, Any]] | None = None
    dependencies: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: float = 300.0
    max_retries: int = 3
    retry_delay_seconds: float = 5.0
    skip_on_upstream_failure: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    # Runtime state
    status: TaskStatus = TaskStatus.PENDING
    result: TaskResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "agent_role": self.agent_role,
            "dependencies": self.dependencies,
            "inputs": self.inputs,
            "priority": self.priority.value,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "status": self.status.value,
            "result": self.result.to_dict() if self.result else None,
            "metadata": self.metadata,
        }


@dataclass
class WorkflowResult:
    """Result of a complete workflow execution."""

    workflow_id: str
    name: str
    status: TaskStatus
    tasks: dict[str, TaskResult]
    started_at: float
    completed_at: float
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)
    audit_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "status": self.status.value,
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "audit_hash": self.audit_hash,
        }


class DAGValidationError(Exception):
    """Raised when DAG validation fails."""

    pass


class WorkflowExecutionError(Exception):
    """Raised when workflow execution fails."""

    pass


class DAGOrchestrator:
    """
    Orchestrates multi-agent workflows using DAG-based task graphs.

    Provides:
    - Workflow definition and validation
    - Parallel task execution with dependency resolution
    - Error handling, retries, and circuit breaking
    - Progress tracking and callbacks
    - Audit logging for compliance
    """

    def __init__(
        self,
        max_concurrent_tasks: int = 10,
        audit_log_path: str | None = None,
    ):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.audit_enabled = os.environ.get("DAG_AUDIT_LOG", "1") in (
            "1",
            "true",
        )
        self.audit_path = audit_log_path or os.environ.get(
            "DAG_AUDIT_PATH", "logs/dag_audit.jsonl"
        )

        # Runtime state
        self.tasks: dict[str, Task] = {}
        self.workflows: dict[str, dict[str, Any]] = {}
        self.running_tasks: set[str] = set()
        self.semaphore: asyncio.Semaphore | None = None

        # Progress callbacks
        self.on_task_start: Callable[[Task], None] | None = None
        self.on_task_complete: Callable[[Task, TaskResult], None] | None = None
        self.on_workflow_complete: Callable[[WorkflowResult], None] | None = (
            None
        )

    def _generate_workflow_id(self, name: str) -> str:
        """Generate unique workflow ID."""
        timestamp = str(time.time())
        content = f"{name}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _compute_audit_hash(self, results: dict[str, TaskResult]) -> str:
        """Compute hash for audit integrity."""
        content = json.dumps(
            {k: v.to_dict() for k, v in results.items()}, sort_keys=True
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def _log_audit(self, result: WorkflowResult) -> None:
        """Log workflow result for audit."""
        if not self.audit_enabled:
            return

        try:
            Path(self.audit_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.audit_path, "a") as f:
                f.write(json.dumps(result.to_dict()) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")

    def add_task(self, task: Task) -> "DAGOrchestrator":
        """Add a task to the orchestrator."""
        self.tasks[task.id] = task
        return self

    def create_task(
        self,
        id: str,
        name: str,
        agent_role: str,
        handler: Callable[..., Coroutine[Any, Any, Any]],
        dependencies: list[str] | None = None,
        inputs: dict[str, Any] | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_seconds: float = 300.0,
        max_retries: int = 3,
    ) -> Task:
        """Create and add a new task."""
        task = Task(
            id=id,
            name=name,
            agent_role=agent_role,
            handler=handler,
            dependencies=dependencies or [],
            inputs=inputs or {},
            priority=priority,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.add_task(task)
        return task

    def validate_dag(self) -> bool:
        """
        Validate the DAG structure.

        Checks:
        - All dependencies exist
        - No circular dependencies
        - All tasks have handlers

        Raises:
            DAGValidationError: If validation fails
        """
        # Check dependencies exist
        for task_id, task in self.tasks.items():
            for dep_id in task.dependencies:
                if dep_id not in self.tasks:
                    raise DAGValidationError(
                        f"Task '{task_id}' depends on unknown task '{dep_id}'"
                    )

        # Check for cycles using DFS
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            task = self.tasks[task_id]
            for dep_id in task.dependencies:
                if dep_id not in visited:
                    if has_cycle(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(task_id)
            return False

        for task_id in self.tasks:
            if task_id not in visited:
                if has_cycle(task_id):
                    raise DAGValidationError(
                        "Circular dependency detected in workflow"
                    )

        # Check handlers
        for task_id, task in self.tasks.items():
            if task.handler is None:
                raise DAGValidationError(f"Task '{task_id}' has no handler")

        logger.info(f"DAG validated: {len(self.tasks)} tasks")
        return True

    def get_ready_tasks(
        self, completed: set[str], failed: set[str]
    ) -> list[Task]:
        """Get tasks that are ready to run (all dependencies satisfied)."""
        ready = []

        for task_id, task in self.tasks.items():
            # Skip if already processed
            if (
                task_id in completed
                or task_id in failed
                or task_id in self.running_tasks
            ):
                continue

            # Check if all dependencies are satisfied
            deps_satisfied = all(
                dep_id in completed for dep_id in task.dependencies
            )

            # Check if any dependency failed
            deps_failed = any(dep_id in failed for dep_id in task.dependencies)

            if deps_failed:
                if task.skip_on_upstream_failure:
                    task.status = TaskStatus.SKIPPED
                    task.result = TaskResult(
                        task_id=task_id,
                        status=TaskStatus.SKIPPED,
                        error="Upstream dependency failed",
                    )
                    failed.add(task_id)
                else:
                    # Mark as failed due to upstream
                    task.status = TaskStatus.FAILED
                    task.result = TaskResult(
                        task_id=task_id,
                        status=TaskStatus.FAILED,
                        error="Upstream dependency failed",
                    )
                    failed.add(task_id)
            elif deps_satisfied:
                ready.append(task)

        # Sort by priority (highest first)
        ready.sort(key=lambda t: t.priority.value, reverse=True)
        return ready

    async def _execute_task(
        self,
        task: Task,
        context: dict[str, Any],
    ) -> TaskResult:
        """Execute a single task with retries and timeout."""
        started_at = time.time()
        retries = 0
        last_error = None

        # Resolve inputs from upstream outputs
        resolved_inputs = task.inputs.copy()
        for dep_id in task.dependencies:
            dep_task = self.tasks[dep_id]
            if dep_task.result and dep_task.result.output:
                resolved_inputs[f"upstream_{dep_id}"] = dep_task.result.output

        while retries <= task.max_retries:
            try:
                task.status = TaskStatus.RUNNING
                self.running_tasks.add(task.id)

                if self.on_task_start:
                    self.on_task_start(task)

                # Execute with timeout
                if task.handler:
                    async with asyncio.timeout(task.timeout_seconds):
                        output = await task.handler(
                            inputs=resolved_inputs,
                            context=context,
                            task=task,
                        )
                else:
                    output = None

                completed_at = time.time()

                result = TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output=output,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=(completed_at - started_at) * 1000,
                    retries=retries,
                )

                task.status = TaskStatus.COMPLETED
                task.result = result

                if self.on_task_complete:
                    self.on_task_complete(task, result)

                return result

            except TimeoutError:
                last_error = f"Task timed out after {task.timeout_seconds}s"
                retries += 1
                logger.warning(
                    f"Task {task.id} timeout (retry {retries}/{task.max_retries})"
                )

            except Exception as e:
                last_error = str(e)
                retries += 1
                logger.warning(
                    f"Task {task.id} failed: {e} (retry {retries}/{task.max_retries})"
                )

            finally:
                self.running_tasks.discard(task.id)

            if retries <= task.max_retries:
                await asyncio.sleep(task.retry_delay_seconds)

        # All retries exhausted
        completed_at = time.time()
        result = TaskResult(
            task_id=task.id,
            status=TaskStatus.FAILED,
            error=last_error,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=(completed_at - started_at) * 1000,
            retries=retries - 1,
        )

        task.status = TaskStatus.FAILED
        task.result = result

        if self.on_task_complete:
            self.on_task_complete(task, result)

        return result

    async def execute(
        self,
        name: str = "workflow",
        context: dict[str, Any] | None = None,
        fail_fast: bool = False,
    ) -> WorkflowResult:
        """
        Execute the workflow DAG.

        Args:
            name: Workflow name for tracking
            context: Shared context passed to all tasks
            fail_fast: Stop on first failure

        Returns:
            WorkflowResult with all task results
        """
        # Validate DAG first
        self.validate_dag()

        workflow_id = self._generate_workflow_id(name)
        started_at = time.time()
        context = context or {}

        logger.info(f"Starting workflow {workflow_id}: {name}")

        # Initialize semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        # Track completion
        completed: set[str] = set()
        failed: set[str] = set()
        results: dict[str, TaskResult] = {}

        # Reset task states
        for task in self.tasks.values():
            task.status = TaskStatus.PENDING
            task.result = None

        async def run_task_with_semaphore(task: Task) -> TaskResult:
            async with self.semaphore:
                return await self._execute_task(task, context)

        # Process tasks until all complete
        while len(completed) + len(failed) < len(self.tasks):
            # Get ready tasks
            ready = self.get_ready_tasks(completed, failed)

            if not ready:
                # No tasks ready - might be deadlock or all complete
                remaining = len(self.tasks) - len(completed) - len(failed)
                if remaining > 0:
                    logger.error(
                        f"Workflow stuck: {remaining} tasks cannot proceed"
                    )
                    break
                break

            # Execute ready tasks in parallel
            tasks_to_run = [run_task_with_semaphore(task) for task in ready]

            if fail_fast:
                # Run one at a time to catch failures early
                for task, coro in zip(ready, tasks_to_run, strict=False):
                    result = await coro
                    results[task.id] = result

                    if result.status == TaskStatus.COMPLETED:
                        completed.add(task.id)
                    else:
                        failed.add(task.id)
                        if fail_fast:
                            logger.info(
                                f"Workflow {workflow_id} stopping due to fail_fast"
                            )
                            # Cancel remaining
                            for t in self.tasks.values():
                                if t.status == TaskStatus.PENDING:
                                    t.status = TaskStatus.CANCELLED
                                    results[t.id] = TaskResult(
                                        task_id=t.id,
                                        status=TaskStatus.CANCELLED,
                                        error="Cancelled due to upstream failure",
                                    )
                            break
            else:
                # Run all ready tasks in parallel
                task_results = await asyncio.gather(
                    *tasks_to_run, return_exceptions=True
                )

                for task, result in zip(ready, task_results, strict=False):
                    if isinstance(result, Exception):
                        result = TaskResult(
                            task_id=task.id,
                            status=TaskStatus.FAILED,
                            error=str(result),
                        )
                        task.status = TaskStatus.FAILED
                        task.result = result

                    results[task.id] = result

                    if result.status == TaskStatus.COMPLETED:
                        completed.add(task.id)
                    else:
                        failed.add(task.id)

            if fail_fast and failed:
                break

        # Determine overall status
        completed_at = time.time()

        if len(failed) == 0:
            status = TaskStatus.COMPLETED
        elif len(completed) > 0:
            status = TaskStatus.COMPLETED  # Partial success
        else:
            status = TaskStatus.FAILED

        # Build result
        workflow_result = WorkflowResult(
            workflow_id=workflow_id,
            name=name,
            status=status,
            tasks=results,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=(completed_at - started_at) * 1000,
            metadata={
                "total_tasks": len(self.tasks),
                "completed": len(completed),
                "failed": len(failed),
            },
            audit_hash=self._compute_audit_hash(results),
        )

        # Log audit
        self._log_audit(workflow_result)

        if self.on_workflow_complete:
            self.on_workflow_complete(workflow_result)

        logger.info(
            f"Workflow {workflow_id} complete: {len(completed)}/{len(self.tasks)} tasks, "
            f"duration={workflow_result.duration_ms:.0f}ms"
        )

        return workflow_result

    def visualize_dag(self) -> str:
        """Generate Mermaid diagram of the DAG."""
        lines = ["graph TD"]

        for task_id, task in self.tasks.items():
            # Node with status color
            status_colors = {
                TaskStatus.PENDING: "fill:#gray",
                TaskStatus.RUNNING: "fill:#yellow",
                TaskStatus.COMPLETED: "fill:#green",
                TaskStatus.FAILED: "fill:#red",
                TaskStatus.SKIPPED: "fill:#orange",
            }
            color = status_colors.get(task.status, "fill:#gray")

            # Add node
            lines.append(f"    {task_id}[{task.name}]")
            lines.append(f"    style {task_id} {color}")

            # Add edges for dependencies
            for dep_id in task.dependencies:
                lines.append(f"    {dep_id} --> {task_id}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all tasks from the orchestrator."""
        self.tasks.clear()
        self.running_tasks.clear()
        logger.info("DAG cleared")


# Workflow builder helper
class WorkflowBuilder:
    """Fluent builder for creating workflows."""

    def __init__(self, name: str = "workflow"):
        self.name = name
        self.orchestrator = DAGOrchestrator()
        self._task_counter = 0

    def add_task(
        self,
        name: str,
        handler: Callable[..., Coroutine[Any, Any, Any]],
        agent_role: str = "Worker",
        depends_on: list[str] | None = None,
        inputs: dict[str, Any] | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        """Add a task and return its ID."""
        self._task_counter += 1
        task_id = f"task_{self._task_counter:03d}"

        self.orchestrator.create_task(
            id=task_id,
            name=name,
            agent_role=agent_role,
            handler=handler,
            dependencies=depends_on or [],
            inputs=inputs or {},
            priority=priority,
        )

        return task_id

    def add_parallel_tasks(
        self,
        tasks: list[tuple[str, Callable[..., Coroutine[Any, Any, Any]]]],
        depends_on: list[str] | None = None,
    ) -> list[str]:
        """Add multiple tasks that run in parallel."""
        task_ids = []
        for name, handler in tasks:
            task_id = self.add_task(
                name=name,
                handler=handler,
                depends_on=depends_on,
            )
            task_ids.append(task_id)
        return task_ids

    async def run(
        self,
        context: dict[str, Any] | None = None,
        fail_fast: bool = False,
    ) -> WorkflowResult:
        """Execute the workflow."""
        return await self.orchestrator.execute(
            name=self.name,
            context=context,
            fail_fast=fail_fast,
        )

    def visualize(self) -> str:
        """Get Mermaid diagram of the workflow."""
        return self.orchestrator.visualize_dag()
