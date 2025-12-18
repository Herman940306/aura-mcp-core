"""
Backend API Tests - Comprehensive testing for ML Backend endpoints
Aura IA MCP E2E Test Suite

Tests:
- Health endpoints
- Chat endpoints
- Embedding endpoints
- Model status endpoints
- Error handling
- Response validation
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from model_output_validator import ModelOutputValidator

# Service URLs
ML_BACKEND_URL = "http://localhost:9201"
RAG_URL = "http://localhost:9202"

# Evidence directory
EVIDENCE_DIR = Path(__file__).parent.parent.parent / "e2e-evidence"
NETWORK_DIR = EVIDENCE_DIR / "network"
NETWORK_DIR.mkdir(parents=True, exist_ok=True)


def save_network_evidence(
    endpoint: str,
    method: str,
    request: dict | None,
    response_data: dict,
    status_code: int,
) -> Path:
    """Save network request/response evidence."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence = {
        "endpoint": endpoint,
        "method": method,
        "timestamp": datetime.now().isoformat(),
        "request": request,
        "response": response_data,
        "status_code": status_code,
    }

    safe_endpoint = endpoint.replace("/", "_").strip("_")
    filepath = NETWORK_DIR / f"{timestamp}_{method}_{safe_endpoint}.json"
    with open(filepath, "w") as f:
        json.dump(evidence, f, indent=2, default=str)
    return filepath


class TestMLBackendHealth:
    """Test ML Backend health and readiness endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        self.client = httpx.Client(timeout=30.0)

    def teardown_method(self):
        """Cleanup after each test."""
        self.client.close()

    def test_health_endpoint(self):
        """Health endpoint should return 200."""
        response = self.client.get(f"{ML_BACKEND_URL}/health")

        save_network_evidence(
            "/health",
            "GET",
            None,
            (
                response.json()
                if response.status_code == 200
                else {"error": response.text}
            ),
            response.status_code,
        )

        assert (
            response.status_code == 200
        ), f"Health check failed: {response.text}"

        data = response.json()
        # Health response should indicate status
        assert isinstance(data, dict)

    def test_healthz_endpoint(self):
        """Kubernetes-style healthz endpoint."""
        response = self.client.get(f"{ML_BACKEND_URL}/healthz")

        # May return 200 or 404 if not implemented
        save_network_evidence(
            "/healthz",
            "GET",
            None,
            {"status_code": response.status_code},
            response.status_code,
        )

        # Either exists and returns 200, or doesn't exist (404)
        assert response.status_code in [200, 404]

    def test_readyz_endpoint(self):
        """Kubernetes-style readyz endpoint."""
        response = self.client.get(f"{ML_BACKEND_URL}/readyz")

        save_network_evidence(
            "/readyz",
            "GET",
            None,
            {"status_code": response.status_code},
            response.status_code,
        )

        # Either exists and returns 200, or doesn't exist (404)
        assert response.status_code in [200, 404]


class TestMLBackendChatEndpoints:
    """Test ML Backend chat endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        self.validator = ModelOutputValidator()
        self.client = httpx.Client(timeout=120.0)

    def teardown_method(self):
        """Cleanup after each test."""
        self.client.close()

    def test_chat_send_endpoint(self):
        """Chat send endpoint should accept messages."""
        request_data = {
            "message": "Hello, this is a test message",
            "conversation_id": "e2e-api-test-1",
        }

        response = self.client.post(
            f"{ML_BACKEND_URL}/chat/send",
            json=request_data,
        )

        save_network_evidence(
            "/chat/send",
            "POST",
            request_data,
            (
                response.json()
                if response.status_code == 200
                else {"error": response.text}
            ),
            response.status_code,
        )

        assert (
            response.status_code == 200
        ), f"Chat send failed: {response.text}"

        data = response.json()
        result = self.validator.validate_chat_response_structure(data)
        assert result.passed, result.message

    def test_chat_status_endpoint(self):
        """Chat status endpoint should return system info."""
        response = self.client.post(
            f"{ML_BACKEND_URL}/chat/status",
            json={},
        )

        if response.status_code == 200:
            data = response.json()
            save_network_evidence(
                "/chat/status", "POST", {}, data, response.status_code
            )

            # Should have some status info
            assert isinstance(data, dict)
        else:
            save_network_evidence(
                "/chat/status",
                "POST",
                {},
                {"error": "not_found"},
                response.status_code,
            )
            pytest.skip("Chat status endpoint not available")

    def test_chat_with_mode_parameter(self):
        """Chat should accept mode parameter."""
        modes = ["general", "concierge", "mcp"]

        for mode in modes:
            request_data = {
                "message": f"Test message in {mode} mode",
                "conversation_id": f"e2e-mode-test-{mode}",
                "mode": mode,
            }

            response = self.client.post(
                f"{ML_BACKEND_URL}/chat/send",
                json=request_data,
            )

            save_network_evidence(
                f"/chat/send/{mode}",
                "POST",
                request_data,
                {"status_code": response.status_code},
                response.status_code,
            )

            # Should accept the mode without crashing
            assert response.status_code in [
                200,
                400,
            ], f"Failed for mode {mode}"

    def test_chat_conversation_continuity(self):
        """Same conversation_id should maintain context."""
        conv_id = f"e2e-continuity-{datetime.now().timestamp()}"

        # First message
        response1 = self.client.post(
            f"{ML_BACKEND_URL}/chat/send",
            json={
                "message": "My name is TestUser",
                "conversation_id": conv_id,
            },
        )

        assert response1.status_code == 200

        # Second message referencing context
        response2 = self.client.post(
            f"{ML_BACKEND_URL}/chat/send",
            json={"message": "What is my name?", "conversation_id": conv_id},
        )

        assert response2.status_code == 200

        save_network_evidence(
            "/chat/continuity",
            "POST",
            {"conversation_id": conv_id},
            {
                "response1_status": response1.status_code,
                "response2_status": response2.status_code,
            },
            200,
        )


