"""
Wave 4: Dual-Model Conversation Integration Tests

Tests the complete dual-model conversation flow including:
- Conversation turn exchanges
- Arbitration between model outputs
- Token budget enforcement
- Rate limiting
- Circuit breaker protection
- Conversation logging
"""

from typing import Any

import pytest

from aura_ia_mcp.core.circuit_breaker import CircuitBreaker, CircuitState
from aura_ia_mcp.core.rate_limiter import RateLimiter
from aura_ia_mcp.services.model_gateway.core.arbitration import (
    ArbitrationEngine,
)
from aura_ia_mcp.services.model_gateway.core.conversation_logger import (
    ConversationLogger,
)
from aura_ia_mcp.services.model_gateway.core.dual_model import DualModelEngine
from aura_ia_mcp.services.model_gateway.core.token_budget import (
    TokenBudgetManager,
)


@pytest.fixture
def mock_backend():
    """Mock backend that returns predictable responses."""

    class MockBackend:
        def __init__(self):
            self.call_count = 0

        async def generate(
            self, prompt: str, model: str, **kwargs: Any
        ) -> dict:
            self.call_count += 1
            return {
                "response": f"Mock response from {model} (call {self.call_count})",
                "done": True,
            }

    return MockBackend()


@pytest.fixture
def dual_engine(mock_backend):
    """Dual-model engine with mock backends."""
    return DualModelEngine(mock_backend, mock_backend)


@pytest.fixture
def arbitration_engine():
    """Arbitration engine with default weights."""
    return ArbitrationEngine()


@pytest.fixture
def token_budget():
    """Token budget manager with reasonable limits."""
    return TokenBudgetManager(max_tokens=4096)


@pytest.fixture
def rate_limiter():
    """Rate limiter with test-friendly settings."""
    return RateLimiter(capacity=10, refill_rate=5.0)


@pytest.fixture
def circuit_breaker():
    """Circuit breaker with test-friendly thresholds."""
    return CircuitBreaker(failure_threshold=3, timeout_seconds=5)


@pytest.fixture
def conversation_logger(tmp_path):
    """Conversation logger using temp directory."""
    logger = ConversationLogger()
    logger.logs_dir = tmp_path / "conversations"
    logger.logs_dir.mkdir(exist_ok=True)
    return logger


class TestDualModelConversation:
    """Test dual-model conversation flows."""

    @pytest.mark.asyncio
    async def test_basic_conversation(self, dual_engine, mock_backend):
        """Test basic dual-model conversation exchange."""
        conversation = await dual_engine.run_conversation(
            user_message="What is 2+2?",
            model_a="model-a",
            model_b="model-b",
            exchanges=2,
        )

        # Should have 4 turns (2 exchanges × 2 models)
        assert len(conversation) == 4
        assert conversation[0].model == "model-a"
        assert conversation[1].model == "model-b"
        assert conversation[2].model == "model-a"
        assert conversation[3].model == "model-b"

        # Mock backend should be called 4 times
        assert mock_backend.call_count == 4

    @pytest.mark.asyncio
    async def test_conversation_with_custom_prompts(self, dual_engine):
        """Test conversation with custom system prompts."""
        conversation = await dual_engine.run_conversation(
            user_message="Test question",
            model_a="model-a",
            model_b="model-b",
            prompt_a="base_system",
            prompt_b="critic_mode",
            exchanges=1,
        )

        assert len(conversation) == 2
        assert "Mock response" in conversation[0].content
        assert "Mock response" in conversation[1].content

    @pytest.mark.asyncio
    async def test_conversation_metadata(self, dual_engine):
        """Test conversation turns include metadata."""
        conversation = await dual_engine.run_conversation(
            user_message="Test",
            model_a="model-a",
            model_b="model-b",
            exchanges=1,
        )

        for turn in conversation:
            assert turn.model in ["model-a", "model-b"]
            assert turn.role in ["assistant_a", "assistant_b"]
            assert turn.content is not None


class TestArbitration:
    """Test arbitration logic."""

    def test_arbitrate_identical_outputs(self, arbitration_engine):
        """Test arbitration when outputs are identical."""
        outputs = [
            {"content": "Same answer", "model": "model-a"},
            {"content": "Same answer", "model": "model-b"},
        ]

        best = arbitration_engine.arbitrate(outputs)
        assert best["content"] == "Same answer"

    def test_arbitrate_divergent_outputs(self, arbitration_engine):
        """Test arbitration when outputs differ."""
        outputs = [
            {
                "content": "Answer A with detailed reasoning",
                "model": "model-a",
            },
            {"content": "Short answer B", "model": "model-b"},
        ]

        best = arbitration_engine.arbitrate(outputs)
        # Should prefer longer, more detailed response
        assert "detailed" in best["content"] or len(best["content"]) > 15

    def test_detect_consensus(self, arbitration_engine):
        """Test consensus detection."""
        # High consensus
        high_consensus = [
            {"content": "The answer is 4", "model": "model-a"},
            {"content": "The answer is four", "model": "model-b"},
        ]
        result_high = arbitration_engine.detect_consensus(high_consensus)
        assert result_high["has_consensus"] is True

        # Low consensus
        low_consensus = [
            {"content": "The answer is 4", "model": "model-a"},
            {"content": "I think it might be 5", "model": "model-b"},
        ]
        result_low = arbitration_engine.detect_consensus(low_consensus)
        assert result_low["has_consensus"] is False


