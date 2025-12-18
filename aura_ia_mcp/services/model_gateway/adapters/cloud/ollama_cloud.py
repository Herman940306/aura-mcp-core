"""
Ollama Cloud Adapter for Aura IA MCP.

This adapter provides access to FREE cloud-hosted models via Ollama's
infrastructure. All models are FREE to use with no API key required.

Supported Models (via `ollama run` CLI):
- deepseek-v3.1:671b-cloud - Advanced reasoning, 128K context
- gpt-oss:120b-cloud - OpenAI-compatible, 128K context
- qwen3-coder:480b-cloud - Code generation specialist, 128K context
- gemini-3-pro-preview:latest - Google's preview, 2M context
- kimi-k2:1t-cloud - Long context flagship, 1M context
- minimax-m2:latest-cloud - Multi-modal specialist, 245K context

All models are FREE via Ollama Cloud infrastructure!
No API key required - just use `ollama run <model>` CLI or HTTP API.
"""

import logging
import os
from typing import Any

import httpx

from .base_cloud import (
    OLLAMA_CLOUD_MODELS,
    BaseCloudAdapter,
    CloudCircuitBreaker,
    CloudProvider,
    CloudProviderBudget,
    CloudSecurityManager,
)

logger = logging.getLogger(__name__)

# Default Ollama API endpoint (can be overridden)
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")


class OllamaCloudAdapter(BaseCloudAdapter):
    """
    Adapter for FREE Ollama Cloud models.

    Uses Ollama's HTTP API to access cloud-hosted models.
    All models are FREE with no cost tracking required.

    Features:
    - FREE - no API key required
    - Same Ollama API as local models
    - Automatic model download if not cached
    - Enterprise-grade reliability patterns (via BaseCloudAdapter)
    """

    def __init__(
        self,
        model_id: str = "deepseek-v3.1-671b",
        base_url: str | None = None,
        provider_budget: CloudProviderBudget | None = None,
        circuit_breaker: CloudCircuitBreaker | None = None,
        security_manager: CloudSecurityManager | None = None,
        timeout: float = 120.0,
    ):
        # Get model config
        model_config = OLLAMA_CLOUD_MODELS.get(model_id)
        if not model_config:
            raise ValueError(f"Unknown Ollama Cloud model: {model_id}")

        # Store model_id for easy access
        self.model_id = model_id

        super().__init__(
            model_config=model_config,
            api_key="ollama-cloud-free",  # No API key needed - FREE!
            provider_budget=provider_budget
            or CloudProviderBudget(
                provider=CloudProvider.OLLAMA_CLOUD,
                daily_budget_usd=0.0,  # FREE!
                daily_request_limit=100000,  # High limit
            ),
            circuit_breaker=circuit_breaker,
            security_manager=security_manager,
        )

        self.base_url = base_url or OLLAMA_API_URL
        self.timeout = timeout

        # HTTP client for Ollama API
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout=timeout),
        )

        # Map model_id to Ollama model name (CLI format)
        self._ollama_model_map = {
            "deepseek-v3.1-671b": "deepseek-v3.1:671b-cloud",
            "gpt-oss-120b": "gpt-oss:120b-cloud",
            "qwen3-coder-480b": "qwen3-coder:480b-cloud",
            "gemini-3-pro-preview": "gemini-3-pro-preview:latest",
            "kimi-k2-1t": "kimi-k2:1t-cloud",
            "minimax-m2": "minimax-m2:latest-cloud",
        }

        logger.info(
            "OllamaCloudAdapter initialized: %s (FREE via Ollama at %s)",
            model_id,
            self.base_url,
        )

    def _get_ollama_model_name(self) -> str:
        """Get the Ollama CLI-compatible model name."""
        return self._ollama_model_map.get(self.model_id, self.model_id)

    async def _call_api(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> tuple[str, int, int]:
        """
        Call the Ollama Cloud API.

        This implements the abstract method from BaseCloudAdapter.

        Returns: (response_text, input_tokens, output_tokens)
        """
        ollama_model = self._get_ollama_model_name()

        payload: dict[str, Any] = {
            "model": ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        # Add any additional Ollama options
        if "system" in kwargs:
            payload["system"] = kwargs["system"]
        if "context" in kwargs:
            payload["context"] = kwargs["context"]

        response = await self._client.post(
            "/api/generate",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        # Extract response
        text = data.get("response", "")
        prompt_eval_count = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)

        return text, prompt_eval_count, eval_count

    async def health_check(self) -> dict[str, Any]:
        """Check Ollama Cloud service health."""
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()

            return {
                "status": "healthy",
                "provider": "ollama_cloud",
                "model": self.model_id,
                "is_free": True,
                "base_url": self.base_url,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "provider": "ollama_cloud",
                "model": self.model_id,
            }

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()

    async def list_available_models(self) -> list[str]:
        """List all available Ollama Cloud models."""
        return list(OLLAMA_CLOUD_MODELS.keys())


def create_ollama_cloud_adapter(
    model_id: str = "deepseek-v3.1-671b",
    **kwargs: Any,
) -> OllamaCloudAdapter:
    """
    Factory function to create an OllamaCloudAdapter.

    All Ollama Cloud models are FREE!

    Args:
        model_id: Model ID (deepseek-v3.1-671b, gpt-oss-120b, etc.)
        **kwargs: Additional adapter options

    Returns:
        Configured OllamaCloudAdapter
    """
    return OllamaCloudAdapter(model_id=model_id, **kwargs)
