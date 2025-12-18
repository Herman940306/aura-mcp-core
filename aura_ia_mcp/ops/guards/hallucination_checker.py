"""Hallucination Checker Guard.

Detects potential hallucinations in LLM outputs using heuristic checks.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HallucinationCheck:
    """Result of hallucination check."""

    hallucination_detected: bool
    confidence_score: float  # 0.0-1.0
    issues: list[str]
    warnings: list[str]
    metadata: dict[str, Any]


class HallucinationChecker:
    """Checks for hallucinations in LLM outputs."""

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode

        # Patterns that suggest hallucinations
        self.suspicious_patterns = [
            r"I (?:don't|do not) have (?:access|information)",
            r"As an AI",
            r"I (?:cannot|can't) (?:access|verify|confirm)",
            r"(?:fictional|made-up|invented) (?:data|information|fact)",
            r"I (?:just|simply) (?:made|invented|created) (?:that|this)",
        ]

        # Hedging phrases that suggest uncertainty
        self.hedging_phrases = [
            "might be",
            "could be",
            "possibly",
            "perhaps",
            "I think",
            "I believe",
            "probably",
            "likely",
            "seems like",
            "appears to",
        ]

        # Contradiction markers
        self.contradiction_markers = [
            "however",
            "but",
            "although",
            "on the other hand",
            "conversely",
        ]

    def check_text(
        self, text: str, context: dict[str, Any] | None = None
    ) -> HallucinationCheck:
        """Check text for hallucination indicators.

        Args:
            text: Text to check
            context: Optional context for verification

        Returns:
            HallucinationCheck result
        """
        issues = []
        warnings = []
        metadata = {}

        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Suspicious pattern detected: {pattern}")

        # Count hedging phrases
        hedging_count = sum(
            1
            for phrase in self.hedging_phrases
            if phrase.lower() in text.lower()
        )
        if hedging_count > 3:
            warnings.append(f"High hedging phrase count: {hedging_count}")
        metadata["hedging_count"] = hedging_count

        # Check for contradictions within text
        sentences = text.split(".")
        if len(sentences) > 1:
            contradiction_count = sum(
                1
                for sentence in sentences
                if any(
                    marker in sentence.lower()
                    for marker in self.contradiction_markers
                )
            )
            if contradiction_count > 0:
                warnings.append(
                    f"Potential contradictions: {contradiction_count}"
                )
            metadata["contradiction_markers"] = contradiction_count

        # Check for specific numeric claims without context
        numeric_claims = re.findall(
            r"\b\d+(?:\.\d+)?\s*(?:%|percent|dollars?|euros?|years?)\b", text
        )
        if len(numeric_claims) > 5 and not context:
            warnings.append(
                f"Many numeric claims without context: {len(numeric_claims)}"
            )
        metadata["numeric_claims"] = len(numeric_claims)

        # Check for overly confident claims
        certainty_markers = [
            "definitely",
            "certainly",
            "absolutely",
            "always",
            "never",
            "all",
            "none",
        ]
        certainty_count = sum(
            1 for marker in certainty_markers if marker.lower() in text.lower()
        )
        if certainty_count > 3:
            warnings.append(f"High certainty marker count: {certainty_count}")
        metadata["certainty_count"] = certainty_count

        # Calculate confidence score (inverse of issue severity)
        issue_weight = len(issues) * 0.3
        warning_weight = len(warnings) * 0.1
        confidence_score = max(0.0, 1.0 - issue_weight - warning_weight)

        hallucination_detected = len(issues) > 0 or (
            self.strict_mode and len(warnings) > 2
        )

        return HallucinationCheck(
            hallucination_detected=hallucination_detected,
            confidence_score=confidence_score,
            issues=issues,
            warnings=warnings,
            metadata=metadata,
        )

    def check_response(
        self, payload: dict, context: dict[str, Any] | None = None
    ) -> HallucinationCheck:
        """Check LLM response payload for hallucinations.

        Args:
            payload: Response payload with text content
            context: Optional verification context

        Returns:
            HallucinationCheck result
        """
        # Extract text from payload
        text = payload.get(
            "text", payload.get("content", payload.get("response", ""))
        )

        if not text:
            return HallucinationCheck(
                hallucination_detected=False,
                confidence_score=1.0,
                issues=[],
                warnings=["No text content found in payload"],
                metadata={},
            )

        return self.check_text(text, context)


# Global checker instance
_checker: HallucinationChecker | None = None


def get_checker(strict_mode: bool = False) -> HallucinationChecker:
    """Get or create global hallucination checker.

    Args:
        strict_mode: Enable strict checking

    Returns:
        HallucinationChecker instance
    """
    global _checker
    if _checker is None:
        _checker = HallucinationChecker(strict_mode=strict_mode)
    return _checker


def check_response(payload: dict) -> dict:
    """Legacy function for backward compatibility.

    Args:
        payload: Response payload to check

    Returns:
        Modified payload with hallucination_flag
    """
    checker = get_checker()
    result = checker.check_response(payload)

    payload["hallucination_flag"] = result.hallucination_detected
    payload["hallucination_confidence"] = result.confidence_score
    payload["hallucination_issues"] = result.issues
    payload["hallucination_warnings"] = result.warnings

    return payload
