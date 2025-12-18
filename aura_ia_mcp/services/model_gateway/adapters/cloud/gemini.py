"""
Google Gemini Adapter for Aura IA MCP.

FREE TIER FIRST! Prioritizes Gemini free tier models:
- gemini-1.5-flash: 15 RPM, 1500 requests/day FREE
- gemini-1.5-flash-8b: 15 RPM, 1500 requests/day FREE
- gemini-2.0-flash-exp: 10 RPM, 1500 requests/day FREE
- gemini-1.5-pro: 2 RPM, 50 requests/day FREE

Enterprise Features:
- Automatic model fallback (flash → flash-8b → pro)
- Rate limit aware scheduling
- Token counting from API response
- Safety settings configuration
- Streaming support (optional)

API Reference: https://ai.google.dev/api/generate-content
"""

import asyncio
import logging
import os
from typing import Any, Optional

import httpx

from .base_cloud import (
    ALL_CLOUD_MODELS,
    GOOGLE_MODELS,
    BaseCloudAdapter,
    CloudCircuitBreaker,
    CloudModelConfig,
    CloudProvider,
    CloudProviderBudget,
    CloudSecurityManager,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Gemini Safety Settings
# =============================================================================


class GeminiSafetyLevel:
    """Safety settings for Gemini API."""

    # Default: Block only high-probability harmful content
    DEFAULT = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_ONLY_HIGH",
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_ONLY_HIGH",
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_ONLY_HIGH",
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_ONLY_HIGH",
        },
    ]

    # Strict: Block medium and above
    STRICT = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
    ]

    # Permissive: Block only explicit harmful content
    PERMISSIVE = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_ONLY_HIGH",
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_ONLY_HIGH",
        },
    ]


# =============================================================================
# Gemini Adapter
# =============================================================================


