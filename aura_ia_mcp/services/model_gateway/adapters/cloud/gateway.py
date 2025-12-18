"""
Unified Model Gateway for Aura IA MCP.

Routes requests between local Ollama and cloud providers based on:
- Model availability
- Resource offloading rules (LOCAL FIRST)
- User preferences
- Task requirements

Features:
- Automatic fallback (local → cloud)
- Transparent model routing
- Unified API interface
- Cost tracking across providers

RESOURCE OFFLOADING RULES:
1. ALWAYS check local Ollama first
2. Offload to cloud ONLY when:
   - Local unavailable (circuit open)
   - Context exceeds local capacity
   - User explicitly requests cloud
   - Task requires cloud-only capabilities
3. Track costs per provider
4. Log all routing decisions
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ..ollama import OllamaBackend
from .factory import CloudAdapterFactory, get_cloud_factory

logger = logging.getLogger(__name__)


# =============================================================================
# Routing Configuration
# =============================================================================


class RoutingTarget(Enum):
    """Where to route the request."""

    LOCAL = "local"  # Local Ollama
    CLOUD = "cloud"  # Cloud provider
    HYBRID = "hybrid"  # Try local, fallback to cloud


@dataclass
class RoutingDecision:
    """Result of routing decision."""

    target: RoutingTarget
    model_id: str
    provider: str
    reason: str
    is_fallback: bool = False


class RoutingPolicy(Enum):
    """Routing policy for requests."""

    LOCAL_ONLY = "local_only"  # Never use cloud
    CLOUD_ONLY = "cloud_only"  # Never use local
    LOCAL_FIRST = "local_first"  # Prefer local, fallback to cloud (DEFAULT)
    CLOUD_FIRST = "cloud_first"  # Prefer cloud, fallback to local
    COST_OPTIMIZED = "cost_optimized"  # Minimize cost (free tier first)


# =============================================================================
# Model Aliases
# =============================================================================


# Map user-friendly names to actual model IDs
MODEL_ALIASES: dict[str, dict[str, str]] = {
    # Generic aliases
    "default": {"local": "llama3", "cloud": "gemini-1.5-flash"},
    "fast": {"local": "llama3", "cloud": "gemini-1.5-flash"},
    "smart": {"local": "llama3:70b", "cloud": "gemini-1.5-pro"},
    "code": {"local": "codellama", "cloud": "qwen3-coder-480b"},
    "coder": {"local": "codellama", "cloud": "qwen3-coder-480b"},
    "chat": {"local": "llama3", "cloud": "gemini-1.5-flash"},
    "reasoning": {"local": "llama3:70b", "cloud": "deepseek-v3.1-671b"},
    # Direct mappings
    "gpt-4": {"cloud": "gemini-1.5-pro"},
    "gpt-3.5": {"cloud": "gemini-1.5-flash"},
    "claude": {"cloud": "gemini-1.5-flash"},  # Best available free
    # Qwen3 Coder aliases
    "qwen3-coder": {"cloud": "qwen3-coder-480b"},
    "qwen3-coder:480b-cloud": {"cloud": "qwen3-coder-480b"},
    # DeepSeek aliases (ollama run deepseek-v3.1:671b-cloud)
    "deepseek": {"cloud": "deepseek-v3.1-671b"},
    "deepseek-v3": {"cloud": "deepseek-v3.1-671b"},
    "deepseek-v3.1": {"cloud": "deepseek-v3.1-671b"},
    "deepseek-v3.1:671b-cloud": {"cloud": "deepseek-v3.1-671b"},
    # GPT-OSS aliases (ollama run gpt-oss:120b-cloud)
    "gpt-oss": {"cloud": "gpt-oss-120b"},
    "gpt-oss:120b-cloud": {"cloud": "gpt-oss-120b"},
    # Gemini 3 aliases (ollama run gemini-3-pro-preview:latest)
    "gemini-3": {"cloud": "gemini-3-pro-preview"},
    "gemini-3-pro": {"cloud": "gemini-3-pro-preview"},
    "gemini-3-pro-preview:latest": {"cloud": "gemini-3-pro-preview"},
    # Kimi K2 1T aliases (ollama run kimi-k2:1t-cloud)
    "kimi-1t": {"cloud": "kimi-k2-1t"},
    "kimi-k2-1t": {"cloud": "kimi-k2-1t"},
    "kimi-k2:1t-cloud": {"cloud": "kimi-k2-1t"},
}


# =============================================================================
# Unified Model Gateway
# =============================================================================


class UnifiedModelGateway:
    """
    Unified gateway for local and cloud model access.

    Routes requests based on:
    - Model availability
    - Routing policy
    - Task requirements
    - Cost optimization
    """

    def __init__(
        self,
        ollama_backend: Optional[OllamaBackend] = None,
        cloud_factory: Optional[CloudAdapterFactory] = None,
        default_policy: RoutingPolicy = RoutingPolicy.LOCAL_FIRST,
        local_context_limit: int = 131072,  # 128K default
    ):
        self.ollama = ollama_backend or OllamaBackend()
        self.cloud_factory = cloud_factory or get_cloud_factory()
        self.default_policy = default_policy
        self.local_context_limit = local_context_limit

        # Statistics
        self.stats = {
            "local_requests": 0,
            "cloud_requests": 0,
            "fallback_count": 0,
            "errors": 0,
        }

        logger.info(
            f"UnifiedModelGateway initialized with policy: {default_policy.value}"
        )

    def _resolve_model(
        self,
        model: str,
        policy: RoutingPolicy,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Resolve model alias to actual model IDs.

        Returns: (local_model, cloud_model) tuple
        """
        model = model.lower()

        # Check aliases
        if model in MODEL_ALIASES:
            alias = MODEL_ALIASES[model]
            return alias.get("local"), alias.get("cloud")

        # Check if it's a known cloud model
        from .base_cloud import ALL_CLOUD_MODELS

        if model in ALL_CLOUD_MODELS:
            return None, model

        # Assume it's a local model
        return model, None

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count."""
        return max(1, (len(text) + 3) // 4)

    async def _check_local_health(self) -> bool:
        """Check if local Ollama is healthy."""
        try:
            return await self.ollama.health()
        except Exception:
            return False

    def _decide_route(
        self,
        model: str,
        prompt: str,
        policy: RoutingPolicy,
        force_cloud: bool = False,
        force_local: bool = False,
    ) -> RoutingDecision:
        """
        Decide where to route the request.

        Implements resource offloading rules.
        """
        local_model, cloud_model = self._resolve_model(model, policy)
        estimated_tokens = self._estimate_tokens(prompt)

        # Force flags override policy
        if force_cloud:
            target_model = cloud_model or "gemini-1.5-flash"
            return RoutingDecision(
                target=RoutingTarget.CLOUD,
                model_id=target_model,
                provider="cloud",
                reason="Explicitly requested cloud",
            )

        if force_local:
            target_model = local_model or "llama3"
            return RoutingDecision(
                target=RoutingTarget.LOCAL,
                model_id=target_model,
                provider="ollama",
                reason="Explicitly requested local",
            )

        # Policy-based routing
        if policy == RoutingPolicy.LOCAL_ONLY:
            return RoutingDecision(
                target=RoutingTarget.LOCAL,
                model_id=local_model or model,
                provider="ollama",
                reason="Local-only policy",
            )

        if policy == RoutingPolicy.CLOUD_ONLY:
            return RoutingDecision(
                target=RoutingTarget.CLOUD,
                model_id=cloud_model or "gemini-1.5-flash",
                provider="cloud",
                reason="Cloud-only policy",
            )

        # Context size check
        if estimated_tokens > self.local_context_limit:
            return RoutingDecision(
                target=RoutingTarget.CLOUD,
                model_id=cloud_model or "gemini-1.5-flash",
                provider="cloud",
                reason=f"Context ({estimated_tokens} tokens) exceeds local limit ({self.local_context_limit})",
            )

        # Cloud-specific model requested
        if cloud_model and not local_model:
            return RoutingDecision(
                target=RoutingTarget.CLOUD,
                model_id=cloud_model,
                provider="cloud",
                reason="Cloud-specific model requested",
            )

        # Default: LOCAL_FIRST with HYBRID fallback
        if policy in [RoutingPolicy.LOCAL_FIRST, RoutingPolicy.COST_OPTIMIZED]:
            return RoutingDecision(
                target=RoutingTarget.HYBRID,
                model_id=local_model or model,
                provider="hybrid",
                reason="Local-first with cloud fallback",
            )

        # CLOUD_FIRST
        return RoutingDecision(
            target=RoutingTarget.HYBRID,
            model_id=cloud_model or "gemini-1.5-flash",
            provider="hybrid",
            reason="Cloud-first with local fallback",
        )

    async def generate(
        self,
        prompt: str,
        model: str = "default",
        user_id: str = "anonymous",
        policy: Optional[RoutingPolicy] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        force_cloud: bool = False,
        force_local: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate text using the appropriate backend.

        Args:
            prompt: The input prompt
            model: Model name or alias
            user_id: User identifier for tracking
            policy: Routing policy (defaults to LOCAL_FIRST)
            temperature: Generation temperature
            max_tokens: Maximum output tokens
            force_cloud: Force cloud routing
            force_local: Force local routing

        Returns:
            dict with response and metadata
        """
        start_time = time.time()
        policy = policy or self.default_policy

        # Make routing decision
        decision = self._decide_route(
            model=model,
            prompt=prompt,
            policy=policy,
            force_cloud=force_cloud,
            force_local=force_local,
        )

        logger.info(
            f"Routing decision: {decision.target.value} → {decision.model_id} "
            f"(reason: {decision.reason})"
        )

        # Execute based on routing decision
        result: dict[str, Any] = {}

        if decision.target == RoutingTarget.LOCAL:
            result = await self._execute_local(
                prompt, decision.model_id, temperature, max_tokens, **kwargs
            )

        elif decision.target == RoutingTarget.CLOUD:
            result = await self._execute_cloud(
                prompt,
                decision.model_id,
                user_id,
                temperature,
                max_tokens,
                **kwargs,
            )

        else:  # HYBRID
            # Try local first, fallback to cloud on failure
            result = await self._execute_hybrid(
                prompt=prompt,
                local_model=decision.model_id,
                user_id=user_id,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

        # Add routing metadata
        latency_ms = (time.time() - start_time) * 1000
        result["routing"] = {
            "decision": decision.target.value,
            "model": decision.model_id,
            "provider": decision.provider,
            "reason": decision.reason,
            "is_fallback": result.get("is_fallback", False),
            "latency_ms": latency_ms,
        }

        return result

    async def _execute_local(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute request on local Ollama."""
        try:
            response = await self.ollama.generate(
                prompt=prompt,
                model=model,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )

            self.stats["local_requests"] += 1

            return {
                "success": True,
                "response": response.get("response", ""),
                "model": model,
                "provider": "ollama",
                "is_local": True,
            }

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Local generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "ollama",
            }

    async def _execute_cloud(
        self,
        prompt: str,
        model: str,
        user_id: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute request on cloud provider."""
        try:
            adapter = self.cloud_factory.get_adapter(model)
            if not adapter:
                # Try default free adapter
                adapter = self.cloud_factory.get_free_adapter()

            if not adapter:
                return {
                    "success": False,
                    "error": f"No cloud adapter available for {model}",
                    "provider": "cloud",
                }

            result = await adapter.generate(
                prompt=prompt,
                user_id=user_id,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            if result.get("success"):
                self.stats["cloud_requests"] += 1
            else:
                self.stats["errors"] += 1

            result["is_local"] = False
            return result

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cloud generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "cloud",
            }

    async def _execute_hybrid(
        self,
        prompt: str,
        local_model: str,
        user_id: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute with local-first, cloud-fallback strategy."""
        # Try local first
        local_healthy = await self._check_local_health()

        if local_healthy:
            result = await self._execute_local(
                prompt, local_model, temperature, max_tokens, **kwargs
            )
            if result.get("success"):
                return result
            logger.warning(
                f"Local failed, falling back to cloud: {result.get('error')}"
            )

        # Fallback to cloud
        self.stats["fallback_count"] += 1
        cloud_result = await self._execute_cloud(
            prompt=prompt,
            model="gemini-1.5-flash",  # FREE TIER
            user_id=user_id,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        cloud_result["is_fallback"] = True
        return cloud_result

    async def health_check(self) -> dict[str, Any]:
        """Check health of all backends."""
        local_health = await self._check_local_health()
        cloud_health = await self.cloud_factory.health_check_all()

        return {
            "local": {
                "healthy": local_health,
                "provider": "ollama",
            },
            "cloud": cloud_health,
            "stats": self.stats,
            "default_policy": self.default_policy.value,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get gateway statistics."""
        total = self.stats["local_requests"] + self.stats["cloud_requests"]
        return {
            **self.stats,
            "total_requests": total,
            "local_percentage": (
                (self.stats["local_requests"] / total * 100) if total else 0
            ),
            "cloud_percentage": (
                (self.stats["cloud_requests"] / total * 100) if total else 0
            ),
            "fallback_rate": (
                (self.stats["fallback_count"] / total * 100) if total else 0
            ),
        }

    def get_budget_stats(self) -> dict[str, Any]:
        """Get budget statistics from cloud factory."""
        return self.cloud_factory.get_budget_stats()


# =============================================================================
# Global Gateway Instance
# =============================================================================


_global_gateway: Optional[UnifiedModelGateway] = None


def get_unified_gateway() -> UnifiedModelGateway:
    """Get or create global gateway instance."""
    global _global_gateway
    if _global_gateway is None:
        _global_gateway = UnifiedModelGateway()
    return _global_gateway


async def generate(
    prompt: str,
    model: str = "default",
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience function for generation via global gateway."""
    gateway = get_unified_gateway()
    return await gateway.generate(prompt, model, **kwargs)
