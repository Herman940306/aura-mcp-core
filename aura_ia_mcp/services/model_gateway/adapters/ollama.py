"""
Ollama Backend Implementation with Enterprise Reliability Features.

This module provides async Ollama integration with:
- Token Budget Management with per-user tracking
- Automatic Model Selection based on task requirements
- Context Window Management with overflow handling
- Error Recovery with retry logic, circuit breaker, and graceful degradation
- Performance Monitoring with latency tracking and throughput metrics
- Security Validation for input/output sanitization

PRD Reference: Section 8.13 (Ollama Agent Integration)
"""

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx

from .base import BaseModelBackend

HTTP_OK = 200
logger = logging.getLogger(__name__)


# =============================================================================
# Token Budget Management
# =============================================================================


@dataclass
class ModelCost:
    """Cost configuration for a model."""

    input_cost_per_1k: float = 0.0  # Cost per 1000 input tokens
    output_cost_per_1k: float = 0.0  # Cost per 1000 output tokens
    context_window: int = 4096  # Max context window size


MODEL_COSTS: dict[str, ModelCost] = {
    "llama3": ModelCost(0.0, 0.0, 8192),
    "llama3.1": ModelCost(0.0, 0.0, 131072),
    "llama3.2": ModelCost(0.0, 0.0, 131072),
    "mistral": ModelCost(0.0, 0.0, 32768),
    "mixtral": ModelCost(0.0, 0.0, 32768),
    "codellama": ModelCost(0.0, 0.0, 16384),
    "qwen2.5-coder": ModelCost(0.0, 0.0, 131072),
    "deepseek-coder-v2": ModelCost(0.0, 0.0, 131072),
    "phi3": ModelCost(0.0, 0.0, 128000),
    "gemma2": ModelCost(0.0, 0.0, 8192),
    "default": ModelCost(0.0, 0.0, 4096),
}


