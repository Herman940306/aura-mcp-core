"""
Cloud Adapter Factory for Aura IA MCP.

Centralized factory for creating and managing cloud model adapters.
Provides:
- Lazy initialization of adapters
- Shared budget tracking per provider
- Unified health checking
- Adapter pooling and reuse

Usage:
    factory = CloudAdapterFactory()

    # Get Gemini adapter (FREE TIER FIRST)
    gemini = factory.get_adapter("gemini-1.5-flash")
    result = await gemini.generate("Hello!")

    # Get adapter by provider
    adapter = factory.get_adapter_for_provider("google")

    # Check all health
    health = await factory.health_check_all()
"""

import logging
import os
from typing import Any, Optional, Type

from .base_cloud import (
    ALL_CLOUD_MODELS,
    OLLAMA_CLOUD_MODELS,
    BaseCloudAdapter,
    CloudCircuitBreaker,
    CloudModelConfig,
    CloudProvider,
    CloudProviderBudget,
    CloudSecurityManager,
)
from .gemini import GeminiAdapter, create_gemini_adapter
from .kimi import KimiAdapter, create_kimi_adapter
from .minimax import MinimaxAdapter, create_minimax_adapter
from .ollama_cloud import OllamaCloudAdapter, create_ollama_cloud_adapter
from .qwen_cloud import QwenCloudAdapter, create_qwen_adapter

logger = logging.getLogger(__name__)


# =============================================================================
# Adapter Registry
# =============================================================================


# Map model IDs to their adapter classes
MODEL_ADAPTER_MAP: dict[str, Type[BaseCloudAdapter]] = {
    # ==========================================================================
    # OLLAMA CLOUD MODELS (FREE!)
    # All these models use OllamaCloudAdapter via Ollama's HTTP API
    # ==========================================================================
    "deepseek-v3.1-671b": OllamaCloudAdapter,  # ollama run deepseek-v3.1:671b-cloud
    "gpt-oss-120b": OllamaCloudAdapter,  # ollama run gpt-oss:120b-cloud
    "qwen3-coder-480b": OllamaCloudAdapter,  # ollama run qwen3-coder:480b-cloud
    "gemini-3-pro-preview": OllamaCloudAdapter,  # ollama run gemini-3-pro-preview:latest
    "kimi-k2-1t": OllamaCloudAdapter,  # ollama run kimi-k2:1t-cloud
    "minimax-m2": OllamaCloudAdapter,  # ollama run minimax-m2:latest-cloud
    # ==========================================================================
    # Google Gemini (Direct API - FREE tier available)
    # ==========================================================================
    "gemini-1.5-flash": GeminiAdapter,
    "gemini-1.5-flash-8b": GeminiAdapter,
    "gemini-1.5-pro": GeminiAdapter,
    "gemini-2.0-flash-exp": GeminiAdapter,
    # ==========================================================================
    # Moonshot (Kimi) - Direct API
    # ==========================================================================
    "kimi-k2-8k": KimiAdapter,
    "kimi-k2-32k": KimiAdapter,
    "kimi-k2-128k": KimiAdapter,
    # ==========================================================================
    # Alibaba (Qwen) - Direct API
    # ==========================================================================
    "qwen-turbo": QwenCloudAdapter,
    "qwen-plus": QwenCloudAdapter,
    "qwen-max": QwenCloudAdapter,
}

# Map providers to their default models
PROVIDER_DEFAULTS: dict[str, str] = {
    # OLLAMA CLOUD - FREE!
    "ollama_cloud": "deepseek-v3.1-671b",  # Best default FREE model
    "deepseek": "deepseek-v3.1-671b",  # ollama run deepseek-v3.1:671b-cloud
    "gpt-oss": "gpt-oss-120b",  # ollama run gpt-oss:120b-cloud
    "qwen3-coder": "qwen3-coder-480b",  # ollama run qwen3-coder:480b-cloud
    "coder": "qwen3-coder-480b",  # Alias for code tasks
    "gemini-3": "gemini-3-pro-preview",  # ollama run gemini-3-pro-preview:latest
    "kimi-1t": "kimi-k2-1t",  # ollama run kimi-k2:1t-cloud
    "minimax-m2": "minimax-m2",  # ollama run minimax-m2:latest-cloud
    # Google Direct API
    "google": "gemini-1.5-flash",  # FREE TIER FIRST!
    "gemini": "gemini-1.5-flash",
    # Moonshot Direct API
    "moonshot": "kimi-k2-8k",
    "kimi": "kimi-k2-8k",
    # Alibaba Direct API
    "alibaba": "qwen-turbo",
    "qwen": "qwen-turbo",
}


# =============================================================================
# Cloud Adapter Factory
# =============================================================================


