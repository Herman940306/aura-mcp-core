"""Dual-model arbitration logic for multi-agent reasoning.

Orchestrates two models in conversation, computes divergence scoring,
and selects optimal output based on semantic overlap, safety, and coherence.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np


class ArbitrationEngine:
    """Arbitrates between outputs from dual-model reasoning."""

    def __init__(
        self,
        divergence_threshold: float = 0.3,
        safety_weight: float = 0.4,
        semantic_weight: float = 0.4,
        coherence_weight: float = 0.2,
    ):
        """Initialize arbitration engine.

        Args:
            divergence_threshold: Trigger consensus refinement if exceeded
            safety_weight: Weight for safety confidence score
            semantic_weight: Weight for semantic overlap
            coherence_weight: Weight for reasoning coherence
        """
        self.divergence_threshold = divergence_threshold
        self.safety_weight = safety_weight
        self.semantic_weight = semantic_weight
        self.coherence_weight = coherence_weight

    def compute_divergence(
        self, embedding_a: list[float], embedding_b: list[float]
    ) -> float:
        """Compute divergence index between two embeddings.

        Args:
            embedding_a: First output embedding
            embedding_b: Second output embedding

        Returns:
            Divergence score in [0, 1] (0=identical, 1=orthogonal)
        """
        vec_a = np.array(embedding_a)
        vec_b = np.array(embedding_b)
        cosine_sim = np.dot(vec_a, vec_b) / (
            np.linalg.norm(vec_a) * np.linalg.norm(vec_b) + 1e-9
        )
        divergence = 1.0 - float(cosine_sim)
        return max(0.0, min(1.0, divergence))

    def score_coherence(self, text: str) -> float:
        """Heuristic coherence scoring based on reasoning signals.

        Args:
            text: Model output text

        Returns:
            Coherence score in [0, 1]
        """
        # Simple heuristic: presence of reasoning keywords
        reasoning_keywords = [
            "therefore",
            "because",
            "however",
            "thus",
            "consequently",
            "for example",
            "specifically",
            "in particular",
        ]
        keyword_count = sum(
            1 for kw in reasoning_keywords if kw in text.lower()
        )
        # Normalize by expected density
        coherence = min(1.0, keyword_count / 3.0)
        return coherence

    def compute_composite_score(
        self,
        semantic_overlap: float,
        safety_confidence: float,
        coherence: float,
    ) -> float:
        """Compute weighted composite score.

        Args:
            semantic_overlap: Semantic similarity score [0,1]
            safety_confidence: Safety score [0,1] (1=safe)
            coherence: Reasoning coherence [0,1]

        Returns:
            Composite score [0,1]
        """
        score = (
            self.semantic_weight * semantic_overlap
            + self.safety_weight * safety_confidence
            + self.coherence_weight * coherence
        )
        return score

    async def arbitrate(
        self,
        output_a: dict[str, Any],
        output_b: dict[str, Any],
        embedding_fn: Any = None,
    ) -> dict[str, Any]:
        """Select optimal output from dual-model exchange.

        Args:
            output_a: First model output with keys: text, safety_score
            output_b: Second model output
            embedding_fn: Async callable to generate embeddings

        Returns:
            dict with keys: selected_output, divergence, scores, decision
        """
        # Extract texts
        text_a = output_a.get("text", "")
        text_b = output_b.get("text", "")

        # Generate embeddings if function provided
        if embedding_fn:
            emb_a, emb_b = await asyncio.gather(
                embedding_fn(text_a), embedding_fn(text_b)
            )
        else:
            # Fallback: mock embeddings for testing
            emb_a = [0.5] * 768
            emb_b = [0.5] * 768

        # Compute divergence
        divergence = self.compute_divergence(emb_a, emb_b)

        # Compute coherence scores
        coherence_a = self.score_coherence(text_a)
        coherence_b = self.score_coherence(text_b)

        # Extract safety scores (1.0 = safe)
        safety_a = output_a.get("safety_score", 1.0)
        safety_b = output_b.get("safety_score", 1.0)

        # Semantic overlap (inverse of divergence)
        semantic_overlap = 1.0 - divergence

        # Composite scores
        score_a = self.compute_composite_score(
            semantic_overlap, safety_a, coherence_a
        )
        score_b = self.compute_composite_score(
            semantic_overlap, safety_b, coherence_b
        )

        # Decision logic
        if divergence > self.divergence_threshold:
            decision = "consensus_refinement_needed"
            selected = output_a if score_a >= score_b else output_b
        else:
            decision = "selected_best"
            selected = output_a if score_a >= score_b else output_b

        return {
            "selected_output": selected,
            "divergence": divergence,
            "scores": {
                "model_a": {
                    "composite": score_a,
                    "coherence": coherence_a,
                    "safety": safety_a,
                },
                "model_b": {
                    "composite": score_b,
                    "coherence": coherence_b,
                    "safety": safety_b,
                },
            },
            "decision": decision,
        }


__all__ = ["ArbitrationEngine"]
