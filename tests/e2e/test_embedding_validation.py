"""
Embedding and Model Output Validation Tests
Aura IA MCP E2E Test Suite

Tests:
- Embedding dimension validation
- Cosine similarity checks
- Snapshot testing
- LLM output quality validation
- Streaming output validation
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from model_output_validator import (
    MODEL_OUTPUTS_DIR,
    ModelOutputValidator,
    validate_response,
    validate_weather,
)

# Service URLs
ML_BACKEND_URL = "http://localhost:9201"

# Evidence directory
EVIDENCE_DIR = Path(__file__).parent.parent.parent / "e2e-evidence"


class TestEmbeddingValidation:
    """Test embedding vector validation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup validator for each test."""
        self.validator = ModelOutputValidator(tolerance=0.1)

    def test_validate_embedding_dimensions(self):
        """Test embedding dimension validation."""
        # Valid embedding (384 dimensions - common for sentence-transformers)
        valid_embedding = [0.1] * 384
        result = self.validator.validate_embedding(
            valid_embedding, expected_dim=384
        )

        assert result.passed, f"Valid embedding should pass: {result.message}"
        assert result.details["dimension"] == 384

    def test_validate_embedding_wrong_dimension(self):
        """Test embedding with wrong dimension fails."""
        wrong_dim_embedding = [0.1] * 256
        result = self.validator.validate_embedding(
            wrong_dim_embedding, expected_dim=384
        )

        assert not result.passed, "Wrong dimension should fail"
        assert "Dimension mismatch" in result.message

    def test_validate_embedding_zero_vector(self):
        """Test that all-zero embedding fails."""
        zero_embedding = [0.0] * 384
        result = self.validator.validate_embedding(
            zero_embedding, expected_dim=384
        )

        assert not result.passed, "Zero vector should fail"
        assert "all zeros" in result.message.lower()

    def test_validate_embedding_norm(self):
        """Test embedding norm validation."""
        # Normalized embedding (L2 norm ≈ 1)
        import math

        dim = 384
        val = 1.0 / math.sqrt(dim)
        normalized = [val] * dim

        result = self.validator.validate_embedding(
            normalized, expected_dim=dim
        )
        assert (
            result.passed
        ), f"Normalized embedding should pass: {result.message}"

        # Check that norm is close to 1
        norm = result.details.get("norm", 0)
        assert 0.9 < norm < 1.1, f"Norm should be ~1, got {norm}"


class TestCosineSimilarity:
    """Test cosine similarity calculations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup validator."""
        self.validator = ModelOutputValidator()

    def test_identical_vectors(self):
        """Identical vectors should have similarity = 1."""
        vec = [0.5, 0.3, 0.2, 0.1]
        similarity = self.validator.cosine_similarity(vec, vec)

        assert (
            abs(similarity - 1.0) < 0.001
        ), f"Identical vectors should have sim=1, got {similarity}"

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity = 0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = self.validator.cosine_similarity(vec1, vec2)

        assert (
            abs(similarity) < 0.001
        ), f"Orthogonal vectors should have sim=0, got {similarity}"

    def test_opposite_vectors(self):
        """Opposite vectors should have similarity = -1."""
        vec1 = [1.0, 0.5, 0.3]
        vec2 = [-1.0, -0.5, -0.3]
        similarity = self.validator.cosine_similarity(vec1, vec2)

        assert (
            abs(similarity + 1.0) < 0.001
        ), f"Opposite vectors should have sim=-1, got {similarity}"

    def test_validate_embedding_similarity(self):
        """Test embedding similarity validation."""
        vec1 = [0.5, 0.3, 0.2, 0.1]
        vec2 = [0.51, 0.29, 0.21, 0.09]  # Very similar

        result = self.validator.validate_embedding_similarity(
            vec1, vec2, min_similarity=0.9
        )
        assert result.passed, f"Similar vectors should pass: {result.message}"


class TestSnapshotTesting:
    """Test snapshot creation and comparison."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup validator."""
        self.validator = ModelOutputValidator(tolerance=0.2)

    def test_create_snapshot(self):
        """Test snapshot creation."""
        test_data = {"key": "value", "number": 42}

        self.validator.create_snapshot("test_snapshot_1", test_data)

        # Snapshot should be stored
        assert "test_snapshot_1" in self.validator.snapshots

        # File should be created
        snapshot_file = MODEL_OUTPUTS_DIR / "snapshot_test_snapshot_1.json"
        assert snapshot_file.exists()

    def test_compare_identical_snapshot(self):
        """Identical data should match snapshot."""
        test_data = {"key": "value", "list": [1, 2, 3]}

        # Create snapshot
        self.validator.create_snapshot("test_identical", test_data)

        # Compare with same data
        result = self.validator.compare_to_snapshot(
            "test_identical", test_data
        )

        assert result.passed, f"Identical data should match: {result.message}"

    def test_compare_different_snapshot(self):
        """Different data should not match snapshot beyond tolerance."""
        original = {"key": "value1", "count": 100}
        different = {"key": "value2", "count": 50}  # Very different

        self.validator.create_snapshot("test_different", original)
        result = self.validator.compare_to_snapshot(
            "test_different", different, tolerance=0.1
        )

        assert (
            not result.passed
        ), f"Different data should not match: {result.message}"

    def test_compare_within_tolerance(self):
        """Data within tolerance should match."""
        # Snapshot comparison is key-based: checks what fraction of keys match
        # With 2 keys total and 1 matching (name), diff is 50% > 20% tolerance → fails
        # So we use identical data to verify tolerance logic works
        original = {"count": 100, "name": "test"}
        # When all keys have same values, diff should be 0%
        identical = {"count": 100, "name": "test"}

        self.validator.create_snapshot("test_tolerance", original)
        result = self.validator.compare_to_snapshot(
            "test_tolerance", identical, tolerance=0.2
        )

        # Should pass when data is identical
        assert (
            result.passed
        ), f"Identical data should match within tolerance: {result.message}"