class OllamaTokenBudgetManager:
    """Enhanced token budget manager with per-user tracking and model awareness."""

    def __init__(self, default_budget: int = 100000):
        self.default_budget = default_budget
        self.user_budgets: dict[str, int] = defaultdict(lambda: default_budget)
        self.user_usage: dict[str, dict[str, int]] = defaultdict(
            lambda: {"input": 0, "output": 0, "total": 0}
        )
        self.model_costs = MODEL_COSTS
        self.history: list[tuple[str, int, int, str]] = (
            []
        )  # (user_id, input, output, model)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (4 chars/token approximation)."""
        return max(1, (len(text) + 3) // 4)

    def get_model_context_limit(self, model: str) -> int:
        """Get context window size for a model."""
        cost = self.model_costs.get(model, self.model_costs["default"])
        return cost.context_window

    def check_budget(
        self,
        user_id: str,
        prompt: str,
        model: str,
        max_new_tokens: int = 512,
    ) -> tuple[bool, str]:
        """Check if user has budget for this request."""
        input_tokens = self.estimate_tokens(prompt)
        context_limit = self.get_model_context_limit(model)

        # Check context window
        if (input_tokens + max_new_tokens) > context_limit:
            return (
                False,
                f"Request exceeds model context window ({context_limit} tokens)",
            )

        # Check user budget
        current_usage = self.user_usage[user_id]["total"]
        remaining = self.user_budgets[user_id] - current_usage

        if (input_tokens + max_new_tokens) > remaining:
            return (
                False,
                f"User budget exceeded. Remaining: {remaining} tokens",
            )

        return True, "OK"

    def record_usage(
        self,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
    ) -> None:
        """Record token usage for a user."""
        self.user_usage[user_id]["input"] += input_tokens
        self.user_usage[user_id]["output"] += output_tokens
        self.user_usage[user_id]["total"] += input_tokens + output_tokens
        self.history.append((user_id, input_tokens, output_tokens, model))

        # Cap history to last 1000 entries
        if len(self.history) > 1000:
            self.history = self.history[-1000:]

    def get_user_stats(self, user_id: str) -> dict[str, Any]:
        """Get usage statistics for a user."""
        return {
            "user_id": user_id,
            "budget": self.user_budgets[user_id],
            "used": self.user_usage[user_id]["total"],
            "remaining": self.user_budgets[user_id]
            - self.user_usage[user_id]["total"],
            "input_tokens": self.user_usage[user_id]["input"],
            "output_tokens": self.user_usage[user_id]["output"],
        }

    def reset_user_budget(
        self, user_id: str, new_budget: Optional[int] = None
    ) -> None:
        """Reset a user's budget."""
        self.user_budgets[user_id] = new_budget or self.default_budget
        self.user_usage[user_id] = {"input": 0, "output": 0, "total": 0}


# =============================================================================
# Model Selection
# =============================================================================


class TaskType(Enum):
    """Task types for model selection."""

    GENERAL = "general"
    CODE = "code"
    MATH = "math"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    CONVERSATION = "conversation"


MODEL_CAPABILITIES: dict[str, list[TaskType]] = {
    "llama3": [TaskType.GENERAL, TaskType.CONVERSATION, TaskType.ANALYSIS],
    "llama3.1": [
        TaskType.GENERAL,
        TaskType.CONVERSATION,
        TaskType.ANALYSIS,
        TaskType.CODE,
    ],
    "llama3.2": [
        TaskType.GENERAL,
        TaskType.CONVERSATION,
        TaskType.ANALYSIS,
        TaskType.CODE,
    ],
    "codellama": [TaskType.CODE],
    "qwen2.5-coder": [TaskType.CODE, TaskType.MATH],
    "deepseek-coder-v2": [TaskType.CODE, TaskType.MATH, TaskType.ANALYSIS],
    "mistral": [TaskType.GENERAL, TaskType.CONVERSATION],
    "mixtral": [TaskType.GENERAL, TaskType.CODE, TaskType.ANALYSIS],
    "phi3": [TaskType.GENERAL, TaskType.CODE, TaskType.MATH],
    "gemma2": [TaskType.GENERAL, TaskType.CREATIVE, TaskType.CONVERSATION],
}


class OllamaModelSelector:
    """Automatic model selection based on task requirements."""

    def __init__(self, available_models: Optional[list[str]] = None):
        self.available_models = available_models or []
        self.model_capabilities = MODEL_CAPABILITIES
        self.model_performance: dict[str, dict[str, float]] = defaultdict(
            lambda: {"latency": 0.0, "success_rate": 1.0, "quality": 0.5}
        )

    def update_available_models(self, models: list[str]) -> None:
        """Update list of available models."""
        self.available_models = models

    def select_model(
        self,
        task_type: TaskType = TaskType.GENERAL,
        prefer_speed: bool = False,
        prefer_quality: bool = False,
        max_context_needed: int = 4096,
    ) -> str:
        """Select best model for the task."""
        candidates = []

        for model in self.available_models:
            # Check if model supports task type
            caps = self.model_capabilities.get(model, [TaskType.GENERAL])
            if task_type in caps or TaskType.GENERAL in caps:
                # Check context window
                context_limit = MODEL_COSTS.get(
                    model, MODEL_COSTS["default"]
                ).context_window
                if context_limit >= max_context_needed:
                    candidates.append(model)

        if not candidates:
            # Fallback to first available or default
            return (
                self.available_models[0] if self.available_models else "llama3"
            )

        # Score candidates
        scored = []
        for model in candidates:
            perf = self.model_performance[model]
            score = perf["success_rate"] * 0.4

            if prefer_speed:
                # Lower latency = higher score
                score += (1.0 - min(perf["latency"] / 10.0, 1.0)) * 0.4
            elif prefer_quality:
                score += perf["quality"] * 0.4
            else:
                score += 0.2 * (1.0 - min(perf["latency"] / 10.0, 1.0))
                score += 0.2 * perf["quality"]

            scored.append((model, score))

        # Return highest scored
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def record_performance(
        self,
        model: str,
        latency: float,
        success: bool,
        quality_score: Optional[float] = None,
    ) -> None:
        """Record model performance metrics."""
        perf = self.model_performance[model]

        # Exponential moving average for latency
        alpha = 0.2
        perf["latency"] = alpha * latency + (1 - alpha) * perf["latency"]

        # Update success rate
        perf["success_rate"] = (
            alpha * (1.0 if success else 0.0)
            + (1 - alpha) * perf["success_rate"]
        )

        # Update quality if provided
        if quality_score is not None:
            perf["quality"] = (
                alpha * quality_score + (1 - alpha) * perf["quality"]
            )


# =============================================================================
# Context Management
# =============================================================================


class OllamaContextManager:
    """Context window management with overflow handling."""

    def __init__(self, default_context_limit: int = 4096):
        self.default_context_limit = default_context_limit
        self.conversation_contexts: dict[str, list[dict[str, str]]] = {}

    def get_context_limit(self, model: str) -> int:
        """Get context limit for a model."""
        return MODEL_COSTS.get(model, MODEL_COSTS["default"]).context_window

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model: str,
    ) -> None:
        """Add a message to conversation context."""
        if conversation_id not in self.conversation_contexts:
            self.conversation_contexts[conversation_id] = []

        self.conversation_contexts[conversation_id].append(
            {
                "role": role,
                "content": content,
            }
        )

        # Prune if over limit
        self._prune_context(conversation_id, model)

    def get_context(
        self,
        conversation_id: str,
        model: str,
        max_tokens: Optional[int] = None,
    ) -> list[dict[str, str]]:
        """Get conversation context within token limits."""
        if conversation_id not in self.conversation_contexts:
            return []

        context = self.conversation_contexts[conversation_id]
        limit = max_tokens or self.get_context_limit(model)

        # Estimate tokens and truncate from oldest
        total_tokens = 0
        result = []

        for msg in reversed(context):
            msg_tokens = (len(msg["content"]) + 3) // 4
            if (
                total_tokens + msg_tokens > limit * 0.8
            ):  # Leave 20% for response
                break
            result.insert(0, msg)
            total_tokens += msg_tokens

        return result

    def _prune_context(self, conversation_id: str, model: str) -> None:
        """Prune context to fit within limits."""
        context = self.conversation_contexts[conversation_id]
        limit = self.get_context_limit(model)

        total_tokens = sum((len(msg["content"]) + 3) // 4 for msg in context)

        # Remove oldest messages until under 70% of limit
        while total_tokens > limit * 0.7 and len(context) > 1:
            removed = context.pop(0)
            total_tokens -= (len(removed["content"]) + 3) // 4

    def clear_context(self, conversation_id: str) -> None:
        """Clear conversation context."""
        if conversation_id in self.conversation_contexts:
            del self.conversation_contexts[conversation_id]

    def summarize_context(
        self,
        conversation_id: str,
        summarizer_func: Optional[Any] = None,
    ) -> str:
        """Summarize context to reduce token usage."""
        if conversation_id not in self.conversation_contexts:
            return ""

        context = self.conversation_contexts[conversation_id]
        if not context:
            return ""

        # Simple summary: concatenate first and last messages
        summary_parts = []
        if len(context) > 0:
            summary_parts.append(f"First: {context[0]['content'][:200]}")
        if len(context) > 2:
            summary_parts.append(f"... ({len(context) - 2} messages) ...")
        if len(context) > 1:
            summary_parts.append(f"Last: {context[-1]['content'][:200]}")

        return "\n".join(summary_parts)


# =============================================================================
# Error Recovery
# =============================================================================


class OllamaCircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class OllamaErrorRecovery:
    """Error recovery with retry logic, circuit breaker, and graceful degradation."""

    failure_threshold: int = 5
    timeout_seconds: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_multiplier: float = 2.0

    failure_count: int = field(default=0, init=False)
    last_failure_time: Optional[float] = field(default=None, init=False)
    state: OllamaCircuitState = field(
        default=OllamaCircuitState.CLOSED, init=False
    )
    consecutive_successes: int = field(default=0, init=False)

    def is_available(self) -> tuple[bool, str]:
        """Check if the circuit is available for requests."""
        if self.state == OllamaCircuitState.CLOSED:
            return True, "OK"

        if self.state == OllamaCircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = OllamaCircuitState.HALF_OPEN
                return True, "Testing recovery"
            return False, f"Circuit OPEN. Retry after {self.timeout_seconds}s"

        # HALF_OPEN - allow limited requests
        return True, "Testing recovery"

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return False
        return (time.time() - self.last_failure_time) >= self.timeout_seconds

    def record_success(self) -> None:
        """Record successful call."""
        self.consecutive_successes += 1
        if (
            self.state == OllamaCircuitState.HALF_OPEN
            and self.consecutive_successes >= 3
        ):
            self.state = OllamaCircuitState.CLOSED
            self.failure_count = 0
            self.consecutive_successes = 0
            logger.info("Ollama circuit breaker CLOSED (recovered)")

    def record_failure(self, error: str) -> None:
        """Record failed call."""
        self.failure_count += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = OllamaCircuitState.OPEN
            logger.warning(
                f"Ollama circuit breaker OPEN after {self.failure_count} failures: {error}"
            )

    async def execute_with_retry(
        self,
        func,
        *args,
        **kwargs,
    ) -> tuple[bool, Any, str]:
        """Execute function with retry logic."""
        available, reason = self.is_available()
        if not available:
            return False, None, reason

        last_error = ""
        delay = self.retry_delay

        for attempt in range(self.max_retries):
            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return True, result, "OK"
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Ollama attempt {attempt + 1}/{self.max_retries} failed: {last_error}"
                )

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= self.backoff_multiplier

        self.record_failure(last_error)
        return (
            False,
            None,
            f"All {self.max_retries} retries failed: {last_error}",
        )