class GeminiAdapter(BaseCloudAdapter):
    """
    Google Gemini API adapter with FREE TIER FIRST strategy.

    Automatically manages:
    - Model selection (prioritizes free models)
    - Rate limits (respects 15 RPM for flash)
    - Daily quotas (1500 requests/day free)
    - Token counting from API response
    - Automatic fallback on rate limit
    """

    # Model priority for fallback (free tier first!)
    MODEL_PRIORITY = [
        "gemini-1.5-flash",  # Best free: 15 RPM, 1500/day
        "gemini-1.5-flash-8b",  # Smaller but fast
        "gemini-2.0-flash-exp",  # Experimental, 10 RPM
        "gemini-1.5-pro",  # Powerful but 2 RPM, 50/day
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "gemini-1.5-flash",  # FREE TIER DEFAULT
        provider_budget: Optional[CloudProviderBudget] = None,
        circuit_breaker: Optional[CloudCircuitBreaker] = None,
        security_manager: Optional[CloudSecurityManager] = None,
        safety_settings: Optional[list] = None,
        timeout: float = 60.0,
    ):
        # Get API key from env if not provided
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not self.api_key:
            logger.warning(
                "No Google API key found. Set GOOGLE_API_KEY environment variable. "
                "Get a FREE key at: https://aistudio.google.com/app/apikey"
            )

        # Get model config
        model_config = GOOGLE_MODELS.get(model_id)
        if not model_config:
            logger.warning(
                f"Unknown model {model_id}, defaulting to gemini-1.5-flash"
            )
            model_config = GOOGLE_MODELS["gemini-1.5-flash"]

        # Initialize provider budget if not provided
        if provider_budget is None:
            provider_budget = CloudProviderBudget(
                provider=CloudProvider.GOOGLE,
                daily_budget_usd=0.0,  # Free tier!
                daily_request_limit=1500,
            )

        super().__init__(
            model_config=model_config,
            api_key=self.api_key,
            provider_budget=provider_budget,
            circuit_breaker=circuit_breaker,
            security_manager=security_manager,
        )

        self.safety_settings = safety_settings or GeminiSafetyLevel.DEFAULT
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
        Call Gemini API.

        API format:
        POST /v1beta/models/{model}:generateContent?key={API_KEY}
        {
            "contents": [{"parts": [{"text": "..."}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
            "safetySettings": [...]
        }
        """
        client = await self._get_client()

        # Build request URL
        url = f"{self.model_config.api_endpoint}?key={self.api_key}"

        # Build request body
        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.95,
                "topK": 40,
            },
            "safetySettings": self.safety_settings,
        }

        # Optional system instruction
        system_instruction = kwargs.get("system_instruction")
        if system_instruction:
            request_body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        # Make request
        response = await client.post(
            url,
            json=request_body,
            headers={"Content-Type": "application/json"},
        )

        # Handle errors
        if response.status_code == 429:
            # Rate limited - try fallback model
            raise RateLimitError(
                f"Rate limited on {self.model_config.model_id}"
            )

        if response.status_code != 200:
            error_text = response.text
            raise GeminiAPIError(
                f"Gemini API error ({response.status_code}): {error_text}"
            )

        # Parse response
        data = response.json()

        # Check for safety blocks
        if "candidates" not in data or not data["candidates"]:
            # Check for prompt feedback (safety block)
            if "promptFeedback" in data:
                block_reason = data["promptFeedback"].get(
                    "blockReason", "UNKNOWN"
                )
                raise SafetyBlockError(f"Prompt blocked: {block_reason}")
            raise GeminiAPIError("No candidates in response")

        candidate = data["candidates"][0]

        # Check finish reason
        finish_reason = candidate.get("finishReason", "STOP")
        if finish_reason == "SAFETY":
            safety_ratings = candidate.get("safetyRatings", [])
            raise SafetyBlockError(
                f"Response blocked for safety: {safety_ratings}"
            )

        # Extract text
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        response_text = "".join(part.get("text", "") for part in parts)

        # Get token counts from usage metadata
        usage = data.get("usageMetadata", {})
        input_tokens = usage.get(
            "promptTokenCount", self.estimate_tokens(prompt)
        )
        output_tokens = usage.get(
            "candidatesTokenCount", self.estimate_tokens(response_text)
        )

        return response_text, input_tokens, output_tokens

    async def generate_with_fallback(
        self,
        prompt: str,
        user_id: str = "anonymous",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate with automatic model fallback on rate limit.

        Tries models in priority order:
        1. gemini-1.5-flash (15 RPM)
        2. gemini-1.5-flash-8b (15 RPM)
        3. gemini-2.0-flash-exp (10 RPM)
        4. gemini-1.5-pro (2 RPM)
        """
        current_model_idx = (
            self.MODEL_PRIORITY.index(self.model_config.model_id)
            if self.model_config.model_id in self.MODEL_PRIORITY
            else 0
        )

        for i in range(current_model_idx, len(self.MODEL_PRIORITY)):
            model_id = self.MODEL_PRIORITY[i]
            self.model_config = GOOGLE_MODELS[model_id]

            try:
                result = await self.generate(
                    prompt=prompt,
                    user_id=user_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                if result["success"]:
                    return result

            except RateLimitError:
                logger.warning(
                    f"Rate limited on {model_id}, trying next model..."
                )
                continue
            except Exception as e:
                logger.error(f"Error with {model_id}: {e}")
                continue

        return {
            "success": False,
            "error": "All Gemini models rate limited or unavailable",
        }

    async def generate_stream(
        self,
        prompt: str,
        user_id: str = "anonymous",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ):
        """
        Stream generation (yields chunks).

        Note: Uses streamGenerateContent endpoint.
        """
        # Security validation
        valid, reason = self.security_manager.validate_input(prompt, user_id)
        if not valid:
            yield {"error": reason}
            return

        # Rate limit check
        rate_ok, rate_reason = await self.provider_budget.check_rate_limit(
            self.model_config
        )
        if not rate_ok:
            yield {"error": rate_reason}
            return

        client = await self._get_client()

        # Stream endpoint
        stream_url = (
            self.model_config.api_endpoint.replace(
                ":generateContent", ":streamGenerateContent"
            )
            + f"?key={self.api_key}&alt=sse"
        )

        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
            "safetySettings": self.safety_settings,
        }

        total_text = ""
        input_tokens = 0
        output_tokens = 0

        try:
            async with client.stream(
                "POST", stream_url, json=request_body
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json

                        data = json.loads(line[6:])

                        if "candidates" in data:
                            for candidate in data["candidates"]:
                                if "content" in candidate:
                                    for part in candidate["content"].get(
                                        "parts", []
                                    ):
                                        if "text" in part:
                                            chunk = part["text"]
                                            total_text += chunk
                                            yield {"chunk": chunk}

                        # Update token counts
                        if "usageMetadata" in data:
                            usage = data["usageMetadata"]
                            input_tokens = usage.get("promptTokenCount", 0)
                            output_tokens = usage.get(
                                "candidatesTokenCount", 0
                            )

            # Record usage after stream completes
            await self.provider_budget.record_request(
                self.model_config, input_tokens, output_tokens
            )
            self.circuit_breaker.record_success()

            yield {
                "done": True,
                "total_text": total_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

        except Exception as e:
            self.circuit_breaker.record_failure(str(e))
            yield {"error": str(e)}

    async def count_tokens(self, text: str) -> dict[str, int]:
        """
        Count tokens using Gemini's tokenizer API.

        More accurate than estimation.
        """
        client = await self._get_client()

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_config.model_id}:countTokens?key={self.api_key}"

        try:
            response = await client.post(
                url,
                json={"contents": [{"parts": [{"text": text}]}]},
            )

            if response.status_code == 200:
                data = response.json()
                return {"tokens": data.get("totalTokens", 0), "exact": True}

        except Exception as e:
            logger.warning(f"Token count API failed: {e}")

        # Fallback to estimation
        return {"tokens": self.estimate_tokens(text), "exact": False}

    def get_model_info(self) -> dict[str, Any]:
        """Get current model information."""
        return {
            "model_id": self.model_config.model_id,
            "display_name": self.model_config.display_name,
            "context_window": self.model_config.context_window,
            "rate_limit_rpm": self.model_config.rate_limit_rpm,
            "is_free_tier": self.model_config.is_free_tier,
            "free_tier_daily_limit": self.model_config.free_tier_daily_limit,
            "api_endpoint": self.model_config.api_endpoint,
        }

    @staticmethod
    def get_available_models() -> list[dict[str, Any]]:
        """Get all available Gemini models."""
        return [
            {
                "model_id": config.model_id,
                "display_name": config.display_name,
                "context_window": config.context_window,
                "rate_limit_rpm": config.rate_limit_rpm,
                "is_free_tier": config.is_free_tier,
                "free_tier_daily_limit": config.free_tier_daily_limit,
            }
            for config in GOOGLE_MODELS.values()
        ]


# =============================================================================
# Custom Exceptions
# =============================================================================


class GeminiAPIError(Exception):
    """General Gemini API error."""

    pass


class RateLimitError(GeminiAPIError):
    """Rate limit exceeded error."""

    pass


class SafetyBlockError(GeminiAPIError):
    """Content blocked for safety reasons."""

    pass


# =============================================================================
# Factory Function
# =============================================================================


def create_gemini_adapter(
    model_id: str = "gemini-1.5-flash",
    api_key: Optional[str] = None,
) -> GeminiAdapter:
    """
    Factory function to create a Gemini adapter.

    Defaults to FREE TIER model (gemini-1.5-flash).

    Usage:
        adapter = create_gemini_adapter()
        result = await adapter.generate("Hello!")
    """
    return GeminiAdapter(
        api_key=api_key,
        model_id=model_id,
    )