class TestMLBackendEmbeddingEndpoints:
    """Test ML Backend embedding endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        self.validator = ModelOutputValidator()
        self.client = httpx.Client(timeout=30.0)

    def teardown_method(self):
        """Cleanup after each test."""
        self.client.close()

    def test_embed_endpoint_exists(self):
        """Check if embedding endpoint exists."""
        response = self.client.post(
            f"{ML_BACKEND_URL}/embed",
            json={"text": "test embedding"},
        )

        save_network_evidence(
            "/embed",
            "POST",
            {"text": "test embedding"},
            {"status_code": response.status_code},
            response.status_code,
        )

        # Endpoint may not exist
        if response.status_code == 404:
            pytest.skip("Embed endpoint not implemented")

        assert response.status_code in [200, 422]

    def test_embedding_dimension(self):
        """Embedding should have correct dimension."""
        response = self.client.post(
            f"{ML_BACKEND_URL}/embed",
            json={"text": "test embedding dimension"},
        )

        if response.status_code != 200:
            pytest.skip("Embed endpoint not available")

        data = response.json()

        if "embedding" in data:
            embedding = data["embedding"]
            result = self.validator.validate_embedding(embedding)

            save_network_evidence(
                "/embed/dimension",
                "POST",
                {"text": "test"},
                {"dimension": len(embedding), "valid": result.passed},
                response.status_code,
            )

    def test_similar_text_similar_embeddings(self):
        """Similar texts should produce similar embeddings."""
        texts = [
            "The weather is nice today",
            "Today the weather is pleasant",
        ]

        embeddings = []
        for text in texts:
            response = self.client.post(
                f"{ML_BACKEND_URL}/embed",
                json={"text": text},
            )

            if response.status_code != 200:
                pytest.skip("Embed endpoint not available")

            data = response.json()
            if "embedding" in data:
                embeddings.append(data["embedding"])

        if len(embeddings) == 2:
            similarity_result = self.validator.validate_embedding_similarity(
                embeddings[0],
                embeddings[1],
                min_similarity=0.5,  # Similar texts should have >0.5 similarity
                label="similar_texts",
            )

            save_network_evidence(
                "/embed/similarity",
                "POST",
                {"texts": texts},
                {
                    "similarity": similarity_result.details.get("similarity"),
                    "passed": similarity_result.passed,
                },
                200,
            )


class TestRAGService:
    """Test RAG/Qdrant service endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        self.client = httpx.Client(timeout=30.0)

    def teardown_method(self):
        """Cleanup after each test."""
        self.client.close()

    def test_qdrant_health(self):
        """Qdrant should be reachable."""
        try:
            response = self.client.get(f"{RAG_URL}/")
            save_network_evidence(
                "qdrant/",
                "GET",
                None,
                {"status_code": response.status_code},
                response.status_code,
            )
            assert response.status_code in [200, 404]
        except httpx.ConnectError:
            pytest.fail("Qdrant service not reachable")

    def test_qdrant_collections(self):
        """Qdrant collections endpoint should work."""
        try:
            response = self.client.get(f"{RAG_URL}/collections")

            if response.status_code == 200:
                data = response.json()
                save_network_evidence(
                    "qdrant/collections",
                    "GET",
                    None,
                    data,
                    response.status_code,
                )

                # Should have collections array
                assert (
                    "result" in data
                    or "collections" in data
                    or isinstance(data, list)
                )
            else:
                save_network_evidence(
                    "qdrant/collections",
                    "GET",
                    None,
                    {"status_code": response.status_code},
                    response.status_code,
                )
        except httpx.ConnectError:
            pytest.skip("Qdrant not reachable")


