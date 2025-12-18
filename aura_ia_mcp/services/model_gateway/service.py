from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import BaseModel

from ...core.circuit_breaker import CircuitBreaker
from ...core.rate_limiter import RateLimiter
from .adapters.ollama import OllamaBackend
from .chat_router import ChatRequest, get_chat_router, route_message
from .core.conversation_logger import ConversationLogger
from .core.token_budget import TokenBudgetManager
from .lifecycle import ChatMode, get_model_manager, model_manager

router = APIRouter(prefix="/v1")

# Initialize backend and managers
backend = OllamaBackend()
budget_manager = TokenBudgetManager()
rate_limiter = RateLimiter(capacity=100, refill_rate=10.0)
circuit_breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
conversation_logger = ConversationLogger()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = 0.7
    max_tokens: int | None = None


@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest, req: Request):
    """OpenAI-compatible chat completions endpoint with reliability features."""

    # 0. Rate Limiting
    client_id = req.client.host if req.client else "unknown"
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # 1. Check Token Budget
    full_prompt = "\n".join([m.content for m in request.messages])
    if not budget_manager.check_budget(full_prompt):
        raise HTTPException(status_code=400, detail="Token budget exceeded")

    # 2. Generate Response (with circuit breaker)
    try:
        prompt = full_prompt

        # Use circuit breaker to protect against backend failures
        response = await circuit_breaker.call(
            backend.generate,
            prompt=prompt,
            model=request.model,
            options={
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        )

        # 3. Format Response (OpenAI style)
        response_data = {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": 1234567890,
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response.get("response", ""),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

        # 4. Log Conversation
        conversation_logger.log_conversation(
            messages=[
                *[
                    {"role": m.role, "content": m.content}
                    for m in request.messages
                ],
                {"role": "assistant", "content": response.get("response", "")},
            ],
            metadata={
                "model": request.model,
                "client_id": client_id,
                "endpoint": "/v1/chat/completions",
            },
        )

        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/health")
async def health_check():
    """Check gateway health."""
    is_healthy = await backend.health()
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "backend": "ollama",
    }


@router.post("/chat/dual")
async def dual_chat(request: dict, req: Request):
    """
    Dual-model conversation endpoint.

    Request body:
        user_message: str - Initial user message
        model_a: str - First model name
        model_b: str - Second model name
        prompt_a: str - System prompt for model A (default: base_system)
        prompt_b: str - System prompt for model B (default: critic_mode)
        exchanges: int - Number of exchanges (default: 2)
    """
    from .core.arbitration import ArbitrationEngine
    from .core.dual_model import DualModelEngine

    # Rate limiting
    client_id = req.client.host if req.client else "unknown"
    if not rate_limiter.is_allowed(client_id, tokens=2):  # Dual model costs 2x
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Extract parameters
    user_message = request.get("user_message")
    model_a = request.get("model_a", "llama3")
    model_b = request.get("model_b", "llama3")
    prompt_a = request.get("prompt_a", "base_system")
    prompt_b = request.get("prompt_b", "critic_mode")
    exchanges = request.get("exchanges", 2)

    if not user_message:
        raise HTTPException(status_code=400, detail="user_message is required")

    # Initialize dual model engine
    dual_engine = DualModelEngine(
        backend, backend
    )  # Same backend, different models
    arbitration = ArbitrationEngine()

    try:
        # Run dual-model conversation
        conversation = await dual_engine.run_conversation(
            user_message=user_message,
            model_a=model_a,
            model_b=model_b,
            prompt_a=prompt_a,
            prompt_b=prompt_b,
            exchanges=exchanges,
        )

        # Arbitrate between final outputs
        final_outputs = [
            {"content": turn.content, "model": turn.model}
            for turn in conversation[-2:]  # Last two turns
        ]

        best_response = arbitration.arbitrate(final_outputs)
        consensus = arbitration.detect_consensus(final_outputs)

        # Log dual-model conversation
        conv_id = conversation_logger.log_conversation(
            messages=[
                {
                    "model": turn.model,
                    "role": turn.role,
                    "content": turn.content,
                    "metadata": turn.metadata,
                }
                for turn in conversation
            ],
            metadata={
                "model_a": model_a,
                "model_b": model_b,
                "exchanges": exchanges,
                "client_id": client_id,
                "endpoint": "/v1/chat/dual",
                "consensus": consensus,
            },
        )

        return {
            "conversation_id": conv_id,
            "conversation": [
                {
                    "model": turn.model,
                    "role": turn.role,
                    "content": turn.content,
                    "metadata": turn.metadata,
                }
                for turn in conversation
            ],
            "best_response": best_response,
            "consensus_detected": consensus,
            "metadata": {
                "model_a": model_a,
                "model_b": model_b,
                "exchanges": exchanges,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Retrieve a conversation by ID."""
    conversation = conversation_logger.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/conversations")
async def list_conversations(limit: int = 100, offset: int = 0):
    """List recent conversations."""
    return {
        "conversations": conversation_logger.list_conversations(limit, offset),
        "limit": limit,
        "offset": offset,
    }


# =============================================================================
# Model Lifecycle Management Endpoints
# =============================================================================


class SmartChatRequest(BaseModel):
    """Request for smart-routed chat."""

    message: str
    user_id: str = "default"
    mode: Optional[str] = None  # chat, concierge, mcp_command, debug, debate
    model: Optional[str] = None  # explicit model override
    temperature: float = 0.7
    max_tokens: Optional[int] = None


@router.post("/chat/smart")
async def smart_chat(request: SmartChatRequest, req: Request):
    """
    Smart chat endpoint with automatic model routing.

    Routes messages to optimal models based on:
    - Intent detection (MCP command, debug, concierge, chat)
    - Model availability and load state
    - Automatic fallback if primary model unavailable
    """
    # Rate limiting
    client_id = req.client.host if req.client else "unknown"
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Route the message
    routing = await route_message(
        message=request.message,
        user_id=request.user_id,
        mode=request.mode,
        model=request.model,
    )

    # Token budget check
    if not budget_manager.check_budget(request.message):
        raise HTTPException(status_code=400, detail="Token budget exceeded")

    # Generate response
    try:
        response = await circuit_breaker.call(
            backend.generate,
            prompt=request.message,
            model=routing.model,
            options={
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        )

        # Format response
        response_data = {
            "id": "smartchat-" + str(hash(request.message))[:8],
            "object": "chat.completion",
            "model": routing.model,
            "mode": routing.mode.value,
            "routing": {
                "detected_mode": routing.mode.value,
                "model_used": routing.model,
                "confidence": routing.confidence,
                "reasoning": routing.reasoning,
                "is_fallback": routing.is_fallback,
                "detected_keywords": routing.detected_keywords,
            },
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response.get("response", ""),
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        # Log conversation
        conversation_logger.log_conversation(
            messages=[
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": response.get("response", "")},
            ],
            metadata={
                "model": routing.model,
                "mode": routing.mode.value,
                "client_id": client_id,
                "endpoint": "/v1/chat/smart",
                "routing_confidence": routing.confidence,
                "is_fallback": routing.is_fallback,
            },
        )

        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/models/status")
async def get_model_status():
    """Get current model loading status and lifecycle info."""
    manager = await get_model_manager()
    return await manager.get_status()


@router.get("/models/health")
async def get_models_health():
    """Health check for Ollama service and loaded models."""
    manager = await get_model_manager()
    return await manager.health_check()


@router.post("/models/{model_name}/load")
async def load_model(model_name: str):
    """Manually load a specific model."""
    manager = await get_model_manager()
    success = await manager.ensure_loaded(model_name)
    if success:
        return {"status": "loaded", "model": model_name}
    raise HTTPException(
        status_code=503, detail=f"Failed to load model {model_name}"
    )


@router.post("/models/{model_name}/unload")
async def unload_model(model_name: str):
    """Manually unload a specific model."""
    manager = await get_model_manager()

    # Check if it's always-loaded
    from .lifecycle import MODEL_CONFIGS

    config = MODEL_CONFIGS.get(model_name)
    if config and config.always_loaded:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot unload always-loaded model {model_name}",
        )

    await manager._offload_model(model_name)
    return {"status": "unloaded", "model": model_name}


@router.get("/router/stats")
async def get_router_stats():
    """Get chat router statistics."""
    router_instance = await get_chat_router()
    return router_instance.get_routing_stats()


@router.post("/router/detect-mode")
async def detect_chat_mode(message: str):
    """Detect the chat mode for a message without executing."""
    router_instance = await get_chat_router()
    mode, confidence, reasoning, keywords = router_instance.detect_mode(
        message
    )
    return {
        "message": message,
        "detected_mode": mode.value,
        "confidence": confidence,
        "reasoning": reasoning,
        "keywords": keywords,
    }


def register(app: FastAPI, settings) -> None:
    app.include_router(router)

    @app.on_event("startup")
    async def startup_model_lifecycle():
        """Initialize model lifecycle manager on startup."""
        import logging

        logger = logging.getLogger(__name__)
        try:
            manager = await get_model_manager()
            logger.info("✅ Model Lifecycle Manager started")
            health = await manager.health_check()
            logger.info(f"   Ollama status: {health.get('status', 'unknown')}")
        except Exception as e:
            logger.warning(f"⚠️ Model Lifecycle Manager startup warning: {e}")

    @app.on_event("shutdown")
    async def shutdown_model_lifecycle():
        """Cleanup model lifecycle manager on shutdown."""
        import logging

        logger = logging.getLogger(__name__)
        try:
            await model_manager.stop()
            logger.info("✅ Model Lifecycle Manager stopped")
        except Exception as e:
            logger.warning(f"⚠️ Model Lifecycle Manager shutdown warning: {e}")
