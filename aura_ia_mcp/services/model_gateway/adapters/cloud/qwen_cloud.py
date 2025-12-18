"""
Qwen (Alibaba) Cloud Adapter for Aura IA MCP.

Alibaba's Qwen models via DashScope API.
API: https://dashscope.aliyuncs.com

Features:
- Qwen-Turbo: Fast, 8K context, affordable
- Qwen-Plus: Balanced, 32K context
- Qwen-Max: Best quality, 32K context
- Excellent for Chinese and multilingual tasks
"""

import logging
import os
from typing import Any, Optional

import httpx

from .base_cloud import (
    ALIBABA_MODELS,
    BaseCloudAdapter,
    CloudCircuitBreaker,
    CloudModelConfig,
    CloudProvider,
    CloudProviderBudget,
    CloudSecurityManager,
)

logger = logging.getLogger(__name__)


class QwenCloudAdapter(BaseCloudAdapter):
    """
    Qwen (Alibaba DashScope) API adapter.

    Models:
    - qwen-turbo: Fast and affordable (8K)
    - qwen-plus: Balanced performance (32K)
    - qwen-max: Best quality (32K)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "qwen-turbo",
        provider_budget: Optional[CloudProviderBudget] = None,
        circuit_breaker: Optional[CloudCircuitBreaker] = None,
        security_manager: Optional[CloudSecurityManager] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")

        if not self.api_key:
            logger.warning(
                "No DashScope API key found. Set DASHSCOPE_API_KEY environment variable. "
                "Get key at: https://dashscope.console.aliyun.com/"
            )

        model_config = ALIBABA_MODELS.get(model_id)
        if not model_config:
            model_config = ALIBABA_MODELS["qwen-turbo"]

        if provider_budget is None:
            provider_budget = CloudProviderBudget(
                provider=CloudProvider.ALIBABA,
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
        Call DashScope API.

        POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation

        DashScope uses a unique format (not OpenAI-compatible).
        """
        client = await self._get_client()

        # Build messages
        messages = kwargs.get("messages", [])
        if not messages:
            messages = [{"role": "user", "content": prompt}]

        # Add system message if provided
        system = kwargs.get("system_instruction")
        if system:
            messages = [{"role": "system", "content": system}] + messages

        # DashScope-specific request format
        request_body = {
            "model": self.model_config.model_id,
            "input": {
                "messages": messages,
            },
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": 0.95,
                "result_format": "message",  # Get structured response
            },
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
            raise QwenRateLimitError("Rate limit exceeded")

        if response.status_code != 200:
            raise QwenAPIError(
                f"Qwen error ({response.status_code}): {response.text}"
            )

        data = response.json()

        # Check for API-level errors
        if "code" in data and data["code"] != "Success":
            error_msg = data.get("message", "Unknown error")
            raise QwenAPIError(f"Qwen API error: {error_msg}")

        # Extract response (DashScope format)
        output = data.get("output", {})

        # result_format=message returns structured response
        choices = output.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            response_text = message.get("content", "")
        else:
            # Fallback to text format
            response_text = output.get("text", "")

        # Token counts
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", self.estimate_tokens(prompt))
        output_tokens = usage.get(
            "output_tokens", self.estimate_tokens(response_text)
        )

        return response_text, input_tokens, output_tokens

    def select_model_for_task(
        self,
        task_type: str = "general",
        context_size: int = 0,
    ) -> str:
        """Select appropriate Qwen model based on task."""
        if task_type in ["simple", "fast", "chat"]:
            return "qwen-turbo"
        elif context_size > 8000:
            return "qwen-plus"
        elif task_type in ["complex", "reasoning", "analysis"]:
            return "qwen-max"
        return "qwen-turbo"  # Default to fast model

    def get_model_info(self) -> dict[str, Any]:
        """Get model information."""
        return {
            "model_id": self.model_config.model_id,
            "display_name": self.model_config.display_name,
            "provider": "alibaba",
            "context_window": self.model_config.context_window,
        }

    @staticmethod
    def get_available_models() -> list[dict[str, Any]]:
        """Get all available Qwen models."""
        return [
            {
                "model_id": config.model_id,
                "display_name": config.display_name,
                "context_window": config.context_window,
                "pricing": {
                    "input_per_1k": config.input_cost_per_1k,
                    "output_per_1k": config.output_cost_per_1k,
                },
            }
            for config in ALIBABA_MODELS.values()
        ]


class QwenAPIError(Exception):
    """Qwen API error."""

    pass


class QwenRateLimitError(QwenAPIError):
    """Rate limit exceeded."""

    pass


def create_qwen_adapter(
    model_id: str = "qwen-turbo",
    api_key: Optional[str] = None,
) -> QwenCloudAdapter:
    """Factory function for Qwen adapter."""
    return QwenCloudAdapter(api_key=api_key, model_id=model_id)