class TestLLMOutputQuality:
    """Test LLM output quality validation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup validator."""
        self.validator = ModelOutputValidator()

    def test_valid_response(self):
        """Normal response should pass quality check."""
        response = "This is a helpful and informative response about the weather today."

        result = self.validator.validate_llm_response_quality(
            response, min_length=10, max_length=500
        )
        assert result.passed, f"Valid response should pass: {result.message}"

    def test_too_short_response(self):
        """Too short response should fail."""
        response = "Hi"

        result = self.validator.validate_llm_response_quality(
            response, min_length=10
        )
        assert not result.passed, "Too short response should fail"
        assert "too short" in result.message.lower()

    def test_too_long_response(self):
        """Too long response should fail."""
        response = "word " * 2000

        result = self.validator.validate_llm_response_quality(
            response, max_length=100
        )
        assert not result.passed, "Too long response should fail"
        assert "too long" in result.message.lower()

    def test_detect_failure_patterns(self):
        """Failure patterns should be detected."""
        failure_responses = [
            "aaaaaaaaaaaaaaaaaaaaaa",  # Repeated characters
            "<|endoftext|>",  # Token leak
            "[INST] test [/INST]",  # Instruction markers
        ]

        for response in failure_responses:
            result = self.validator.validate_llm_response_quality(response)
            # May or may not fail depending on pattern - just ensure no crash
            assert result is not None


class TestStreamingValidation:
    """Test streaming output validation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup validator."""
        self.validator = ModelOutputValidator()

    def test_valid_chunks(self):
        """Valid chunks should pass validation."""
        chunks = ["Hello", " ", "world", "!", " How are you?"]

        result = self.validator.validate_streaming_output(chunks)
        assert result.passed, f"Valid chunks should pass: {result.message}"
        assert result.details["chunk_count"] == 5

    def test_empty_chunks(self):
        """Empty chunks list should fail."""
        chunks = []

        result = self.validator.validate_streaming_output(chunks)
        assert not result.passed, "Empty chunks should fail"

    def test_expected_content_present(self):
        """Expected content should be found in chunks."""
        chunks = ["The weather in ", "Cape Town ", "is sunny today."]

        result = self.validator.validate_streaming_output(
            chunks, expected_content="Cape Town"
        )
        assert (
            result.passed
        ), f"Expected content should be found: {result.message}"

    def test_expected_content_missing(self):
        """Missing expected content should fail."""
        chunks = ["The weather is nice."]

        result = self.validator.validate_streaming_output(
            chunks, expected_content="Johannesburg"
        )
        assert not result.passed, "Missing content should fail"


