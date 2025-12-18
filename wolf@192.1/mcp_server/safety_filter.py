"""Model safety filter for content moderation.

Implements multi-tier classification (severe, moderate, safe) with
configurable actions (block, flag, allow).
"""

from __future__ import annotations

import re
from typing import Any


class SafetyFilter:
    """Content moderation filter for model outputs."""

    def __init__(self):
        """Initialize safety patterns and thresholds."""
        # Pattern categories
        self.severe_patterns = [
            re.compile(r"\b(violence|harm|abuse)\b", re.IGNORECASE),
            re.compile(r"\b(malware|exploit|hack)\b", re.IGNORECASE),
        ]
        self.moderate_patterns = [
            re.compile(r"\b(controversial|sensitive)\b", re.IGNORECASE),
        ]

    def classify(self, text: str) -> dict[str, Any]:
        """Classify content safety level.

        Args:
            text: Content to classify

        Returns:
            Classification result with category, confidence, and matches
        """
        severe_matches = []
        for pattern in self.severe_patterns:
            matches = pattern.findall(text)
            severe_matches.extend(matches)

        moderate_matches = []
        for pattern in self.moderate_patterns:
            matches = pattern.findall(text)
            moderate_matches.extend(matches)

        if severe_matches:
            return {
                "category": "severe",
                "confidence": 0.9,
                "action": "block",
                "matches": severe_matches,
            }
        elif moderate_matches:
            return {
                "category": "moderate",
                "confidence": 0.7,
                "action": "flag",
                "matches": moderate_matches,
            }
        else:
            return {
                "category": "safe",
                "confidence": 1.0,
                "action": "allow",
                "matches": [],
            }

    def filter_output(self, text: str) -> dict[str, Any]:
        """Apply safety filter to output.

        Args:
            text: Model output text

        Returns:
            Filtering result with decision and filtered text
        """
        classification = self.classify(text)

        if classification["action"] == "block":
            return {
                "decision": "blocked",
                "filtered_text": "[CONTENT BLOCKED: Safety violation detected]",
                "classification": classification,
            }
        elif classification["action"] == "flag":
            return {
                "decision": "flagged",
                "filtered_text": text,
                "classification": classification,
            }
        else:
            return {
                "decision": "allowed",
                "filtered_text": text,
                "classification": classification,
            }


__all__ = ["SafetyFilter"]