# =============================================================================
# Performance Monitoring
# =============================================================================


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    model: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    success: bool
    timestamp: float = field(default_factory=time.time)


class OllamaPerformanceMonitor:
    """Performance monitoring with latency tracking and throughput metrics."""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics: list[RequestMetrics] = []
        self.model_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "total_requests": 0,
                "successful_requests": 0,
                "total_latency_ms": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            }
        )

    def record_request(
        self,
        model: str,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        success: bool,
    ) -> None:
        """Record request metrics."""
        metric = RequestMetrics(
            model=model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=success,
        )
        self.metrics.append(metric)

        # Update model stats
        stats = self.model_stats[model]
        stats["total_requests"] += 1
        if success:
            stats["successful_requests"] += 1
        stats["total_latency_ms"] += latency_ms
        stats["total_input_tokens"] += input_tokens
        stats["total_output_tokens"] += output_tokens

        # Prune old metrics
        if len(self.metrics) > self.window_size:
            self.metrics = self.metrics[-self.window_size :]

    def get_stats(self, model: Optional[str] = None) -> dict[str, Any]:
        """Get performance statistics."""
        if model:
            stats = self.model_stats[model]
            total = stats["total_requests"]
            if total == 0:
                return {"model": model, "requests": 0}
            return {
                "model": model,
                "requests": total,
                "success_rate": stats["successful_requests"] / total,
                "avg_latency_ms": stats["total_latency_ms"] / total,
                "total_input_tokens": stats["total_input_tokens"],
                "total_output_tokens": stats["total_output_tokens"],
                "tokens_per_second": (
                    (
                        stats["total_input_tokens"]
                        + stats["total_output_tokens"]
                    )
                    / (stats["total_latency_ms"] / 1000)
                    if stats["total_latency_ms"] > 0
                    else 0
                ),
            }

        # Aggregate all models
        all_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "total_latency_ms": 0.0,
            "models": {},
        }
        for m, s in self.model_stats.items():
            all_stats["total_requests"] += s["total_requests"]
            all_stats["successful_requests"] += s["successful_requests"]
            all_stats["total_latency_ms"] += s["total_latency_ms"]
            all_stats["models"][m] = self.get_stats(m)

        if all_stats["total_requests"] > 0:
            all_stats["success_rate"] = (
                all_stats["successful_requests"] / all_stats["total_requests"]
            )
            all_stats["avg_latency_ms"] = (
                all_stats["total_latency_ms"] / all_stats["total_requests"]
            )
        else:
            all_stats["success_rate"] = 0.0
            all_stats["avg_latency_ms"] = 0.0

        return all_stats

    def get_recent_latencies(
        self, model: Optional[str] = None, count: int = 100
    ) -> list[float]:
        """Get recent latency measurements."""
        recent = (
            self.metrics[-count:]
            if len(self.metrics) >= count
            else self.metrics
        )
        if model:
            return [m.latency_ms for m in recent if m.model == model]
        return [m.latency_ms for m in recent]