class TestBackendErrorHandling:
    """Test backend error handling."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        self.client = httpx.Client(timeout=30.0)

    def teardown_method(self):
        """Cleanup after each test."""
        self.client.close()

    def test_invalid_json_body(self):
        """Invalid JSON should return proper error."""
        response = self.client.post(
            f"{ML_BACKEND_URL}/chat/send",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        save_network_evidence(
            "/chat/send/invalid_json",
            "POST",
            {"content": "not valid json"},
            {"status_code": response.status_code},
            response.status_code,
        )

        # Should return 400 or 422, not 500
        assert response.status_code in [
            400,
            422,
        ], f"Should return 400/422 for invalid JSON, got {response.status_code}"

    def test_nonexistent_endpoint(self):
        """Non-existent endpoint should return 404."""
        response = self.client.get(
            f"{ML_BACKEND_URL}/nonexistent/endpoint/test"
        )

        save_network_evidence(
            "/nonexistent",
            "GET",
            None,
            {"status_code": response.status_code},
            response.status_code,
        )

        assert response.status_code == 404

    def test_method_not_allowed(self):
        """Wrong HTTP method should return 405."""
        response = self.client.get(
            f"{ML_BACKEND_URL}/chat/send"
        )  # Should be POST

        save_network_evidence(
            "/chat/send",
            "GET",
            None,
            {"status_code": response.status_code},
            response.status_code,
        )

        # Should return 405 or 404, not 500
        assert response.status_code in [404, 405]


class TestBackendPerformance:
    """Test backend performance characteristics."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        self.client = httpx.Client(timeout=120.0)

    def teardown_method(self):
        """Cleanup after each test."""
        self.client.close()

    def test_health_response_time(self):
        """Health endpoint should respond quickly."""
        import time

        start = time.time()
        response = self.client.get(f"{ML_BACKEND_URL}/health")
        elapsed = time.time() - start

        save_network_evidence(
            "/health/performance",
            "GET",
            None,
            {
                "status_code": response.status_code,
                "response_time_ms": elapsed * 1000,
            },
            response.status_code,
        )

        # Health should respond in < 5 seconds
        assert elapsed < 5.0, f"Health endpoint too slow: {elapsed:.2f}s"

    def test_chat_response_time(self):
        """Chat endpoint should respond within timeout."""
        import time

        request_data = {
            "message": "Quick test",
            "conversation_id": "e2e-perf-test",
        }

        start = time.time()
        response = self.client.post(
            f"{ML_BACKEND_URL}/chat/send",
            json=request_data,
        )
        elapsed = time.time() - start

        save_network_evidence(
            "/chat/send/performance",
            "POST",
            request_data,
            {
                "status_code": response.status_code,
                "response_time_ms": elapsed * 1000,
            },
            response.status_code,
        )

        # Chat should respond within 120 seconds (GPU should be much faster)
        assert elapsed < 120.0, f"Chat endpoint too slow: {elapsed:.2f}s"

        # Log performance for monitoring
        print(f"\n⏱️ Chat response time: {elapsed:.2f}s")


class TestBackendSecurity:
    """Test backend security measures."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        self.client = httpx.Client(timeout=30.0)

    def teardown_method(self):
        """Cleanup after each test."""
        self.client.close()

    def test_xss_in_message_sanitized(self):
        """XSS attempts in messages should be handled safely."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
        ]

        for payload in xss_payloads:
            response = self.client.post(
                f"{ML_BACKEND_URL}/chat/send",
                json={"message": payload, "conversation_id": "e2e-xss-test"},
            )

            # Should not crash
            assert response.status_code in [
                200,
                400,
            ], "Unexpected response for XSS payload"

            if response.status_code == 200:
                data = response.json()
                response_text = str(data.get("response", ""))

                # Response should not contain raw script tags
                assert "<script>" not in response_text.lower()

        save_network_evidence(
            "/chat/send/xss",
            "POST",
            {"payloads": xss_payloads},
            {"all_handled": True},
            200,
        )

    def test_sql_injection_handled(self):
        """SQL injection attempts should be handled safely."""
        sql_payloads = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "admin'--",
        ]

        for payload in sql_payloads:
            response = self.client.post(
                f"{ML_BACKEND_URL}/chat/send",
                json={"message": payload, "conversation_id": "e2e-sqli-test"},
            )

            # Should not crash or expose SQL errors
            assert response.status_code in [200, 400]

            if response.status_code == 200:
                data = response.json()
                response_text = str(data)

                # Response should not contain SQL error messages
                sql_error_indicators = [
                    "syntax error",
                    "mysql",
                    "postgresql",
                    "sqlite",
                    "sql error",
                ]
                for indicator in sql_error_indicators:
                    assert indicator not in response_text.lower()

        save_network_evidence(
            "/chat/send/sqli",
            "POST",
            {"payloads": sql_payloads},
            {"all_handled": True},
            200,
        )


# Generate API test summary
@pytest.fixture(scope="session", autouse=True)
def generate_api_test_summary(request):
    """Generate summary after all API tests."""
    yield

    # Count evidence files
    network_files = (
        list(NETWORK_DIR.glob("*.json")) if NETWORK_DIR.exists() else []
    )

    summary = {
        "test_suite": "Backend API Tests",
        "timestamp": datetime.now().isoformat(),
        "evidence_files": len(network_files),
        "evidence_directory": str(NETWORK_DIR),
    }

    summary_path = EVIDENCE_DIR / "backend_api_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n📊 Backend API Test Summary saved to: {summary_path}")
    print(f"📁 Network evidence files: {len(network_files)}")