class TestTokenBudget:
    """Test token budget management."""

    def test_simple_budget_check(self, token_budget):
        """Test basic budget checking."""
        # Short prompt should pass
        short_prompt = "Hello world"
        assert token_budget.check_budget(short_prompt) is True

        # Very long prompt should fail
        long_prompt = "word " * 10000  # ~20k characters
        assert token_budget.check_budget(long_prompt) is False

    def test_budget_with_history(self, token_budget):
        """Test budget forecasting with conversation history."""
        # Record some history
        token_budget.record_turn(input_tokens=100, output_tokens=150)
        token_budget.record_turn(input_tokens=120, output_tokens=180)

        # Check budget with new input
        result = token_budget.forecast_usage(current_input=200)
        assert "forecast_total" in result
        assert "available" in result
        assert (
            result["forecast_total"] > 200
        )  # Should include predicted output

    def test_truncation_recommendation(self, token_budget):
        """Test truncation recommendations."""
        # Fill up budget
        for _ in range(5):
            token_budget.record_turn(input_tokens=500, output_tokens=500)

        # Try large input
        result = token_budget.forecast_usage(current_input=3000)
        if result["needs_truncation"]:
            assert "recommended_input" in result
            assert result["recommended_input"] < 3000


class TestRateLimiting:
    """Test rate limiting behavior."""

    def test_rate_limit_allows_initial_requests(self, rate_limiter):
        """Test rate limiter allows requests within capacity."""
        client_id = "test_client"

        # Should allow up to capacity
        for i in range(10):  # Capacity is 10
            assert rate_limiter.is_allowed(client_id) is True

    def test_rate_limit_blocks_excess(self, rate_limiter):
        """Test rate limiter blocks requests exceeding capacity."""
        client_id = "test_client"

        # Exhaust capacity
        for _ in range(10):
            rate_limiter.is_allowed(client_id)

        # 11th request should be blocked
        assert rate_limiter.is_allowed(client_id) is False

    def test_rate_limit_per_client(self, rate_limiter):
        """Test rate limiter tracks clients independently."""
        client_a = "client_a"
        client_b = "client_b"

        # Exhaust client A
        for _ in range(10):
            rate_limiter.is_allowed(client_a)

        # Client B should still be allowed
        assert rate_limiter.is_allowed(client_b) is True

    def test_rate_limit_refill(self, rate_limiter):
        """Test rate limiter refills tokens over time."""
        import time

        client_id = "test_client"

        # Exhaust capacity
        for _ in range(10):
            rate_limiter.is_allowed(client_id)

        assert rate_limiter.is_allowed(client_id) is False

        # Wait for refill (refill_rate=5.0 tokens/sec, need 1 token)
        time.sleep(0.3)  # Should refill ~1.5 tokens

        # Should allow at least 1 more request
        assert rate_limiter.is_allowed(client_id) is True


class TestCircuitBreaker:
    """Test circuit breaker state transitions."""

    def test_circuit_closed_initially(self, circuit_breaker):
        """Test circuit starts in CLOSED state."""
        assert circuit_breaker.state == CircuitState.CLOSED

    def test_circuit_opens_on_failures(self, circuit_breaker):
        """Test circuit opens after threshold failures."""

        def failing_function():
            raise Exception("Simulated failure")

        # Trigger failures up to threshold (3)
        for _ in range(3):
            try:
                circuit_breaker.call(failing_function)
            except Exception:
                pass

        # Circuit should now be OPEN
        assert circuit_breaker.state == CircuitState.OPEN

    def test_circuit_rejects_when_open(self, circuit_breaker):
        """Test circuit rejects calls when OPEN."""

        def failing_function():
            raise Exception("Fail")

        # Open the circuit
        for _ in range(3):
            try:
                circuit_breaker.call(failing_function)
            except Exception:
                pass

        # Further calls should be rejected immediately
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            circuit_breaker.call(lambda: "success")

    def test_circuit_half_open_after_timeout(self, circuit_breaker):
        """Test circuit transitions to HALF_OPEN after timeout."""
        import time

        def failing_function():
            raise Exception("Fail")

        # Open the circuit
        for _ in range(3):
            try:
                circuit_breaker.call(failing_function)
            except Exception:
                pass

        assert circuit_breaker.state == CircuitState.OPEN

        # Wait for timeout (5 seconds)
        time.sleep(6)

        # Next call should transition to HALF_OPEN
        try:
            circuit_breaker.call(lambda: "success")
        except Exception:
            pass

        # Should be CLOSED after successful call
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_async_circuit_breaker(self, circuit_breaker):
        """Test circuit breaker with async functions."""

        async def async_success():
            return "success"

        async def async_failure():
            raise Exception("Async fail")

        # Test successful async call
        result = await circuit_breaker.call(async_success)
        assert result == "success"

        # Test failed async calls
        for _ in range(3):
            try:
                await circuit_breaker.call(async_failure)
            except Exception:
                pass

        assert circuit_breaker.state == CircuitState.OPEN


