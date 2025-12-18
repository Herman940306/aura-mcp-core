"""Honesty Policy Guard.

Enforces honesty policies on LLM outputs through claim verification and uncertainty handling.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HonestyAnalysis:
    """Result of honesty policy analysis."""

    compliant: bool
    confidence_score: float
    violations: list[str]
    suggestions: list[str]
    transformed_text: str | None
    metadata: dict[str, Any]


class HonestyPolicy:
    """Enforces honesty and truth-telling in LLM outputs."""

    def __init__(
        self, enforce_sources: bool = True, enforce_uncertainty: bool = True
    ):
        self.enforce_sources = enforce_sources
        self.enforce_uncertainty = enforce_uncertainty

        # Patterns for unsourced claims
        self.unsourced_claim_patterns = [
            r"(?:studies|research|data) (?:show|shows|indicate|suggests)",
            r"(?:according|refers) to (?:experts|scientists|researchers)",
            r"it is (?:proven|demonstrated|established) that",
            r"(?:all|most|many) (?:experts|scientists) (?:agree|believe)",
        ]

        # Absolute claim markers (may need hedging)
        self.absolute_markers = [
            "always",
            "never",
            "all",
            "none",
            "everyone",
            "no one",
            "impossible",
            "certain",
        ]

        # Proper hedge phrases
        self.hedge_phrases = [
            "generally",
            "typically",
            "often",
            "in many cases",
            "usually",
            "commonly",
            "frequently",
        ]

    def analyze_text(
        self, text: str, require_sources: bool | None = None
    ) -> HonestyAnalysis:
        """Analyze text for honesty policy compliance.

        Args:
            text: Text to analyze
            require_sources: Override source requirement

        Returns:
            HonestyAnalysis result
        """
        violations = []
        suggestions = []
        metadata = {}
        transformed = text

        require_src = (
            require_sources
            if require_sources is not None
            else self.enforce_sources
        )

        # Check for unsourced claims
        if require_src:
            for pattern in self.unsourced_claim_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    violations.append(f"Unsourced claim detected: {pattern}")
                    suggestions.append(
                        "Add source citations or use hedging language"
                    )

        # Check for absolute claims without hedging
        if self.enforce_uncertainty:
            absolute_count = sum(
                1
                for marker in self.absolute_markers
                if f" {marker} " in f" {text.lower()} "
            )

            if absolute_count > 2:
                violations.append(
                    f"Excessive absolute claims: {absolute_count}"
                )
                suggestions.append(
                    "Consider hedging with: generally, typically, often, etc."
                )

                # Auto-transform: add hedging to absolute claims
                for marker in self.absolute_markers:
                    pattern = rf"\b{marker}\b"
                    if re.search(pattern, transformed, re.IGNORECASE):
                        hedge = self.hedge_phrases[0]  # Use "generally"
                        transformed = re.sub(
                            pattern,
                            f"{hedge} {marker}",
                            transformed,
                            count=1,
                            flags=re.IGNORECASE,
                        )

            metadata["absolute_claims"] = absolute_count

        # Check for false confidence indicators
        false_confidence = [
            "I know for sure",
            "I am certain",
            "without a doubt",
            "100% accurate",
        ]
        confidence_count = sum(
            1 for phrase in false_confidence if phrase.lower() in text.lower()
        )
        if confidence_count > 0:
            violations.append(
                f"False confidence indicators: {confidence_count}"
            )
            suggestions.append(
                "Replace with: 'Based on available information' or 'To the best of my knowledge'"
            )
        metadata["false_confidence"] = confidence_count

        # Check for disclaimer absence on uncertain topics
        uncertain_topics = [
            "medical",
            "legal",
            "financial",
            "investment",
            "diagnosis",
            "treatment",
        ]
        has_disclaimer = any(
            phrase in text.lower()
            for phrase in [
                "consult a professional",
                "seek professional advice",
                "not professional advice",
            ]
        )

        if (
            any(topic in text.lower() for topic in uncertain_topics)
            and not has_disclaimer
        ):
            suggestions.append(
                "Consider adding disclaimer for professional advice (medical/legal/financial topics detected)"
            )
            metadata["professional_topic_detected"] = True

        # Calculate compliance
        compliant = len(violations) == 0
        confidence_score = max(0.0, 1.0 - len(violations) * 0.25)

        return HonestyAnalysis(
            compliant=compliant,
            confidence_score=confidence_score,
            violations=violations,
            suggestions=suggestions,
            transformed_text=transformed if transformed != text else None,
            metadata=metadata,
        )

    def enforce(self, text: str, auto_transform: bool = False) -> str:
        """Enforce honesty policy on text.

        Args:
            text: Input text
            auto_transform: Apply automatic transformations

        Returns:
            Original or transformed text
        """
        analysis = self.analyze_text(text)

        if auto_transform and analysis.transformed_text:
            logger.info(
                f"Applied honesty transformations: {len(analysis.violations)} violations addressed"
            )
            return analysis.transformed_text

        if not analysis.compliant:
            logger.warning(
                f"Honesty policy violations: {len(analysis.violations)}"
            )

        return text


# Global policy instance
_policy: HonestyPolicy | None = None


def get_policy() -> HonestyPolicy:
    """Get or create global honesty policy.

    Returns:
        HonestyPolicy instance
    """
    global _policy
    if _policy is None:
        _policy = HonestyPolicy()
    return _policy


def enforce_clauses(text: str) -> str:
    """Legacy function for backward compatibility.

    Args:
        text: Input text

    Returns:
        Processed text
    """
    policy = get_policy()
    return policy.enforce(text, auto_transform=False)
