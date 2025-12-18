"""Unit tests for multi-agent orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mcp_server.arbitration import ArbitrationEngine
from src.mcp_server.multi_agent_orchestrator import (
    AgentRole,
    MultiAgentOrchestrator,
)


@pytest.mark.asyncio
async def test_orchestrator_basic_flow():
    """Verify orchestrator executes full agent workflow."""
    # Mock adapter
    mock_adapter = MagicMock()
    mock_adapter.generate = MagicMock(
        side_effect=[
            "Strategy: approach X",
            "Critique: risk Y",
            "Synthesis: solution Z",
        ]
    )

    # Real arbitrator with mock embedding
    arbitrator = ArbitrationEngine()

    orchestrator = MultiAgentOrchestrator(mock_adapter, arbitrator)
    result = await orchestrator.orchestrate("Test query")

    assert "final_output" in result
    assert "provenance" in result
    assert result["provenance"]["arbitration_decision"] in [
        "selected_best",
        "consensus_refinement_needed",
    ]


@pytest.mark.asyncio
async def test_orchestrator_triggers_verification():
    """Verify verifier invoked when confidence below threshold."""
    mock_adapter = MagicMock()
    mock_adapter.generate = MagicMock(
        side_effect=[
            "Strategy: weak plan",
            "Critique: major flaws",
            "Synthesis: uncertain solution",
            "Verification: confirmed issues",
        ]
    )

    # Mock arbitrator to return low score
    mock_arbitrator = AsyncMock()
    mock_arbitrator.arbitrate = AsyncMock(
        return_value={
            "selected_output": {
                "text": "uncertain solution",
                "role": "synthesizer",
            },
            "divergence": 0.4,
            "scores": {
                "model_a": {"composite": 0.5, "coherence": 0.5, "safety": 1.0},
                "model_b": {"composite": 0.5, "coherence": 0.5, "safety": 1.0},
            },
            "decision": "selected_best",
        }
    )

    orchestrator = MultiAgentOrchestrator(mock_adapter, mock_arbitrator)
    result = await orchestrator.orchestrate(
        "Test query", confidence_threshold=0.8
    )

    # Should trigger verification due to low score (0.5 < 0.8)
    assert (
        mock_adapter.generate.call_count == 4
    )  # strategy, critic, synthesizer, verifier


@pytest.mark.asyncio
async def test_orchestrator_skips_verification():
    """Verify verifier skipped when confidence high."""
    mock_adapter = MagicMock()
    mock_adapter.generate = MagicMock(
        side_effect=[
            "Strategy: strong plan",
            "Critique: minor issues",
            "Synthesis: excellent solution",
        ]
    )

    # Mock arbitrator to return high score
    mock_arbitrator = AsyncMock()
    mock_arbitrator.arbitrate = AsyncMock(
        return_value={
            "selected_output": {
                "text": "excellent solution",
                "role": "synthesizer",
            },
            "divergence": 0.1,
            "scores": {
                "model_a": {"composite": 0.9, "coherence": 0.9, "safety": 1.0},
                "model_b": {"composite": 0.9, "coherence": 0.9, "safety": 1.0},
            },
            "decision": "selected_best",
        }
    )

    orchestrator = MultiAgentOrchestrator(mock_adapter, mock_arbitrator)
    result = await orchestrator.orchestrate(
        "Test query", confidence_threshold=0.7
    )

    # Should NOT trigger verification (0.9 > 0.7)
    assert (
        mock_adapter.generate.call_count == 3
    )  # strategy, critic, synthesizer only
    assert "Verification" not in result["final_output"]
    # Should NOT trigger verification (0.9 > 0.7)
    assert (
        mock_adapter.generate.call_count == 3
    )  # strategy, critic, synthesizer only
    assert "Verification" not in result["final_output"]
