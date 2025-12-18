"""Unit tests for dual-model arbitration logic."""

from __future__ import annotations

import pytest

from src.mcp_server.arbitration import ArbitrationEngine


def test_divergence_identical_embeddings():
    """Verify divergence is 0 for identical embeddings."""
    engine = ArbitrationEngine()
    emb = [0.5, 0.5, 0.5]
    divergence = engine.compute_divergence(emb, emb)
    assert divergence == 0.0


def test_divergence_orthogonal_embeddings():
    """Verify divergence is 1 for orthogonal embeddings."""
    engine = ArbitrationEngine()
    emb_a = [1.0, 0.0, 0.0]
    emb_b = [0.0, 1.0, 0.0]
    divergence = engine.compute_divergence(emb_a, emb_b)
    assert divergence == 1.0


def test_coherence_scoring():
    """Verify coherence heuristic detects reasoning keywords."""
    engine = ArbitrationEngine()
    text_low = "Simple answer."
    text_high = "Therefore, because of this evidence, we can conclude specifically that..."
    score_low = engine.score_coherence(text_low)
    score_high = engine.score_coherence(text_high)
    assert score_high > score_low


def test_composite_score_weighting():
    """Verify composite score respects weights."""
    engine = ArbitrationEngine(
        semantic_weight=0.5, safety_weight=0.3, coherence_weight=0.2
    )
    score = engine.compute_composite_score(
        semantic_overlap=1.0, safety_confidence=1.0, coherence=1.0
    )
    assert score == 1.0

    score_partial = engine.compute_composite_score(
        semantic_overlap=0.5, safety_confidence=1.0, coherence=0.5
    )
    # 0.5*0.5 + 0.3*1.0 + 0.2*0.5 = 0.25 + 0.3 + 0.1 = 0.65
    assert abs(score_partial - 0.65) < 0.01


@pytest.mark.asyncio
async def test_arbitrate_selects_best():
    """Verify arbitration selects output with higher composite score."""
    engine = ArbitrationEngine(divergence_threshold=0.5)
    output_a = {"text": "Simple answer.", "safety_score": 1.0}
    output_b = {
        "text": "Therefore, based on evidence, the answer is...",
        "safety_score": 1.0,
    }
    result = await engine.arbitrate(output_a, output_b)
    # output_b has higher coherence
    assert result["selected_output"] == output_b
    assert result["decision"] == "selected_best"


@pytest.mark.asyncio
async def test_arbitrate_triggers_consensus():
    """Verify consensus refinement triggered on high divergence."""
    engine = ArbitrationEngine(divergence_threshold=0.2)

    async def mock_embedding(text: str) -> list[float]:
        # Return different embeddings to simulate divergence
        if "Model A" in text:
            return [1.0, 0.0, 0.0] * 256  # 768-dim
        return [0.0, 1.0, 0.0] * 256

    output_a = {"text": "Model A response", "safety_score": 1.0}
    output_b = {"text": "Model B response", "safety_score": 1.0}
    result = await engine.arbitrate(
        output_a, output_b, embedding_fn=mock_embedding
    )
    assert result["divergence"] > 0.2
    assert result["decision"] == "consensus_refinement_needed"


@pytest.mark.asyncio
async def test_arbitrate_safety_prioritization():
    """Verify lower safety score penalizes composite score."""
    engine = ArbitrationEngine(
        safety_weight=0.8, semantic_weight=0.1, coherence_weight=0.1
    )
    output_a = {"text": "Safe answer", "safety_score": 1.0}
    output_b = {"text": "Unsafe answer", "safety_score": 0.3}
    result = await engine.arbitrate(output_a, output_b)
    # output_a should win due to safety
    assert result["selected_output"] == output_a
    assert (
        result["scores"]["model_a"]["safety"]
        > result["scores"]["model_b"]["safety"]
    )
