"""
Kimi (Moonshot) K2 Adapter for Aura IA MCP.

Moonshot AI's Kimi is known for long-context capabilities.
API: https://api.moonshot.cn

Features:
- 8K, 32K, and 128K context windows
- OpenAI-compatible API format
- Competitive pricing
"""

import logging
import os
from typing import Any, Optional

import httpx

from .base_cloud import (
    MOONSHOT_MODELS,
    BaseCloudAdapter,
    CloudCircuitBreaker,
    CloudModelConfig,
    CloudProvider,
    CloudProviderBudget,
    CloudSecurityManager,
)

logger = logging.getLogger(__name__)


class KimiAdapter(BaseCloudAdapter):
    """
    Kimi (Moonshot) K2 API adapter.

    Uses OpenAI-compatible API format.
    Models:
    - moonshot-v1-8k (fast, 8K context)
    - moonshot-v1-32k (balanced, 32K context)
    - moonshot-v1-128k (long context, 128K)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "kimi-k2-8k",
        provider_budget: Optional[CloudProviderBudget] = None,
        circuit_breaker: Optional[CloudCircuitBreaker] = None,
        security_manager: Optional[CloudSecurityManager] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.environ.get("MOONSHOT_API_KEY", "")

        if not self.api_key:
            logger.warning(
                "No Moonshot API key found. Set MOONSHOT_API_KEY environment variable. "
                "Get key at: https://platform.moonshot.cn/"
            )

        model_config = MOONSHOT_MODELS.get(model_id)
        if not model_config:
            model_config = MOONSHOT_MODELS["kimi-k2-8k"]

        if provider_budget is None:
            provider_budget = CloudProviderBudget(
                provider=CloudProvider.MOONSHOT,
                daily_budget_usd=5.0,
                daily_request_limit=10000,
            )

        super().__init__(
            model_config=model_config,
            api_key=self.api_key,
            provider_budget=provider_budget,
            circuit_breaker=circuit_breaker,
            security_manager=security_manager,
        )

        self.timeout = timeout
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def _call_api(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> tuple[str, int, int]:
        """
        Call Moonshot API (OpenAI-compatible format).

        POST https://api.moonshot.cn/v1/chat/completions
        """
        client = await self._get_client()

        # Build messages in OpenAI format
        messages = kwargs.get("messages", [])
        if not messages:
            messages = [{"role": "user", "content": prompt}]

        # Prepend system message if provided
        system = kwargs.get("system_instruction")
        if system:
            messages = [{"role": "system", "content": system}] + messages

        request_body = {
            "model": self.model_config.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 0.95,
        }

        response = await client.post(
            self.model_config.api_endpoint,
            json=request_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        if response.status_code == 429:
            raise KimiRateLimitError("Rate limit exceeded")

        if response.status_code != 200:
            raise KimiAPIError(
                f"Kimi error ({response.status_code}): {response.text}"
            )

        data = response.json()

        # Extract response (OpenAI format)
        choices = data.get("choices", [])
        if not choices:
            raise KimiAPIError("No choices in response")

        message = choices[0].get("message", {})
        response_text = message.get("content", "")

        # Token counts
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", self.estimate_tokens(prompt))
        output_tokens = usage.get(
            "completion_tokens", self.estimate_tokens(response_text)
        )

        return response_text, input_tokens, output_tokens

    def select_model_for_context(self, token_count: int) -> str:
        """Select appropriate model based on context size."""
        if token_count <= 6000:
            return "kimi-k2-8k"
        elif token_count <= 28000:
            return "kimi-k2-32k"
        else:
            return "kimi-k2-128k"

    def get_model_info(self) -> dict[str, Any]:
        """Get model information."""
        return {
            "model_id": self.model_config.model_id,
            "display_name": self.model_config.display_name,
            "provider": "moonshot",
            "context_window": self.model_config.context_window,
        }

    @staticmethod
    def get_available_models() -> list[dict[str, Any]]:
        """Get all available Kimi models."""
        return [
            {
                "model_id": config.model_id,
                "display_name": config.display_name,
                "context_window": config.context_window,
            }
            for config in MOONSHOT_MODELS.values()
        ]


class KimiAPIError(Exception):
    """Kimi API error."""

    pass


class KimiRateLimitError(KimiAPIError):
    """Rate limit exceeded."""

    pass


def create_kimi_adapter(
    model_id: str = "kimi-k2-8k",
    api_key: Optional[str] = None,
) -> KimiAdapter:
    """Factory function for Kimi adapter."""
    return KimiAdapter(api_key=api_key, model_id=model_id)
