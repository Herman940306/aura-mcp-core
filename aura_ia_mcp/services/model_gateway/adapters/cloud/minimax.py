"""
Minimax M2 Adapter for Aura IA MCP.

Minimax is a Chinese AI company with strong text/image capabilities.
API: https://api.minimax.chat

Features:
- Large context windows (up to 245K tokens)
- Competitive pricing
- Good for Chinese language tasks
"""

import logging
import os
from typing import Any, Optional

import httpx

from .base_cloud import (
    MINIMAX_MODELS,
    BaseCloudAdapter,
    CloudCircuitBreaker,
    CloudModelConfig,
    CloudProvider,
    CloudProviderBudget,
    CloudSecurityManager,
)

logger = logging.getLogger(__name__)


class MinimaxAdapter(BaseCloudAdapter):
    """
    Minimax M2 API adapter.

    Supports:
    - abab6.5-chat (default)
    - abab5.5-chat (faster)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        group_id: Optional[str] = None,  # Minimax requires group_id
        model_id: str = "minimax-m2",
        provider_budget: Optional[CloudProviderBudget] = None,
        circuit_breaker: Optional[CloudCircuitBreaker] = None,
        security_manager: Optional[CloudSecurityManager] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.group_id = group_id or os.environ.get("MINIMAX_GROUP_ID", "")

        if not self.api_key:
            logger.warning(
                "No Minimax API key found. Set MINIMAX_API_KEY environment variable."
            )

        model_config = MINIMAX_MODELS.get(model_id)
        if not model_config:
            model_config = MINIMAX_MODELS["minimax-m2"]

        if provider_budget is None:
            provider_budget = CloudProviderBudget(
                provider=CloudProvider.MINIMAX,
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
        Call Minimax API.

        Format:
        POST https://api.minimax.chat/v1/text/chatcompletion_pro?GroupId={group_id}
        """
        client = await self._get_client()

        url = f"{self.model_config.api_endpoint}?GroupId={self.group_id}"

        # Minimax uses a message format
        messages = kwargs.get("messages", [])
        if not messages:
            messages = [{"sender_type": "USER", "text": prompt}]

        request_body = {
            "model": self.model_config.model_id,
            "messages": messages,
            "tokens_to_generate": max_tokens,
            "temperature": temperature,
            "top_p": 0.95,
        }

        # Optional system prompt as bot setting
        system = kwargs.get("system_instruction")
        if system:
            request_body["bot_setting"] = [
                {"bot_name": "assistant", "content": system}
            ]

        response = await client.post(
            url,
            json=request_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        if response.status_code != 200:
            raise MinimaxAPIError(
                f"Minimax error ({response.status_code}): {response.text}"
            )

        data = response.json()

        # Check for errors in response
        if data.get("base_resp", {}).get("status_code", 0) != 0:
            error_msg = data.get("base_resp", {}).get(
                "status_msg", "Unknown error"
            )
            raise MinimaxAPIError(f"Minimax API error: {error_msg}")

        # Extract response
        reply = data.get("reply", "")

        # Token counts
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", self.estimate_tokens(prompt))
        output_tokens = usage.get(
            "completion_tokens", self.estimate_tokens(reply)
        )

        return reply, input_tokens, output_tokens

    def get_model_info(self) -> dict[str, Any]:
        """Get model information."""
        return {
            "model_id": self.model_config.model_id,
            "display_name": self.model_config.display_name,
            "provider": "minimax",
            "context_window": self.model_config.context_window,
        }


class MinimaxAPIError(Exception):
    """Minimax API error."""

    pass


def create_minimax_adapter(
    model_id: str = "minimax-m2",
    api_key: Optional[str] = None,
    group_id: Optional[str] = None,
) -> MinimaxAdapter:
    """Factory function for Minimax adapter."""
    return MinimaxAdapter(
        api_key=api_key, group_id=group_id, model_id=model_id
    )
