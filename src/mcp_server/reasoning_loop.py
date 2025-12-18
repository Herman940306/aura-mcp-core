"""
KIRO_MCP Reasoning Loop - Continuous Learning from Problem-Solution Cycles
Project Creator: Herman Swanepoel

This module captures the complete reasoning journey:
1. Initial Problem
2. Reasoning Steps
3. Solution Attempts
4. Final Solution
5. Lessons Learned

All data is fed back to KIRO_MCP for continuous learning.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("kiro_mcp.reasoning_loop")


@dataclass
class ReasoningStep:
    """A single step in the reasoning process."""

    timestamp: str
    step_number: int
    thought: str
    action: str
    observation: str
    confidence: float


@dataclass
class ProblemSolutionCycle:
    """Complete problem-solution cycle with reasoning."""

    cycle_id: str
    timestamp_start: str
    timestamp_end: str | None

    # Problem
    initial_problem: str
    problem_context: dict[str, Any]
    problem_category: str

    # Reasoning Journey
    reasoning_steps: list[ReasoningStep]

    # Solution
    solution_attempts: list[dict[str, Any]]
    final_solution: str | None
    solution_success: bool

    # Learning
    lessons_learned: list[str]
    patterns_discovered: list[str]
    optimizations_identified: list[str]

    # Metadata
    agent_session_id: str
    user_id: str
    workspace: str


class ReasoningLoopManager:
    """Manages the reasoning loop and feedback to KIRO_MCP."""

    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.cycles_path = data_path / "reasoning_cycles"
        self.cycles_path.mkdir(exist_ok=True)

        self.current_cycle: ProblemSolutionCycle | None = None

    def start_cycle(
        self,
        problem: str,
        context: dict[str, Any],
        category: str = "general",
        session_id: str = "unknown",
        user_id: str = "herman",
        workspace: str = "unknown",
    ) -> str:
        """Start a new problem-solution cycle."""
        cycle_id = (
            f"cycle_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S_%f')}"
        )

        self.current_cycle = ProblemSolutionCycle(
            cycle_id=cycle_id,
            timestamp_start=datetime.now(UTC).isoformat(),
            timestamp_end=None,
            initial_problem=problem,
            problem_context=context,
            problem_category=category,
            reasoning_steps=[],
            solution_attempts=[],
            final_solution=None,
            solution_success=False,
            lessons_learned=[],
            patterns_discovered=[],
            optimizations_identified=[],
            agent_session_id=session_id,
            user_id=user_id,
            workspace=workspace,
        )

        logger.info(f"Started reasoning cycle: {cycle_id}")
        return cycle_id

    def add_reasoning_step(
        self,
        thought: str,
        action: str,
        observation: str,
        confidence: float = 0.8,
    ) -> None:
        """Add a reasoning step to the current cycle."""
        if not self.current_cycle:
            logger.warning("No active cycle - cannot add reasoning step")
            return

        step = ReasoningStep(
            timestamp=datetime.now(UTC).isoformat(),
            step_number=len(self.current_cycle.reasoning_steps) + 1,
            thought=thought,
            action=action,
            observation=observation,
            confidence=confidence,
        )

        self.current_cycle.reasoning_steps.append(step)
        logger.debug(f"Added reasoning step {step.step_number}")

    def add_solution_attempt(
        self,
        attempt: str,
        success: bool,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a solution attempt."""
        if not self.current_cycle:
            logger.warning("No active cycle - cannot add solution attempt")
            return

        attempt_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "attempt_number": len(self.current_cycle.solution_attempts) + 1,
            "solution": attempt,
            "success": success,
            "error": error,
            "metadata": metadata or {},
        }

        self.current_cycle.solution_attempts.append(attempt_data)
        logger.debug(
            f"Added solution attempt {attempt_data['attempt_number']}"
        )

    def complete_cycle(
        self,
        final_solution: str,
        success: bool,
        lessons: list[str] | None = None,
        patterns: list[str] | None = None,
        optimizations: list[str] | None = None,
    ) -> dict[str, Any]:
        """Complete the current cycle and save for learning."""
        if not self.current_cycle:
            logger.warning("No active cycle to complete")
            return {}

        self.current_cycle.timestamp_end = datetime.now(
            UTC
        ).isoformat()
        self.current_cycle.final_solution = final_solution
        self.current_cycle.solution_success = success
        self.current_cycle.lessons_learned = lessons or []
        self.current_cycle.patterns_discovered = patterns or []
        self.current_cycle.optimizations_identified = optimizations or []

        # Save to file
        cycle_file = self.cycles_path / f"{self.current_cycle.cycle_id}.json"
        with open(cycle_file, "w", encoding="utf-8") as f:
            json.dump(asdict(self.current_cycle), f, indent=2)

        logger.info(
            f"Completed and saved cycle: {self.current_cycle.cycle_id}"
        )

        # Extract learning data
        learning_data = self._extract_learning_data()

        # Save to knowledge base
        self._save_to_knowledge_base(learning_data)

        # Save patterns
        if patterns:
            self._save_patterns(patterns)

        # Save optimizations
        if optimizations:
            self._save_optimizations(optimizations)

        cycle_data = asdict(self.current_cycle)
        self.current_cycle = None

        return cycle_data

    def _extract_learning_data(self) -> dict[str, Any]:
        """Extract learning data from the completed cycle."""
        if not self.current_cycle:
            return {}

        return {
            "problem_type": self.current_cycle.problem_category,
            "reasoning_depth": len(self.current_cycle.reasoning_steps),
            "solution_attempts": len(self.current_cycle.solution_attempts),
            "success": self.current_cycle.solution_success,
            "key_insights": self.current_cycle.lessons_learned,
            "patterns": self.current_cycle.patterns_discovered,
            "optimizations": self.current_cycle.optimizations_identified,
            "reasoning_chain": [
                {
                    "step": step.step_number,
                    "thought": step.thought,
                    "confidence": step.confidence,
                }
                for step in self.current_cycle.reasoning_steps
            ],
        }

    def _save_to_knowledge_base(self, learning_data: dict[str, Any]) -> None:
        """Save learning data to knowledge base."""
        kb_path = self.data_path / "knowledge"
        kb_path.mkdir(exist_ok=True)

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        kb_file = kb_path / f"learning_{timestamp}.json"

        with open(kb_file, "w", encoding="utf-8") as f:
            json.dump(learning_data, f, indent=2)

        logger.info(f"Saved learning data to knowledge base: {kb_file.name}")

    def _save_patterns(self, patterns: list[str]) -> None:
        """Save discovered patterns."""
        patterns_path = self.data_path / "patterns"
        patterns_path.mkdir(exist_ok=True)

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        pattern_file = patterns_path / f"patterns_{timestamp}.json"

        with open(pattern_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "patterns": patterns,
                    "source_cycle": (
                        self.current_cycle.cycle_id
                        if self.current_cycle
                        else None
                    ),
                },
                f,
                indent=2,
            )

        logger.info(f"Saved patterns: {pattern_file.name}")

    def _save_optimizations(self, optimizations: list[str]) -> None:
        """Save identified optimizations."""
        opt_path = self.data_path / "optimizations"
        opt_path.mkdir(exist_ok=True)

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        opt_file = opt_path / f"optimization_{timestamp}.json"

        with open(opt_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "optimizations": optimizations,
                    "source_cycle": (
                        self.current_cycle.cycle_id
                        if self.current_cycle
                        else None
                    ),
                },
                f,
                indent=2,
            )

        logger.info(f"Saved optimizations: {opt_file.name}")

    def get_cycle_stats(self) -> dict[str, Any]:
        """Get statistics about all completed cycles."""
        cycles = list(self.cycles_path.glob("*.json"))

        total_cycles = len(cycles)
        successful_cycles = 0
        total_reasoning_steps = 0
        total_lessons = 0

        for cycle_file in cycles:
            with open(cycle_file, encoding="utf-8") as f:
                cycle_data = json.load(f)
                if cycle_data.get("solution_success"):
                    successful_cycles += 1
                total_reasoning_steps += len(
                    cycle_data.get("reasoning_steps", [])
                )
                total_lessons += len(cycle_data.get("lessons_learned", []))

        return {
            "total_cycles": total_cycles,
            "successful_cycles": successful_cycles,
            "success_rate": (
                successful_cycles / total_cycles if total_cycles > 0 else 0
            ),
            "avg_reasoning_steps": (
                total_reasoning_steps / total_cycles if total_cycles > 0 else 0
            ),
            "total_lessons_learned": total_lessons,
        }


# Global instance
_reasoning_loop_manager: ReasoningLoopManager | None = None


def get_reasoning_loop_manager(
    data_path: Path | None = None,
) -> ReasoningLoopManager:
    """Get or create the global reasoning loop manager."""
    global _reasoning_loop_manager

    if _reasoning_loop_manager is None:
        if data_path is None:
            data_path = Path(__file__).parent / "data"
        _reasoning_loop_manager = ReasoningLoopManager(data_path)

    return _reasoning_loop_manager
