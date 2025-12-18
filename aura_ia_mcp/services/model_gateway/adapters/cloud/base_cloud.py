"""
Base Cloud Adapter with Enterprise Features for Aura IA MCP.

This module provides the foundation for all cloud model adapters with:
- Per-provider token budget management
- Circuit breaker for fault tolerance
- Resource offloading rules (LOCAL FIRST, cloud as fallback)
- Security validation and PII filtering
- Rate limiting and quota management

RESOURCE OFFLOADING RULES:
1. ALWAYS prefer local Ollama models when available
2. Offload to cloud ONLY when:
   - Local model is unavailable (circuit open)
   - Task explicitly requires cloud model capabilities
   - User explicitly requests cloud model
   - Local model context window is insufficient
3. Track costs separately per provider
4. Respect rate limits (RPM/TPM quotas)

PRD Reference: Section 8.13 (External LLM Integration)
"""

import asyncio
import hashlib
import logging
import os
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Cloud Provider Configuration
# =============================================================================


class CloudProvider(Enum):
    """Supported cloud providers - ALL via Ollama Cloud (FREE)."""

    OLLAMA_CLOUD = "ollama_cloud"  # Ollama hosted cloud models (FREE)
    GOOGLE = "google"  # Google Gemini direct API
    MINIMAX = "minimax"
    MOONSHOT = "moonshot"  # Kimi
    ALIBABA = "alibaba"  # Qwen


@dataclass
class CloudModelConfig:
    """Configuration for a cloud model."""

    provider: CloudProvider
    model_id: str
    display_name: str
    api_endpoint: str
    context_window: int
    input_cost_per_1k: float  # Cost per 1000 input tokens
    output_cost_per_1k: float  # Cost per 1000 output tokens
    rate_limit_rpm: int  # Requests per minute
    rate_limit_tpm: int  # Tokens per minute
    is_free_tier: bool = False
    free_tier_daily_limit: int = 0


# Google Gemini Models (FREE TIER FIRST!)
GOOGLE_MODELS = {
    "gemini-1.5-flash": CloudModelConfig(
        provider=CloudProvider.GOOGLE,
        model_id="gemini-1.5-flash",
        display_name="Gemini 1.5 Flash (FREE)",
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        context_window=1048576,  # 1M tokens!
        input_cost_per_1k=0.0,  # FREE
        output_cost_per_1k=0.0,  # FREE
        rate_limit_rpm=15,  # Free tier: 15 RPM
        rate_limit_tpm=1000000,  # 1M TPM free
        is_free_tier=True,
        free_tier_daily_limit=1500,  # 1500 requests/day free
    ),
    "gemini-1.5-flash-8b": CloudModelConfig(
        provider=CloudProvider.GOOGLE,
        model_id="gemini-1.5-flash-8b",
        display_name="Gemini 1.5 Flash 8B (FREE)",
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-8b:generateContent",
        context_window=1048576,
        input_cost_per_1k=0.0,
        output_cost_per_1k=0.0,
        rate_limit_rpm=15,
        rate_limit_tpm=1000000,
        is_free_tier=True,
        free_tier_daily_limit=1500,
    ),
    "gemini-1.5-pro": CloudModelConfig(
        provider=CloudProvider.GOOGLE,
        model_id="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent",
        context_window=2097152,  # 2M tokens!
        input_cost_per_1k=0.00125,  # $1.25/1M
        output_cost_per_1k=0.005,  # $5/1M
        rate_limit_rpm=2,  # Free tier: 2 RPM
        rate_limit_tpm=32000,
        is_free_tier=True,
        free_tier_daily_limit=50,
    ),
    "gemini-2.0-flash-exp": CloudModelConfig(
        provider=CloudProvider.GOOGLE,
        model_id="gemini-2.0-flash-exp",
        display_name="Gemini 2.0 Flash Experimental (FREE)",
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
        context_window=1048576,
        input_cost_per_1k=0.0,
        output_cost_per_1k=0.0,
        rate_limit_rpm=10,
        rate_limit_tpm=4000000,
        is_free_tier=True,
        free_tier_daily_limit=1500,
    ),
}

