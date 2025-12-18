"""Multi-agent orchestration engine for dual-model reasoning workflows.

Implements Strategy → Critic → Synthesizer → Verifier pattern.
"""

from __future__ import annotations

import asyncio
from typing import Any


class AgentRole:
    """Agent role definitions."""

    STRATEGIST = "strategist"
    CRITIC = "critic"
    SYNTHESIZER = "synthesizer"
    VERIFIER = "verifier"
    SAFETY_GUARDIAN = "safety_guardian"


class MultiAgentOrchestrator:
    """Orchestrates multi-agent reasoning workflow."""

    def __init__(self, model_adapter: Any, arbitration_engine: Any):
        """Initialize orchestrator.

        Args:
            model_adapter: Model backend adapter
            arbitration_engine: Arbitration engine for output selection
        """
        self.adapter = model_adapter
        self.arbitrator = arbitration_engine

    async def _invoke_agent(
        self, role: str, context: dict[str, Any], system_prompt: str
    ) -> dict[str, Any]:
        """Invoke single agent with role-specific prompt.

        Args:
            role: Agent role identifier
            context: Current conversation context
            system_prompt: Role-specific system prompt

        Returns:
            Agent output with text and metadata
        """
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context.get("user_query", "")},
        ]
        # Add prior agent outputs if present
        if "history" in context:
            messages.extend(context["history"])

        # Generate response
        response = await asyncio.to_thread(
            self.adapter.generate, prompt=str(messages)
        )

        return {
            "text": response,
            "role": role,
            "safety_score": 1.0,  # Placeholder
        }

    async def orchestrate(
        self, user_query: str, confidence_threshold: float = 0.7
    ) -> dict[str, Any]:
        """Execute multi-agent reasoning workflow.

        Args:
            user_query: User input
            confidence_threshold: Minimum score to skip verification

        Returns:
            Final output with provenance trace
        """
        context: dict[str, Any] = {"user_query": user_query, "history": []}

        # Phase 1: Strategy Agent
        strategy_output = await self._invoke_agent(
            AgentRole.STRATEGIST,
            context,
            "You are a strategic planner. Break down the problem and outline approach.",
        )
        context["history"].append(
            {"role": "assistant", "content": strategy_output["text"]}
        )

        # Phase 2: Critic Agent challenges
        critic_output = await self._invoke_agent(
            AgentRole.CRITIC,
            context,
            "You are a critical evaluator. Identify flaws, edge cases, and risks.",
        )
        context["history"].append(
            {"role": "assistant", "content": critic_output["text"]}
        )

        # Phase 3: Synthesizer merges insights
        synthesizer_output = await self._invoke_agent(
            AgentRole.SYNTHESIZER,
            context,
            "You are a synthesizer. Merge strategy and critique into coherent solution.",
        )

        # Phase 4: Arbitrate between strategy and synthesizer
        arbitration = await self.arbitrator.arbitrate(
            strategy_output, synthesizer_output
        )
        selected = arbitration["selected_output"]
        composite_score = max(
            arbitration["scores"]["model_a"]["composite"],
            arbitration["scores"]["model_b"]["composite"],
        )

        # Phase 5: Verifier (optional if low confidence)
        if composite_score < confidence_threshold:
            context["history"].append(
                {"role": "assistant", "content": selected["text"]}
            )
            verifier_output = await self._invoke_agent(
                AgentRole.VERIFIER,
                context,
                "You are a verifier. Validate correctness, safety, and consistency.",
            )
            final_output = verifier_output
        else:
            final_output = selected

        return {
            "final_output": final_output["text"],
            "provenance": {
                "strategy": strategy_output["text"][:200],
                "critique": critic_output["text"][:200],
                "synthesis": synthesizer_output["text"][:200],
                "arbitration_decision": arbitration["decision"],
                "divergence": arbitration["divergence"],
                "composite_score": composite_score,
            },
        }


__all__ = ["MultiAgentOrchestrator", "AgentRole"]