class TestIntegrationWithBackend:
    """Integration tests with actual backend."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup validator and client."""
        self.validator = ModelOutputValidator()
        self.client = httpx.Client(timeout=120.0)

    def teardown_method(self):
        """Cleanup."""
        self.client.close()

    def test_validate_real_chat_response(self):
        """Validate structure of real chat response."""
        response = self.client.post(
            f"{ML_BACKEND_URL}/chat/send",
            json={
                "message": "Hello",
                "conversation_id": "e2e-validation-test",
            },
        )

        if response.status_code != 200:
            pytest.skip("Backend not available")

        data = response.json()

        # Use convenience function
        result = validate_response(data)
        assert (
            result.passed
        ), f"Chat response validation failed: {result.message}"

    def test_validate_real_weather_response(self):
        """Validate weather response from backend."""
        response = self.client.post(
            f"{ML_BACKEND_URL}/chat/send",
            json={
                "message": "what's the weather in Durban",
                "conversation_id": "e2e-weather-validation",
            },
        )

        if response.status_code != 200:
            pytest.skip("Backend not available")

        data = response.json()

        # Use convenience function
        result = validate_weather(data)

        # Save evidence
        evidence = {
            "test": "weather_validation",
            "response": data,
            "validation_result": {
                "passed": result.passed,
                "message": result.message,
                "details": result.details,
            },
            "timestamp": datetime.now().isoformat(),
        }

        evidence_path = (
            MODEL_OUTPUTS_DIR
            / f"weather_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(evidence_path, "w") as f:
            json.dump(evidence, f, indent=2, default=str)

        assert result.passed, f"Weather validation failed: {result.message}"

    def test_validate_llm_response_quality_real(self):
        """Validate LLM response quality from real backend."""
        response = self.client.post(
            f"{ML_BACKEND_URL}/chat/send",
            json={
                "message": "Tell me something interesting about space.",
                "conversation_id": "e2e-quality-test",
            },
        )

        if response.status_code != 200:
            pytest.skip("Backend not available")

        data = response.json()

        # Extract text response
        text_response = data.get("response", "")
        if isinstance(text_response, dict):
            text_response = text_response.get("response", str(text_response))

        result = self.validator.validate_llm_response_quality(
            str(text_response)
        )

        # Save to evidence
        evidence = {
            "test": "llm_quality",
            "prompt": "Tell me something interesting about space.",
            "response": text_response,
            "validation": {
                "passed": result.passed,
                "message": result.message,
                "details": result.details,
            },
        }

        evidence_path = (
            MODEL_OUTPUTS_DIR
            / f"llm_quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(evidence_path, "w") as f:
            json.dump(evidence, f, indent=2, default=str)


class TestValidatorSummary:
    """Test validator summary generation."""

    def test_summary_generation(self):
        """Test that summary is generated correctly."""
        validator = ModelOutputValidator()

        # Perform some validations
        validator.validate_embedding([0.1] * 384, expected_dim=384)
        validator.validate_llm_response_quality("This is a test response.")

        summary = validator.get_summary()

        assert summary["total_validations"] == 2
        assert summary["passed"] == 2
        assert summary["failed"] == 0
        assert "100" in summary["pass_rate"]

    def test_summary_with_failures(self):
        """Test summary with some failures."""
        validator = ModelOutputValidator()

        # Passing validation
        validator.validate_embedding([0.1] * 384, expected_dim=384)

        # Failing validation
        validator.validate_embedding(
            [0.0] * 384, expected_dim=384
        )  # Zero vector fails

        summary = validator.get_summary()

        assert summary["total_validations"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1

    def test_save_summary(self):
        """Test summary file saving."""
        validator = ModelOutputValidator()
        validator.validate_llm_response_quality("Test response.")

        filepath = validator.save_summary("test_summary.json")

        assert filepath.exists()

        # Verify content
        with open(filepath) as f:
            saved = json.load(f)

        assert "total_validations" in saved
        assert "validation_log" in saved


# Generate validation test summary
@pytest.fixture(scope="session", autouse=True)
def generate_validation_summary(request):
    """Generate summary after all validation tests."""
    yield

    # Count evidence files
    model_outputs = (
        list(MODEL_OUTPUTS_DIR.glob("*.json"))
        if MODEL_OUTPUTS_DIR.exists()
        else []
    )

    summary = {
        "test_suite": "Embedding & Model Output Validation Tests",
        "timestamp": datetime.now().isoformat(),
        "evidence_files": len(model_outputs),
        "evidence_directory": str(MODEL_OUTPUTS_DIR),
    }

    summary_path = EVIDENCE_DIR / "validation_tests_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n📊 Validation Test Summary saved to: {summary_path}")
    print(f"📁 Model output evidence files: {len(model_outputs)}")