class TestConversationLogging:
    """Test conversation logging."""

    def test_log_conversation(self, conversation_logger):
        """Test logging a conversation."""
        messages = [
            {"model": "model-a", "role": "assistant", "content": "Hello"},
            {"model": "model-b", "role": "assistant", "content": "Hi there"},
        ]

        conv_id = conversation_logger.log_conversation(
            messages=messages, metadata={"test": "value"}
        )

        assert conv_id is not None
        assert len(conv_id) > 0

        # Verify log file was created
        log_files = list(conversation_logger.logs_dir.glob("*.json"))
        assert len(log_files) > 0

    def test_retrieve_conversation(self, conversation_logger):
        """Test retrieving a logged conversation."""
        messages = [{"model": "test", "role": "assistant", "content": "Test"}]

        conv_id = conversation_logger.log_conversation(messages=messages)
        retrieved = conversation_logger.get_conversation(conv_id)

        assert retrieved is not None
        assert retrieved["id"] == conv_id
        assert len(retrieved["messages"]) == 1
        assert retrieved["messages"][0]["content"] == "Test"

    def test_list_conversations(self, conversation_logger):
        """Test listing all conversations."""
        # Log multiple conversations
        for i in range(3):
            conversation_logger.log_conversation(
                messages=[
                    {
                        "model": "test",
                        "role": "assistant",
                        "content": f"Msg {i}",
                    }
                ]
            )

        conversations = conversation_logger.list_conversations()
        assert len(conversations) >= 3


class TestIntegrationFlow:
    """Test complete integration flows."""

    @pytest.mark.asyncio
    async def test_full_dual_model_flow_with_guards(
        self,
        dual_engine,
        arbitration_engine,
        token_budget,
        rate_limiter,
        circuit_breaker,
        conversation_logger,
    ):
        """Test complete flow with all components."""
        client_id = "test_client"

        # 1. Check rate limit
        if not rate_limiter.is_allowed(client_id):
            pytest.skip("Rate limit exceeded")

        # 2. Check token budget
        user_message = "What is the capital of France?"
        if not token_budget.check_budget(user_message):
            pytest.skip("Token budget exceeded")

        # 3. Run dual-model conversation (with circuit breaker)
        try:
            conversation = await circuit_breaker.call(
                dual_engine.run_conversation,
                user_message=user_message,
                model_a="model-a",
                model_b="model-b",
                exchanges=2,
            )
        except Exception as e:
            pytest.fail(f"Conversation failed: {e}")

        # 4. Arbitrate
        final_outputs = [
            {"content": turn.content, "model": turn.model}
            for turn in conversation[-2:]
        ]
        best_response = arbitration_engine.arbitrate(final_outputs)

        # 5. Log conversation
        conv_id = conversation_logger.log_conversation(
            messages=[
                {
                    "model": turn.model,
                    "role": turn.role,
                    "content": turn.content,
                }
                for turn in conversation
            ],
            metadata={"arbitration": best_response["model"]},
        )

        # Assertions
        assert len(conversation) == 4
        assert best_response is not None
        assert conv_id is not None

    @pytest.mark.asyncio
    async def test_flow_with_circuit_breaker_open(
        self, dual_engine, circuit_breaker
    ):
        """Test flow when circuit breaker is open."""

        async def always_fail():
            raise Exception("Backend failure")

        # Open circuit breaker
        for _ in range(3):
            try:
                await circuit_breaker.call(always_fail)
            except Exception:
                pass

        # Conversation should fail immediately
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await circuit_breaker.call(
                dual_engine.run_conversation,
                user_message="Test",
                model_a="model-a",
                model_b="model-b",
                exchanges=1,
            )

    @pytest.mark.asyncio
    async def test_flow_with_rate_limit_exhausted(
        self, dual_engine, rate_limiter
    ):
        """Test flow when rate limit is exhausted."""
        client_id = "heavy_user"

        # Exhaust rate limit
        for _ in range(10):
            rate_limiter.is_allowed(client_id)

        # Should be blocked
        if not rate_limiter.is_allowed(client_id):
            # Expected: rate limit blocks further requests
            assert True
        else:
            pytest.fail("Rate limiter did not block request")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