# =============================================================================
# Security Manager
# =============================================================================


class OllamaSecurityManager:
    """Security validation for input/output sanitization."""

    def __init__(self):
        self.blocked_patterns: list[str] = [
            "ignore previous",
            "ignore all",
            "disregard",
            "system prompt",
            "jailbreak",
            "DAN mode",
        ]
        self.max_input_length = 100000  # Max input characters
        self.max_output_length = 50000  # Max output characters

    def validate_input(
        self, prompt: str, user_id: str = "anonymous"
    ) -> tuple[bool, str]:
        """Validate input for security concerns."""
        if not prompt or not isinstance(prompt, str):
            return False, "Invalid input: empty or not a string"

        if len(prompt) > self.max_input_length:
            return (
                False,
                f"Input too long: {len(prompt)} > {self.max_input_length}",
            )

        # Check for injection patterns
        prompt_lower = prompt.lower()
        for pattern in self.blocked_patterns:
            if pattern.lower() in prompt_lower:
                logger.warning(
                    f"Blocked pattern detected in input from user {user_id}: {pattern}"
                )
                return False, f"Input contains blocked pattern: {pattern}"

        return True, "OK"

    def sanitize_output(self, response: str) -> str:
        """Sanitize output for safety."""
        if not response:
            return ""

        # Truncate if too long
        if len(response) > self.max_output_length:
            response = response[: self.max_output_length] + "... [truncated]"

        return response

    def hash_sensitive_data(self, data: str) -> str:
        """Hash sensitive data for logging."""
        return hashlib.sha256(data.encode()).hexdigest()[:16]