# MOONSHOT_MODELS - Direct API (paid) - Keep for legacy/direct access
MOONSHOT_MODELS = {
    "kimi-k2-8k": CloudModelConfig(
        provider=CloudProvider.MOONSHOT,
        model_id="moonshot-v1-8k",
        display_name="Kimi K2 (8K)",
        api_endpoint="https://api.moonshot.cn/v1/chat/completions",
        context_window=8192,
        input_cost_per_1k=0.001,
        output_cost_per_1k=0.001,
        rate_limit_rpm=60,
        rate_limit_tpm=100000,
    ),
    "kimi-k2-32k": CloudModelConfig(
        provider=CloudProvider.MOONSHOT,
        model_id="moonshot-v1-32k",
        display_name="Kimi K2 (32K)",
        api_endpoint="https://api.moonshot.cn/v1/chat/completions",
        context_window=32768,
        input_cost_per_1k=0.002,
        output_cost_per_1k=0.002,
        rate_limit_rpm=60,
        rate_limit_tpm=100000,
    ),
    "kimi-k2-128k": CloudModelConfig(
        provider=CloudProvider.MOONSHOT,
        model_id="moonshot-v1-128k",
        display_name="Kimi K2 (128K)",
        api_endpoint="https://api.moonshot.cn/v1/chat/completions",
        context_window=131072,
        input_cost_per_1k=0.005,
        output_cost_per_1k=0.005,
        rate_limit_rpm=60,
        rate_limit_tpm=100000,
    ),
}

# MINIMAX_MODELS - Deprecated, now in OLLAMA_CLOUD_MODELS
# Kept for backward compatibility
MINIMAX_MODELS = {
    "minimax-m2": CloudModelConfig(
        provider=CloudProvider.OLLAMA_CLOUD,  # Now via Ollama Cloud (FREE)
        model_id="minimax-m2:latest-cloud",
        display_name="Minimax M2 (Ollama Cloud FREE)",
        api_endpoint="http://localhost:11434/api/generate",
        context_window=245760,
        input_cost_per_1k=0.0,  # FREE via Ollama Cloud
        output_cost_per_1k=0.0,
        rate_limit_rpm=60,
        rate_limit_tpm=500000,
        is_free_tier=True,
        free_tier_daily_limit=0,
    ),
}

# ALIBABA_MODELS - Direct API (paid)
ALIBABA_MODELS = {
    "qwen-turbo": CloudModelConfig(
        provider=CloudProvider.ALIBABA,
        model_id="qwen-turbo",
        display_name="Qwen Turbo",
        api_endpoint="https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
        context_window=8192,
        input_cost_per_1k=0.0008,
        output_cost_per_1k=0.002,
        rate_limit_rpm=60,
        rate_limit_tpm=100000,
    ),
    "qwen-plus": CloudModelConfig(
        provider=CloudProvider.ALIBABA,
        model_id="qwen-plus",
        display_name="Qwen Plus",
        api_endpoint="https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
        context_window=32768,
        input_cost_per_1k=0.002,
        output_cost_per_1k=0.006,
        rate_limit_rpm=60,
        rate_limit_tpm=100000,
    ),
    "qwen-max": CloudModelConfig(
        provider=CloudProvider.ALIBABA,
        model_id="qwen-max",
        display_name="Qwen Max (Best)",
        api_endpoint="https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
        context_window=32768,
        input_cost_per_1k=0.004,
        output_cost_per_1k=0.012,
        rate_limit_rpm=60,
        rate_limit_tpm=100000,
    ),
}

# =============================================================================
# OLLAMA CLOUD MODELS (FREE TO USE!)
# These models are hosted on Ollama's cloud infrastructure
# Access via: ollama run <model>:<variant>-cloud
# =============================================================================