class CloudAdapterFactory:
    """
    Factory for creating and managing cloud model adapters.

    Features:
    - Singleton adapters per model (reuse)
    - Shared budget tracking per provider
    - Unified security and circuit breaker
    - Environment-based API key resolution
    """

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        minimax_api_key: Optional[str] = None,
        minimax_group_id: Optional[str] = None,
        moonshot_api_key: Optional[str] = None,
        dashscope_api_key: Optional[str] = None,
    ):
        # API keys (from params or environment)
        self._api_keys = {
            CloudProvider.OLLAMA_CLOUD: "ollama-cloud-free",  # FREE - no API key needed
            CloudProvider.GOOGLE: google_api_key
            or os.environ.get("GOOGLE_API_KEY", ""),
            CloudProvider.MINIMAX: minimax_api_key
            or os.environ.get("MINIMAX_API_KEY", ""),
            CloudProvider.MOONSHOT: moonshot_api_key
            or os.environ.get("MOONSHOT_API_KEY", ""),
            CloudProvider.ALIBABA: dashscope_api_key
            or os.environ.get("DASHSCOPE_API_KEY", ""),
        }
        self._minimax_group_id = minimax_group_id or os.environ.get(
            "MINIMAX_GROUP_ID", ""
        )

        # Shared components (per provider)
        self._budgets: dict[CloudProvider, CloudProviderBudget] = {}
        self._circuit_breakers: dict[CloudProvider, CloudCircuitBreaker] = {}
        self._security_manager = CloudSecurityManager()

        # Adapter cache (per model)
        self._adapters: dict[str, BaseCloudAdapter] = {}

        logger.info("CloudAdapterFactory initialized")
        self._log_available_providers()

    def _log_available_providers(self) -> None:
        """Log which providers have API keys configured."""
        for provider, key in self._api_keys.items():
            status = "✓ configured" if key else "✗ no API key"
            logger.info(f"Provider {provider.value}: {status}")

    def _get_budget(self, provider: CloudProvider) -> CloudProviderBudget:
        """Get or create budget tracker for provider."""
        if provider not in self._budgets:
            # Default budget config per provider
            budget_configs = {
                CloudProvider.OLLAMA_CLOUD: {
                    "daily_budget_usd": 0.0,
                    "daily_request_limit": 100000,
                },  # FREE - unlimited!
                CloudProvider.GOOGLE: {
                    "daily_budget_usd": 0.0,
                    "daily_request_limit": 1500,
                },  # FREE
                CloudProvider.MINIMAX: {
                    "daily_budget_usd": 5.0,
                    "daily_request_limit": 10000,
                },
                CloudProvider.MOONSHOT: {
                    "daily_budget_usd": 5.0,
                    "daily_request_limit": 10000,
                },
                CloudProvider.ALIBABA: {
                    "daily_budget_usd": 5.0,
                    "daily_request_limit": 10000,
                },
            }
            config = budget_configs.get(
                provider,
                {"daily_budget_usd": 5.0, "daily_request_limit": 10000},
            )
            self._budgets[provider] = CloudProviderBudget(
                provider=provider, **config
            )
        return self._budgets[provider]

    def _get_circuit_breaker(
        self, provider: CloudProvider
    ) -> CloudCircuitBreaker:
        """Get or create circuit breaker for provider."""
        if provider not in self._circuit_breakers:
            self._circuit_breakers[provider] = CloudCircuitBreaker()
        return self._circuit_breakers[provider]

    def get_adapter(self, model_id: str) -> Optional[BaseCloudAdapter]:
        """
        Get adapter for a specific model.

        Creates adapter on first request, reuses on subsequent calls.

        Args:
            model_id: Model identifier (e.g., "gemini-1.5-flash")

        Returns:
            BaseCloudAdapter instance or None if model unknown/no API key
        """
        # Check cache
        if model_id in self._adapters:
            return self._adapters[model_id]

        # Find model config
        model_config = ALL_CLOUD_MODELS.get(model_id)
        if not model_config:
            logger.warning(f"Unknown model: {model_id}")
            return None

        # Check API key
        provider = model_config.provider
        api_key = self._api_keys.get(provider, "")
        if not api_key:
            logger.warning(f"No API key for provider {provider.value}")
            return None

        # Get shared components
        budget = self._get_budget(provider)
        circuit_breaker = self._get_circuit_breaker(provider)

        # Create adapter
        adapter: Optional[BaseCloudAdapter] = None

        if provider == CloudProvider.OLLAMA_CLOUD:
            # FREE - no API key needed!
            adapter = OllamaCloudAdapter(
                model_id=model_id,
                provider_budget=budget,
                circuit_breaker=circuit_breaker,
                security_manager=self._security_manager,
            )
        elif provider == CloudProvider.GOOGLE:
            adapter = GeminiAdapter(
                api_key=api_key,
                model_id=model_id,
                provider_budget=budget,
                circuit_breaker=circuit_breaker,
                security_manager=self._security_manager,
            )
        elif provider == CloudProvider.MINIMAX:
            adapter = MinimaxAdapter(
                api_key=api_key,
                group_id=self._minimax_group_id,
                model_id=model_id,
                provider_budget=budget,
                circuit_breaker=circuit_breaker,
                security_manager=self._security_manager,
            )
        elif provider == CloudProvider.MOONSHOT:
            adapter = KimiAdapter(
                api_key=api_key,
                model_id=model_id,
                provider_budget=budget,
                circuit_breaker=circuit_breaker,
                security_manager=self._security_manager,
            )
        elif provider == CloudProvider.ALIBABA:
            adapter = QwenCloudAdapter(
                api_key=api_key,
                model_id=model_id,
                provider_budget=budget,
                circuit_breaker=circuit_breaker,
                security_manager=self._security_manager,
            )

        if adapter:
            self._adapters[model_id] = adapter
            logger.info(f"Created adapter for {model_id}")

        return adapter

    def get_adapter_for_provider(
        self,
        provider_name: str,
        prefer_free: bool = True,
    ) -> Optional[BaseCloudAdapter]:
        """
        Get adapter for a provider (uses default model).

        Args:
            provider_name: Provider name (google, minimax, moonshot, alibaba)
            prefer_free: If True, prefer free tier models (default True)

        Returns:
            BaseCloudAdapter for provider's default model
        """
        provider_name = provider_name.lower()

        # Map to default model
        default_model = PROVIDER_DEFAULTS.get(provider_name)
        if not default_model:
            logger.warning(f"Unknown provider: {provider_name}")
            return None

        return self.get_adapter(default_model)

    def get_free_adapter(self) -> Optional[BaseCloudAdapter]:
        """
        Get the best available FREE tier adapter.

        Priority:
        1. Ollama Cloud models (ALL FREE!) - DeepSeek, GPT-OSS, etc.
        2. Google Gemini free tier
        """
        # OLLAMA CLOUD MODELS - ALL FREE!
        ollama_cloud_free_models = [
            "deepseek-v3.1-671b",  # Best reasoning
            "gpt-oss-120b",  # OpenAI-compatible
            "qwen3-coder-480b",  # Best for code
            "gemini-3-pro-preview",  # Google preview
            "kimi-k2-1t",  # Long context
            "minimax-m2",  # Multi-modal
        ]

        # Try Ollama Cloud first (all FREE!)
        for model_id in ollama_cloud_free_models:
            adapter = self.get_adapter(model_id)
            if adapter:
                logger.info(f"Using FREE Ollama Cloud adapter: {model_id}")
                return adapter

        # Fallback to Google Gemini free tier
        gemini_free_models = [
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro",  # Limited free
        ]

        for model_id in gemini_free_models:
            adapter = self.get_adapter(model_id)
            if adapter:
                logger.info(f"Using FREE Gemini adapter: {model_id}")
                return adapter

        logger.warning("No free tier adapter available")
        return None

    async def health_check_all(self) -> dict[str, Any]:
        """Check health of all initialized adapters."""
        results = {}

        for model_id, adapter in self._adapters.items():
            try:
                health = await adapter.health_check()
                results[model_id] = health
            except Exception as e:
                results[model_id] = {"error": str(e)}

        return {
            "adapters": results,
            "total_adapters": len(self._adapters),
            "providers_with_keys": sum(
                1 for k in self._api_keys.values() if k
            ),
        }

    def get_budget_stats(self) -> dict[str, Any]:
        """Get budget statistics for all providers."""
        return {
            provider.value: budget.get_stats()
            for provider, budget in self._budgets.items()
        }

    def list_available_models(self) -> list[dict[str, Any]]:
        """List all models with availability status."""
        models = []

        for model_id, config in ALL_CLOUD_MODELS.items():
            provider = config.provider
            has_key = bool(self._api_keys.get(provider, ""))

            models.append(
                {
                    "model_id": model_id,
                    "display_name": config.display_name,
                    "provider": provider.value,
                    "context_window": config.context_window,
                    "is_free_tier": config.is_free_tier,
                    "available": has_key,
                    "rate_limit_rpm": config.rate_limit_rpm,
                }
            )

        return sorted(
            models, key=lambda x: (not x["is_free_tier"], x["provider"])
        )

    async def close_all(self) -> None:
        """Close all adapter HTTP clients."""
        for model_id, adapter in self._adapters.items():
            try:
                await adapter.close()
            except Exception as e:
                logger.warning(f"Error closing adapter {model_id}: {e}")

        self._adapters.clear()
        logger.info("All cloud adapters closed")


# =============================================================================
# Global Factory Instance
# =============================================================================


_global_factory: Optional[CloudAdapterFactory] = None


def get_cloud_factory() -> CloudAdapterFactory:
    """Get or create global factory instance."""
    global _global_factory
    if _global_factory is None:
        _global_factory = CloudAdapterFactory()
    return _global_factory


async def get_cloud_adapter(
    model_id: str = "gemini-1.5-flash",
) -> Optional[BaseCloudAdapter]:
    """Convenience function to get an adapter from global factory."""
    factory = get_cloud_factory()
    return factory.get_adapter(model_id)


async def get_free_cloud_adapter() -> Optional[BaseCloudAdapter]:
    """Convenience function to get best free tier adapter."""
    factory = get_cloud_factory()
    return factory.get_free_adapter()