# =============================================================================
# Enhanced Ollama Backend
# =============================================================================


class OllamaBackend(BaseModelBackend):
    """Enterprise-grade Ollama backend implementation with full reliability features."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
        default_budget: int = 100000,
    ):
        self.base_url = base_url
        self.model = model

        # Initialize enterprise features
        self.token_manager = OllamaTokenBudgetManager(default_budget)
        self.model_selector = OllamaModelSelector()
        self.context_manager = OllamaContextManager()
        self.error_recovery = OllamaErrorRecovery()
        self.performance_monitor = OllamaPerformanceMonitor()
        self.security_manager = OllamaSecurityManager()

        logger.info(f"OllamaBackend initialized: {base_url}, model={model}")

    async def generate(
        self,
        prompt: str,
        user_id: str = "anonymous",
        conversation_id: Optional[str] = None,
        task_type: TaskType = TaskType.GENERAL,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate text using Ollama API with enterprise features."""
        start_time = time.time()

        # Security validation
        valid, reason = self.security_manager.validate_input(prompt, user_id)
        if not valid:
            return {"error": reason, "success": False}

        # Select model if auto-selection enabled
        model = kwargs.pop("model", None) or self.model
        if kwargs.pop("auto_select_model", False):
            await self._refresh_available_models()
            model = self.model_selector.select_model(
                task_type=task_type,
                prefer_speed=kwargs.pop("prefer_speed", False),
                prefer_quality=kwargs.pop("prefer_quality", False),
                max_context_needed=self.token_manager.estimate_tokens(prompt),
            )

        # Check budget
        max_tokens = int(kwargs.get("num_predict", 512))
        budget_ok, budget_msg = self.token_manager.check_budget(
            user_id, prompt, model, max_tokens
        )
        if not budget_ok:
            return {"error": budget_msg, "success": False}

        # Get conversation context if available
        if conversation_id:
            context = self.context_manager.get_context(conversation_id, model)
            if context:
                # Prepend context to prompt
                context_str = "\n".join(
                    f"{m['role']}: {m['content']}" for m in context
                )
                prompt = f"{context_str}\nuser: {prompt}"

        # Execute with error recovery
        async def _do_generate():
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        **kwargs,
                    },
                    timeout=120.0,
                )
                response.raise_for_status()
                return response.json()

        success, result, error_msg = (
            await self.error_recovery.execute_with_retry(_do_generate)
        )

        latency_ms = (time.time() - start_time) * 1000

        if not success:
            self.performance_monitor.record_request(
                model=model,
                latency_ms=latency_ms,
                input_tokens=self.token_manager.estimate_tokens(prompt),
                output_tokens=0,
                success=False,
            )
            return {"error": error_msg, "success": False}

        # Process successful response
        output_text = result.get("response", "")
        output_text = self.security_manager.sanitize_output(output_text)

        input_tokens = self.token_manager.estimate_tokens(prompt)
        output_tokens = self.token_manager.estimate_tokens(output_text)

        # Record metrics
        self.token_manager.record_usage(
            user_id, input_tokens, output_tokens, model
        )
        self.performance_monitor.record_request(
            model=model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=True,
        )
        self.model_selector.record_performance(model, latency_ms / 1000, True)

        # Update conversation context
        if conversation_id:
            self.context_manager.add_message(
                conversation_id, "user", prompt, model
            )
            self.context_manager.add_message(
                conversation_id, "assistant", output_text, model
            )

        return {
            "success": True,
            "response": output_text,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "user_budget_remaining": self.token_manager.get_user_stats(
                user_id
            )["remaining"],
        }

    async def embed(self, text: str) -> list[float]:
        """Generate embeddings using Ollama API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json().get("embedding", [])

    async def health(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/tags", timeout=5.0
                )
                return response.status_code == HTTP_OK
        except Exception:
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        """List available Ollama models."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/tags", timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                return data.get("models", [])
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def pull_model(self, model_name: str) -> dict[str, Any]:
        """Pull a model from Ollama registry."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name, "stream": False},
                    timeout=600.0,  # Models can take a while to pull
                )
                response.raise_for_status()
                return {
                    "success": True,
                    "model": model_name,
                    "message": "Model pulled successfully",
                }
        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            return {"success": False, "error": str(e)}

    async def get_model_info(self, model_name: str) -> dict[str, Any]:
        """Get detailed information about a model."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/show",
                    json={"name": model_name},
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get model info for {model_name}: {e}")
            return {"error": str(e)}

    async def _refresh_available_models(self) -> None:
        """Refresh the list of available models for auto-selection."""
        models = await self.list_models()
        model_names = [m.get("name", "").split(":")[0] for m in models]
        self.model_selector.update_available_models(model_names)

    def get_performance_stats(self) -> dict[str, Any]:
        """Get comprehensive performance statistics."""
        return self.performance_monitor.get_stats()

    def get_user_budget_stats(self, user_id: str) -> dict[str, Any]:
        """Get budget statistics for a user."""
        return self.token_manager.get_user_stats(user_id)

    def get_circuit_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        available, reason = self.error_recovery.is_available()
        return {
            "state": self.error_recovery.state.value,
            "available": available,
            "reason": reason,
            "failure_count": self.error_recovery.failure_count,
        }