OLLAMA_CLOUD_MODELS = {
    # DeepSeek V3.1 671B (ollama run deepseek-v3.1:671b-cloud)
    "deepseek-v3.1-671b": CloudModelConfig(
        provider=CloudProvider.OLLAMA_CLOUD,
        model_id="deepseek-v3.1:671b-cloud",
        display_name="DeepSeek V3.1 671B (Ollama Cloud FREE)",
        api_endpoint="http://localhost:11434/api/generate",  # Ollama API
        context_window=131072,  # 128K context
        input_cost_per_1k=0.0,  # FREE via Ollama Cloud
        output_cost_per_1k=0.0,  # FREE via Ollama Cloud
        rate_limit_rpm=60,
        rate_limit_tpm=500000,
        is_free_tier=True,
        free_tier_daily_limit=0,  # Unlimited
    ),
    # GPT-OSS 120B (ollama run gpt-oss:120b-cloud)
    "gpt-oss-120b": CloudModelConfig(
        provider=CloudProvider.OLLAMA_CLOUD,
        model_id="gpt-oss:120b-cloud",
        display_name="GPT-OSS 120B (Ollama Cloud FREE)",
        api_endpoint="http://localhost:11434/api/generate",  # Ollama API
        context_window=131072,  # 128K context
        input_cost_per_1k=0.0,  # FREE via Ollama Cloud
        output_cost_per_1k=0.0,  # FREE via Ollama Cloud
        rate_limit_rpm=60,
        rate_limit_tpm=300000,
        is_free_tier=True,
        free_tier_daily_limit=0,  # Unlimited
    ),
    # Qwen3 Coder 480B (ollama run qwen3-coder:480b-cloud)
    "qwen3-coder-480b": CloudModelConfig(
        provider=CloudProvider.OLLAMA_CLOUD,
        model_id="qwen3-coder:480b-cloud",
        display_name="Qwen3 Coder 480B (Ollama Cloud FREE)",
        api_endpoint="http://localhost:11434/api/generate",  # Ollama API
        context_window=131072,  # 128K context
        input_cost_per_1k=0.0,  # FREE via Ollama Cloud
        output_cost_per_1k=0.0,  # FREE via Ollama Cloud
        rate_limit_rpm=30,
        rate_limit_tpm=200000,
        is_free_tier=True,
        free_tier_daily_limit=0,  # Unlimited
    ),
    # Gemini 3 Pro Preview (ollama run gemini-3-pro-preview:latest)
    "gemini-3-pro-preview": CloudModelConfig(
        provider=CloudProvider.OLLAMA_CLOUD,
        model_id="gemini-3-pro-preview:latest",
        display_name="Gemini 3 Pro Preview (Ollama Cloud FREE)",
        api_endpoint="http://localhost:11434/api/generate",  # Ollama API
        context_window=2097152,  # 2M tokens
        input_cost_per_1k=0.0,  # FREE via Ollama Cloud
        output_cost_per_1k=0.0,  # FREE via Ollama Cloud
        rate_limit_rpm=30,
        rate_limit_tpm=1000000,
        is_free_tier=True,
        free_tier_daily_limit=0,  # Unlimited
    ),
    # Kimi K2 1T (ollama run kimi-k2:1t-cloud)
    "kimi-k2-1t": CloudModelConfig(
        provider=CloudProvider.OLLAMA_CLOUD,
        model_id="kimi-k2:1t-cloud",
        display_name="Kimi K2 1T (Ollama Cloud FREE)",
        api_endpoint="http://localhost:11434/api/generate",  # Ollama API
        context_window=1048576,  # 1M tokens
        input_cost_per_1k=0.0,  # FREE via Ollama Cloud
        output_cost_per_1k=0.0,  # FREE via Ollama Cloud
        rate_limit_rpm=20,
        rate_limit_tpm=500000,
        is_free_tier=True,
        free_tier_daily_limit=0,  # Unlimited
    ),
    # Minimax M2 (ollama run minimax-m2:latest-cloud)
    "minimax-m2": CloudModelConfig(
        provider=CloudProvider.OLLAMA_CLOUD,
        model_id="minimax-m2:latest-cloud",
        display_name="Minimax M2 (Ollama Cloud FREE)",
        api_endpoint="http://localhost:11434/api/generate",  # Ollama API
        context_window=245760,
        input_cost_per_1k=0.0,  # FREE via Ollama Cloud
        output_cost_per_1k=0.0,  # FREE via Ollama Cloud
        rate_limit_rpm=60,
        rate_limit_tpm=100000,
        is_free_tier=True,
        free_tier_daily_limit=0,  # Unlimited
    ),
}

# Unified model registry
ALL_CLOUD_MODELS = {
    **GOOGLE_MODELS,
    **OLLAMA_CLOUD_MODELS,
    **MOONSHOT_MODELS,
    **ALIBABA_MODELS,
}


# =============================================================================
# Per-Provider Budget Management
# =============================================================================


@dataclass
class ProviderUsage:
    """Usage tracking for a single provider."""

    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    daily_requests: int = 0
    daily_reset_time: float = field(default_factory=time.time)
    minute_requests: list = field(
        default_factory=list
    )  # Timestamps for rate limiting


