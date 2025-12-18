"""Enhanced arbitration engine with semantic scoring."""

import difflib
from typing import Any


class ArbitrationEngine:
    """Engine for arbitrating between multiple model outputs."""

    def __init__(self):
        pass

    def compare(self, output_a: str, output_b: str) -> float:
        """
        Compare two outputs and return a divergence score.

        Args:
            output_a: First output
            output_b: Second output

        Returns:
            Divergence score (0.0 = identical, 1.0 = completely different)
        """
        if not output_a or not output_b:
            return 1.0

        # Use SequenceMatcher for semantic similarity
        similarity = difflib.SequenceMatcher(None, output_a, output_b).ratio()
        divergence = 1.0 - similarity

        return divergence

    def semantic_similarity(self, output_a: str, output_b: str) -> float:
        """
        Calculate semantic similarity between two outputs.

        Uses a hybrid of SequenceMatcher ratio and Jaccard word overlap
        to better handle minor lexical variations (e.g., "4" vs "four").

        Returns:
            Similarity score (0.0 = no overlap, 1.0 = identical)
        """
        a = output_a or ""
        b = output_b or ""
        # Sequence similarity
        seq_sim = difflib.SequenceMatcher(None, a, b).ratio()
        # Word overlap
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if words_a and words_b:
            intersection = words_a & words_b
            union = words_a | words_b
            jaccard = len(intersection) / len(union) if union else 0.0
        else:
            jaccard = 0.0
        # Use the max to be tolerant to minor lexical differences
        return max(seq_sim, jaccard)

    def score_quality(self, output: str) -> dict[str, float]:
        """
        Score output quality on multiple dimensions.

        Returns:
            Dictionary of quality scores
        """
        scores = {
            "length": min(len(output) / 1000, 1.0),  # Normalize to 0-1
            "completeness": (
                1.0 if output.strip().endswith((".", "!", "?")) else 0.5
            ),
            "structure": self._score_structure(output),
        }

        return scores

    def _score_structure(self, output: str) -> float:
        """Score structural quality (paragraphs, formatting)."""
        lines = output.split("\n")
        non_empty_lines = [l for l in lines if l.strip()]

        # Simple heuristic: well-structured text has multiple paragraphs
        if len(non_empty_lines) > 3:
            return 1.0
        elif len(non_empty_lines) > 1:
            return 0.7
        return 0.5

    def arbitrate(self, responses: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Select the best response from a list of candidates.

        Args:
            responses: List of response dictionaries with 'content' and optional 'metadata'

        Returns:
            Best response with arbitration metadata
        """
        if not responses:
            return {}

        if len(responses) == 1:
            return responses[0]

        # Score each response
        scored_responses = []
        for resp in responses:
            content = resp.get("content", "")
            quality_scores = self.score_quality(content)

            # Calculate overall score (weighted average)
            overall_score = (
                quality_scores["length"] * 0.3
                + quality_scores["completeness"] * 0.4
                + quality_scores["structure"] * 0.3
            )

            scored_responses.append(
                {
                    **resp,
                    "arbitration_score": overall_score,
                    "quality_breakdown": quality_scores,
                }
            )

        # Sort by score and return best
        best = max(scored_responses, key=lambda x: x["arbitration_score"])

        # Add comparison metadata
        if len(responses) == 2:
            divergence = self.compare(
                responses[0].get("content", ""),
                responses[1].get("content", ""),
            )
            best["divergence_from_alternative"] = divergence

        return best

    def detect_consensus(
        self, responses: list[dict[str, Any]], threshold: float = 0.7
    ) -> dict[str, Any]:
        """
        Detect if responses show consensus.

        Args:
            responses: List of responses
            threshold: Similarity threshold for consensus

        Returns:
            Dict with keys:
              - has_consensus: bool
              - avg_similarity: float
        """
        if len(responses) < 2:
            return {"has_consensus": True, "avg_similarity": 1.0}

        # Compare all pairs
        similarities = []
        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                sim = self.semantic_similarity(
                    responses[i].get("content", ""),
                    responses[j].get("content", ""),
                )
                similarities.append(sim)

        # Consensus if average similarity above threshold
        avg_similarity = (
            sum(similarities) / len(similarities) if similarities else 0.0
        )
        return {
            "has_consensus": avg_similarity >= threshold,
            "avg_similarity": avg_similarity,
        }
