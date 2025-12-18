"""
Model Output Validator - Aura IA MCP E2E Testing
Validates LLM outputs, embeddings, and tool responses with deterministic checks.

Features:
- Cosine similarity for embedding validation
- Snapshot testing with tolerance
- Structure validation for JSON responses
- Streaming output validation
- Weather/tool response format validation
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Evidence output paths
EVIDENCE_DIR = Path(__file__).parent.parent.parent / "e2e-evidence"
MODEL_OUTPUTS_DIR = EVIDENCE_DIR / "model-outputs"
TOOL_RESULTS_DIR = EVIDENCE_DIR / "tool-results"

# Ensure directories exist
MODEL_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ValidationResult:
    """Result of a validation check."""

    passed: bool
    message: str
    details: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ModelOutputValidator:
    """Validates model outputs with deterministic checks."""

    # Expected response structure fields
    REQUIRED_CHAT_FIELDS = {"response", "success"}
    OPTIONAL_CHAT_FIELDS = {
        "tool_calls",
        "conversation_id",
        "mode",
        "llm_used",
        "blocked",
        "error",
    }

    # Weather response expected fields
    WEATHER_REQUIRED_FIELDS = {"response", "weather_data", "location"}
    WEATHER_DATA_FIELDS = {"current_weather", "latitude", "longitude"}

    # Tool response structure
    TOOL_REQUIRED_FIELDS = {"tool", "arguments", "result"}

    def __init__(self, tolerance: float = 0.1):
        """Initialize validator with tolerance settings."""
        self.tolerance = tolerance
        self.snapshots: dict[str, Any] = {}
        self.validation_log: list[ValidationResult] = []

    def validate_chat_response_structure(
        self, response: dict[str, Any]
    ) -> ValidationResult:
        """Validate chat response has required structure."""
        missing = self.REQUIRED_CHAT_FIELDS - set(response.keys())

        if missing:
            result = ValidationResult(
                passed=False,
                message=f"Missing required fields: {missing}",
                details={
                    "missing_fields": list(missing),
                    "response_keys": list(response.keys()),
                },
            )
        else:
            result = ValidationResult(
                passed=True,
                message="Chat response structure valid",
                details={"fields_present": list(response.keys())},
            )

        self.validation_log.append(result)
        self._save_evidence("chat_structure", response, result)
        return result

    def validate_weather_response(
        self, response: dict[str, Any]
    ) -> ValidationResult:
        """Validate weather response format and content."""
        errors = []

        # Check if response contains weather data
        inner_response = response.get("response", response)

        if isinstance(inner_response, dict):
            # Check for weather_data field
            if "weather_data" not in inner_response:
                errors.append("Missing weather_data field")
            else:
                weather_data = inner_response["weather_data"]
                if "current_weather" not in weather_data:
                    errors.append("Missing current_weather in weather_data")
                else:
                    current = weather_data["current_weather"]
                    if "temperature" not in current:
                        errors.append("Missing temperature in current_weather")
                    if "windspeed" not in current:
                        errors.append("Missing windspeed in current_weather")

            # Check for human-readable response
            if "response" in inner_response:
                text_response = inner_response["response"]
                if not isinstance(text_response, str):
                    errors.append("Human-readable response should be string")
                elif len(text_response) < 20:
                    errors.append("Human-readable response too short")
                # Check for natural language indicators
                natural_indicators = [
                    "°C",
                    "°F",
                    "km/h",
                    "mph",
                    "weather",
                    "temperature",
                ]
                if not any(ind in text_response for ind in natural_indicators):
                    errors.append(
                        "Response doesn't appear to be natural weather description"
                    )

        elif isinstance(inner_response, str):
            # String response - check for weather content
            if not any(
                word in inner_response.lower()
                for word in [
                    "weather",
                    "temperature",
                    "°",
                    "celsius",
                    "fahrenheit",
                ]
            ):
                errors.append(
                    "String response doesn't contain weather information"
                )

        result = ValidationResult(
            passed=len(errors) == 0,
            message=(
                "Weather response valid"
                if not errors
                else f"Weather validation failed: {errors}"
            ),
            details={
                "errors": errors,
                "response_type": type(inner_response).__name__,
            },
        )

        self.validation_log.append(result)
        self._save_evidence("weather_response", response, result)
        return result

    def validate_tool_response(
        self, tool_name: str, response: dict[str, Any]
    ) -> ValidationResult:
        """Validate MCP tool response structure."""
        errors = []

        # Tool responses should have success indicator
        if "success" not in response and "result" not in response:
            errors.append("Missing success/result field")

        # Check for error handling
        if response.get("success") is False:
            if "error" not in response:
                errors.append("Failed response missing error message")

        result = ValidationResult(
            passed=len(errors) == 0,
            message=(
                f"Tool '{tool_name}' response valid"
                if not errors
                else f"Tool validation failed: {errors}"
            ),
            details={
                "tool_name": tool_name,
                "errors": errors,
                "response_keys": list(response.keys()),
            },
        )

        self.validation_log.append(result)
        self._save_evidence(f"tool_{tool_name}", response, result)
        return result

    def validate_embedding(
        self,
        embedding: list[float],
        expected_dim: int = 384,
        min_norm: float = 0.5,
        max_norm: float = 2.0,
    ) -> ValidationResult:
        """Validate embedding vector properties."""
        errors = []

        # Check dimension
        if len(embedding) != expected_dim:
            errors.append(
                f"Dimension mismatch: got {len(embedding)}, expected {expected_dim}"
            )

        # Check for valid floats
        if not all(isinstance(x, (int, float)) for x in embedding):
            errors.append("Embedding contains non-numeric values")

        # Check norm (L2 normalized embeddings should have norm ≈ 1)
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm < min_norm or norm > max_norm:
            errors.append(
                f"Embedding norm {norm:.4f} outside valid range [{min_norm}, {max_norm}]"
            )

        # Check for degenerate values
        if all(x == 0 for x in embedding):
            errors.append("Embedding is all zeros")

        result = ValidationResult(
            passed=len(errors) == 0,
            message=(
                "Embedding valid"
                if not errors
                else f"Embedding validation failed: {errors}"
            ),
            details={
                "dimension": len(embedding),
                "norm": round(norm, 4),
                "errors": errors,
            },
        )

        self.validation_log.append(result)
        return result

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            raise ValueError(
                f"Vector dimension mismatch: {len(vec1)} vs {len(vec2)}"
            )

        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        norm1 = math.sqrt(sum(x * x for x in vec1))
        norm2 = math.sqrt(sum(x * x for x in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def validate_embedding_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
        min_similarity: float = 0.7,
        label: str = "embeddings",
    ) -> ValidationResult:
        """Validate two embeddings are similar enough."""
        try:
            similarity = self.cosine_similarity(embedding1, embedding2)
            passed = similarity >= min_similarity

            result = ValidationResult(
                passed=passed,
                message=f"Similarity {similarity:.4f} {'≥' if passed else '<'} threshold {min_similarity}",
                details={
                    "similarity": round(similarity, 4),
                    "threshold": min_similarity,
                    "label": label,
                },
            )
        except ValueError as e:
            result = ValidationResult(
                passed=False,
                message=f"Similarity check failed: {e}",
                details={"error": str(e), "label": label},
            )

        self.validation_log.append(result)
        return result

    def create_snapshot(self, name: str, data: Any) -> None:
        """Create a snapshot of output for future comparison."""
        self.snapshots[name] = {
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "hash": hash(json.dumps(data, sort_keys=True, default=str)),
        }

        # Save to file
        snapshot_path = MODEL_OUTPUTS_DIR / f"snapshot_{name}.json"
        with open(snapshot_path, "w") as f:
            json.dump(self.snapshots[name], f, indent=2, default=str)

    def compare_to_snapshot(
        self, name: str, data: Any, tolerance: float | None = None
    ) -> ValidationResult:
        """Compare data to a stored snapshot."""
        tolerance = tolerance or self.tolerance

        if name not in self.snapshots:
            # Try loading from file
            snapshot_path = MODEL_OUTPUTS_DIR / f"snapshot_{name}.json"
            if snapshot_path.exists():
                with open(snapshot_path) as f:
                    self.snapshots[name] = json.load(f)
            else:
                # Create new snapshot
                self.create_snapshot(name, data)
                return ValidationResult(
                    passed=True,
                    message=f"Created new snapshot: {name}",
                    details={"action": "created", "name": name},
                )

        # Compare
        expected = self.snapshots[name]["data"]
        diff = self._calculate_diff(expected, data)

        passed = diff["score"] >= (1 - tolerance)

        result = ValidationResult(
            passed=passed,
            message=(
                f"Snapshot match: {diff['score']:.2%}"
                if passed
                else f"Snapshot mismatch: {diff['score']:.2%}"
            ),
            details={"diff": diff, "tolerance": tolerance, "name": name},
        )

        self.validation_log.append(result)
        return result

    def _calculate_diff(self, expected: Any, actual: Any) -> dict[str, Any]:
        """Calculate difference between expected and actual values."""
        if type(expected) != type(actual):
            return {
                "score": 0.0,
                "reason": "type_mismatch",
                "expected_type": type(expected).__name__,
                "actual_type": type(actual).__name__,
            }

        if isinstance(expected, dict):
            all_keys = set(expected.keys()) | set(actual.keys())
            if not all_keys:
                return {"score": 1.0, "reason": "both_empty_dicts"}

            matching = 0
            for key in all_keys:
                if key in expected and key in actual:
                    if expected[key] == actual[key]:
                        matching += 1
                    elif isinstance(expected[key], (dict, list)):
                        sub_diff = self._calculate_diff(
                            expected[key], actual[key]
                        )
                        matching += sub_diff["score"]

            return {
                "score": matching / len(all_keys),
                "reason": "dict_comparison",
                "total_keys": len(all_keys),
                "matching": matching,
            }

        if isinstance(expected, list):
            if len(expected) == 0 and len(actual) == 0:
                return {"score": 1.0, "reason": "both_empty_lists"}
            if len(expected) != len(actual):
                return {
                    "score": 0.5,
                    "reason": "length_mismatch",
                    "expected_len": len(expected),
                    "actual_len": len(actual),
                }

            matching = sum(
                1 for e, a in zip(expected, actual, strict=False) if e == a
            )
            return {
                "score": matching / len(expected),
                "reason": "list_comparison",
            }

        if isinstance(expected, (int, float)):
            if expected == 0 and actual == 0:
                return {"score": 1.0, "reason": "both_zero"}
            if expected == 0 or actual == 0:
                return {"score": 0.0, "reason": "one_zero"}
            ratio = min(expected, actual) / max(expected, actual)
            return {"score": ratio, "reason": "numeric_comparison"}

        # String or other
        if expected == actual:
            return {"score": 1.0, "reason": "exact_match"}

        # Fuzzy string match
        if isinstance(expected, str):
            expected_words = set(expected.lower().split())
            actual_words = set(actual.lower().split())
            if not expected_words:
                return {
                    "score": 1.0 if not actual_words else 0.0,
                    "reason": "empty_expected",
                }
            overlap = len(expected_words & actual_words) / len(
                expected_words | actual_words
            )
            return {"score": overlap, "reason": "string_fuzzy_match"}

        return {"score": 0.0, "reason": "unknown_type"}

    def validate_llm_response_quality(
        self, response: str, min_length: int = 10, max_length: int = 5000
    ) -> ValidationResult:
        """Validate LLM response quality metrics."""
        errors = []

        # Length checks
        if len(response) < min_length:
            errors.append(
                f"Response too short: {len(response)} < {min_length}"
            )
        if len(response) > max_length:
            errors.append(f"Response too long: {len(response)} > {max_length}")

        # Check for common LLM failure patterns
        failure_patterns = [
            r"^(\s*\n){3,}",  # Excessive newlines
            r"(.)\1{10,}",  # Repeated characters
            r"undefined|null|NaN",  # Programming artifacts
            r"<\|.*?\|>",  # Model tokens leaked
            r"\[INST\]|\[/INST\]",  # Instruction markers
            r"<s>|</s>",  # Token markers
        ]

        for pattern in failure_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                errors.append(f"Detected failure pattern: {pattern}")

        # Check for coherence (basic)
        words = response.split()
        if len(words) < 3 and len(response) > 20:
            errors.append("Response lacks word separation")

        result = ValidationResult(
            passed=len(errors) == 0,
            message=(
                "LLM response quality valid"
                if not errors
                else f"Quality issues: {errors}"
            ),
            details={
                "length": len(response),
                "word_count": len(words),
                "errors": errors,
            },
        )

        self.validation_log.append(result)
        return result

    def validate_streaming_output(
        self, chunks: list[str], expected_content: str | None = None
    ) -> ValidationResult:
        """Validate streaming output chunks."""
        errors = []

        if not chunks:
            errors.append("No chunks received")
        else:
            # Check chunk continuity
            full_output = "".join(chunks)

            if len(full_output) == 0:
                errors.append("Empty combined output")

            # Check for chunk ordering issues
            for i, chunk in enumerate(chunks):
                if chunk is None:
                    errors.append(f"Chunk {i} is None")

            if expected_content:
                # Check if expected content is present
                if expected_content.lower() not in full_output.lower():
                    errors.append(
                        f"Expected content '{expected_content}' not found"
                    )

        result = ValidationResult(
            passed=len(errors) == 0,
            message=(
                "Streaming output valid"
                if not errors
                else f"Streaming issues: {errors}"
            ),
            details={
                "chunk_count": len(chunks),
                "total_length": len("".join(chunks)) if chunks else 0,
                "errors": errors,
            },
        )

        self.validation_log.append(result)
        return result

    def _save_evidence(
        self, name: str, data: Any, result: ValidationResult
    ) -> None:
        """Save validation evidence to file."""
        evidence = {
            "name": name,
            "timestamp": result.timestamp,
            "passed": result.passed,
            "message": result.message,
            "details": result.details,
            "data": data,
        }

        # Determine directory based on type
        if "tool" in name.lower():
            evidence_dir = TOOL_RESULTS_DIR
        else:
            evidence_dir = MODEL_OUTPUTS_DIR

        filepath = (
            evidence_dir / f"{result.timestamp.replace(':', '-')}_{name}.json"
        )
        with open(filepath, "w") as f:
            json.dump(evidence, f, indent=2, default=str)

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all validations performed."""
        total = len(self.validation_log)
        passed = sum(1 for r in self.validation_log if r.passed)
        failed = total - passed

        return {
            "total_validations": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "N/A",
            "validation_log": [
                {
                    "passed": r.passed,
                    "message": r.message,
                    "timestamp": r.timestamp,
                }
                for r in self.validation_log
            ],
        }

    def save_summary(self, filename: str = "validation_summary.json") -> Path:
        """Save validation summary to file."""
        summary = self.get_summary()
        filepath = EVIDENCE_DIR / filename
        with open(filepath, "w") as f:
            json.dump(summary, f, indent=2)
        return filepath


# Convenience functions for test files
def validate_response(response: dict) -> ValidationResult:
    """Quick validation of a chat response."""
    validator = ModelOutputValidator()
    return validator.validate_chat_response_structure(response)


def validate_weather(response: dict) -> ValidationResult:
    """Quick validation of a weather response."""
    validator = ModelOutputValidator()
    return validator.validate_weather_response(response)


def validate_embedding(
    embedding: list[float], dim: int = 384
) -> ValidationResult:
    """Quick validation of an embedding vector."""
    validator = ModelOutputValidator()
    return validator.validate_embedding(embedding, expected_dim=dim)