class CloudProviderBudget:
    """Per-provider budget and rate limit management."""

    def __init__(
        self,
        provider: CloudProvider,
        daily_budget_usd: float = 0.0,  # 0 = unlimited for free tier
        daily_request_limit: int = 1500,  # Free tier default
    ):
        self.provider = provider
        self.daily_budget_usd = daily_budget_usd
        self.daily_request_limit = daily_request_limit
        self.usage = ProviderUsage()
        self._lock = asyncio.Lock()

    def _reset_daily_if_needed(self) -> None:
        """Reset daily counters if a new day has started."""
        current_time = time.time()
        # Reset if more than 24 hours have passed
        if current_time - self.usage.daily_reset_time > 86400:
            self.usage.daily_requests = 0
            self.usage.daily_reset_time = current_time
            logger.info(f"Daily counters reset for {self.provider.value}")

    def _clean_minute_window(self) -> None:
        """Remove request timestamps older than 1 minute."""
        current_time = time.time()
        self.usage.minute_requests = [
            ts for ts in self.usage.minute_requests if current_time - ts < 60
        ]

    async def check_rate_limit(
        self, model_config: CloudModelConfig
    ) -> tuple[bool, str]:
        """Check if request is within rate limits."""
        async with self._lock:
            self._reset_daily_if_needed()
            self._clean_minute_window()

            # Check RPM (requests per minute)
            if len(self.usage.minute_requests) >= model_config.rate_limit_rpm:
                wait_time = 60 - (time.time() - self.usage.minute_requests[0])
                return False, f"Rate limit exceeded. Wait {wait_time:.1f}s"

            # Check daily limit for free tier
            if model_config.is_free_tier:
                if (
                    self.usage.daily_requests
                    >= model_config.free_tier_daily_limit
                ):
                    return (
                        False,
                        f"Daily free tier limit ({model_config.free_tier_daily_limit}) exceeded",
                    )

            # Check daily budget
            if (
                self.daily_budget_usd > 0
                and self.usage.total_cost >= self.daily_budget_usd
            ):
                return (
                    False,
                    f"Daily budget (${self.daily_budget_usd}) exceeded",
                )

            return True, "OK"

    async def record_request(
        self,
        model_config: CloudModelConfig,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record a successful request."""
        async with self._lock:
            self.usage.total_requests += 1
            self.usage.total_input_tokens += input_tokens
            self.usage.total_output_tokens += output_tokens
            self.usage.daily_requests += 1
            self.usage.minute_requests.append(time.time())

            # Calculate cost
            input_cost = (input_tokens / 1000) * model_config.input_cost_per_1k
            output_cost = (
                output_tokens / 1000
            ) * model_config.output_cost_per_1k
            self.usage.total_cost += input_cost + output_cost

    def get_stats(self) -> dict[str, Any]:
        """Get usage statistics."""
        self._reset_daily_if_needed()
        return {
            "provider": self.provider.value,
            "total_requests": self.usage.total_requests,
            "daily_requests": self.usage.daily_requests,
            "daily_limit": self.daily_request_limit,
            "total_input_tokens": self.usage.total_input_tokens,
            "total_output_tokens": self.usage.total_output_tokens,
            "total_cost_usd": round(self.usage.total_cost, 4),
            "daily_budget_usd": self.daily_budget_usd,
            "budget_remaining_usd": max(
                0, self.daily_budget_usd - self.usage.total_cost
            ),
        }


# =============================================================================
# Circuit Breaker for Cloud APIs
# =============================================================================


class CloudCircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CloudCircuitBreaker:
    """Circuit breaker for cloud API fault tolerance."""

    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    half_open_max_calls: int = 3

    _failure_count: int = field(default=0, init=False)
    _last_failure_time: Optional[float] = field(default=None, init=False)
    _state: CloudCircuitState = field(
        default=CloudCircuitState.CLOSED, init=False
    )
    _half_open_calls: int = field(default=0, init=False)

    def is_available(self) -> tuple[bool, str]:
        """Check if circuit allows requests."""
        if self._state == CloudCircuitState.CLOSED:
            return True, "OK"

        if self._state == CloudCircuitState.OPEN:
            if self._should_attempt_recovery():
                self._state = CloudCircuitState.HALF_OPEN
                self._half_open_calls = 0
                return True, "Testing recovery"
            return (
                False,
                f"Circuit OPEN. Retry in {self._time_until_recovery():.0f}s",
            )

        # HALF_OPEN
        if self._half_open_calls < self.half_open_max_calls:
            return True, "Half-open testing"
        return False, "Half-open test limit reached"

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time passed for recovery attempt."""
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    def _time_until_recovery(self) -> float:
        """Time until recovery attempt."""
        if self._last_failure_time is None:
            return 0
        return max(
            0, self.recovery_timeout - (time.time() - self._last_failure_time)
        )

    def record_success(self) -> None:
        """Record successful call."""
        if self._state == CloudCircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                self._state = CloudCircuitState.CLOSED
                self._failure_count = 0
                logger.info("Cloud circuit breaker CLOSED (recovered)")
        elif self._state == CloudCircuitState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self, error: str) -> None:
        """Record failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CloudCircuitState.HALF_OPEN:
            self._state = CloudCircuitState.OPEN
            logger.warning(
                f"Cloud circuit breaker OPEN (half-open test failed): {error}"
            )
        elif self._failure_count >= self.failure_threshold:
            self._state = CloudCircuitState.OPEN
            logger.warning(
                f"Cloud circuit breaker OPEN after {self._failure_count} failures: {error}"
            )

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        available, reason = self.is_available()
        return {
            "state": self._state.value,
            "available": available,
            "reason": reason,
            "failure_count": self._failure_count,
            "time_until_recovery": (
                self._time_until_recovery()
                if self._state == CloudCircuitState.OPEN
                else 0
            ),
        }


# =============================================================================
# Security Manager for Cloud APIs
# =============================================================================


class CloudSecurityManager:
    """Security validation for cloud API requests."""

    def __init__(self):
        self.blocked_patterns = [
            "ignore previous",
            "ignore all instructions",
            "disregard",
            "system prompt",
            "jailbreak",
            "DAN mode",
            "pretend you",
            "act as if",
        ]
        self.max_input_length = 100000
        self.max_output_length = 50000

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
                    f"Blocked pattern in cloud request from {user_id}: {pattern}"
                )
                return False, f"Input contains blocked pattern"

        return True, "OK"

    def sanitize_output(self, response: str) -> str:
        """Sanitize output for safety."""
        if not response:
            return ""

        if len(response) > self.max_output_length:
            response = (
                response[: self.max_output_length] + "\n\n[Output truncated]"
            )

        return response

    def hash_for_logging(self, data: str) -> str:
        """Hash sensitive data for logging."""
        return hashlib.sha256(data.encode()).hexdigest()[:12]


# =============================================================================
# Resource Offload Manager
# =============================================================================


class OffloadDecision(Enum):
    """Decision for where to route a request."""

    LOCAL = "local"  # Use local Ollama
    CLOUD = "cloud"  # Use cloud API
    REJECT = "reject"  # Reject request


@dataclass
class OffloadReason:
    """Reason for offload decision."""

    decision: OffloadDecision
    reason: str
    suggested_model: Optional[str] = None


class ResourceOffloadManager:
    """
    Manages resource offloading decisions.

    RULE: LOCAL FIRST, CLOUD AS FALLBACK

    Offload to cloud ONLY when:
    1. Local Ollama is unavailable (circuit open)
    2. User explicitly requests cloud model
    3. Task requires context > local model capacity
    4. Task requires specific cloud capability (e.g., vision)
    """

    def __init__(
        self,
        local_circuit_breaker: Optional[Any] = None,
        local_context_limit: int = 131072,  # Default local context
    ):
        self.local_circuit_breaker = local_circuit_breaker
        self.local_context_limit = local_context_limit
        self.cloud_only_capabilities = {
            "vision",
            "audio",
            "video",
            "long_context",
        }

    def decide(
        self,
        prompt: str,
        requested_model: Optional[str] = None,
        required_capabilities: Optional[set] = None,
        force_cloud: bool = False,
    ) -> OffloadReason:
        """
        Decide whether to use local or cloud resources.

        Returns OffloadReason with decision and explanation.
        """
        required_capabilities = required_capabilities or set()

        # Rule 1: User explicitly requests cloud
        if force_cloud:
            return OffloadReason(
                decision=OffloadDecision.CLOUD,
                reason="User explicitly requested cloud model",
                suggested_model=requested_model,
            )

        # Rule 2: Specific cloud model requested
        if requested_model and requested_model in ALL_CLOUD_MODELS:
            return OffloadReason(
                decision=OffloadDecision.CLOUD,
                reason=f"Specific cloud model requested: {requested_model}",
                suggested_model=requested_model,
            )

        # Rule 3: Cloud-only capability required
        if required_capabilities & self.cloud_only_capabilities:
            caps = required_capabilities & self.cloud_only_capabilities
            return OffloadReason(
                decision=OffloadDecision.CLOUD,
                reason=f"Cloud-only capabilities required: {caps}",
                suggested_model="gemini-1.5-flash",  # Default for capabilities
            )

        # Rule 4: Context too large for local
        estimated_tokens = len(prompt) // 4
        if estimated_tokens > self.local_context_limit:
            return OffloadReason(
                decision=OffloadDecision.CLOUD,
                reason=f"Context ({estimated_tokens} tokens) exceeds local limit ({self.local_context_limit})",
                suggested_model="gemini-1.5-flash",  # 1M context
            )

        # Rule 5: Local circuit breaker open
        if self.local_circuit_breaker:
            available, reason = self.local_circuit_breaker.is_available()
            if not available:
                return OffloadReason(
                    decision=OffloadDecision.CLOUD,
                    reason=f"Local Ollama unavailable: {reason}",
                    suggested_model="gemini-1.5-flash",
                )

        # Default: Use local
        return OffloadReason(
            decision=OffloadDecision.LOCAL,
            reason="Local Ollama available and sufficient",
            suggested_model=requested_model or "llama3",
        )


# =============================================================================
# Base Cloud Adapter
# =============================================================================


class BaseCloudAdapter(ABC):
    """
    Abstract base class for cloud model adapters.

    All cloud adapters inherit from this and implement _call_api().
    Enterprise features are handled here:
    - Security validation
    - Rate limiting
    - Budget tracking
    - Circuit breaker
    - Logging
    """

    def __init__(
        self,
        model_config: CloudModelConfig,
        api_key: str,
        provider_budget: CloudProviderBudget,
        circuit_breaker: Optional[CloudCircuitBreaker] = None,
        security_manager: Optional[CloudSecurityManager] = None,
    ):
        self.model_config = model_config
        self.api_key = api_key
        self.provider_budget = provider_budget
        self.circuit_breaker = circuit_breaker or CloudCircuitBreaker()
        self.security_manager = security_manager or CloudSecurityManager()

        logger.info(
            f"Initialized {model_config.display_name} adapter "
            f"(free_tier={model_config.is_free_tier})"
        )

    @abstractmethod
    async def _call_api(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> tuple[str, int, int]:
        """
        Call the cloud API.

        Returns: (response_text, input_tokens, output_tokens)
        """
        pass

    async def generate(
        self,
        prompt: str,
        user_id: str = "anonymous",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate text with full enterprise stack.

        Returns dict with response and metadata.
        """
        start_time = time.time()

        # 1. Security validation
        valid, reason = self.security_manager.validate_input(prompt, user_id)
        if not valid:
            return {"success": False, "error": reason}

        # 2. Circuit breaker check
        available, cb_reason = self.circuit_breaker.is_available()
        if not available:
            return {
                "success": False,
                "error": f"Service unavailable: {cb_reason}",
            }

        # 3. Rate limit check
        rate_ok, rate_reason = await self.provider_budget.check_rate_limit(
            self.model_config
        )
        if not rate_ok:
            return {"success": False, "error": rate_reason}

        # 4. Call API with retry
        try:
            response_text, input_tokens, output_tokens = await self._call_api(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            # 5. Sanitize output
            response_text = self.security_manager.sanitize_output(
                response_text
            )

            # 6. Record success
            self.circuit_breaker.record_success()
            await self.provider_budget.record_request(
                self.model_config, input_tokens, output_tokens
            )

            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Cloud request success: model={self.model_config.model_id}, "
                f"user={user_id}, tokens={input_tokens}+{output_tokens}, "
                f"latency={latency_ms:.0f}ms"
            )

            return {
                "success": True,
                "response": response_text,
                "model": self.model_config.model_id,
                "provider": self.model_config.provider.value,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "is_free_tier": self.model_config.is_free_tier,
            }

        except Exception as e:
            self.circuit_breaker.record_failure(str(e))
            logger.error(f"Cloud API error: {self.model_config.model_id}: {e}")
            return {"success": False, "error": str(e)}

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        return {
            "model": self.model_config.model_id,
            "provider": self.model_config.provider.value,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "budget": self.provider_budget.get_stats(),
            "is_free_tier": self.model_config.is_free_tier,
        }

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (4 chars/token approximation)."""
        return max(1, (len(text) + 3) // 4)
