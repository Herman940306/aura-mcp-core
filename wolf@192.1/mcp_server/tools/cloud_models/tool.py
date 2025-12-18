"""
Cloud Models MCP Tool.

Query cloud AI models with intelligent routing.
FREE TIER FIRST - Prioritizes Gemini free models!

Resource Offloading Rules:
1. ALWAYS check local Ollama first (unless force_cloud=True)
2. Route to cloud when local unavailable or context too large
3. Track costs per provider
4. Respect rate limits

Usage:
    result = run({"prompt": "Hello!", "model": "gemini-1.5-flash"})
"""

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def run(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Run cloud model generation.

    Args:
        payload: Dict with prompt, model, temperature, max_tokens, force_cloud

    Returns:
        Dict with response, model, tokens, latency, routing info
    """
    start = time.time()

    prompt = payload.get("prompt", "")
    if not prompt:
        return {
            "success": False,
            "error": "Prompt is required",
            "latency_ms": 0,
        }

    model = payload.get("model", "gemini-1.5-flash")
    temperature = payload.get("temperature", 0.3)
    max_tokens = payload.get("max_tokens", 2048)
    force_cloud = payload.get("force_cloud", False)
    system_instruction = payload.get("system_instruction")

    # Run async generation
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _async_generate(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                force_cloud=force_cloud,
                system_instruction=system_instruction,
            )
        )
    except RuntimeError:
        # No event loop - create one
        result = asyncio.run(
            _async_generate(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                force_cloud=force_cloud,
                system_instruction=system_instruction,
            )
        )

    latency_ms = int((time.time() - start) * 1000)
    result["latency_ms"] = latency_ms

    return result


async def _async_generate(
    prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    force_cloud: bool,
    system_instruction: str | None,
) -> dict[str, Any]:
    """Async generation via unified gateway."""
    try:
        from aura_ia_mcp.services.model_gateway.adapters.cloud.gateway import (
            get_unified_gateway,
        )

        gateway = get_unified_gateway()

        result = await gateway.generate(
            prompt=prompt,
            model=model,
            user_id="mcp_tool",
            temperature=temperature,
            max_tokens=max_tokens,
            force_cloud=force_cloud,
            system_instruction=system_instruction,
        )

        if result.get("success"):
            return {
                "success": True,
                "response": result.get("response", ""),
                "model": result.get("model", model),
                "provider": result.get("provider", "unknown"),
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "is_free_tier": result.get("is_free_tier", True),
                "is_local": result.get("is_local", False),
                "routing": result.get("routing", {}),
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "provider": result.get("provider", "unknown"),
            }

    except ImportError as e:
        logger.warning("Cloud gateway not available: %s", e)
        return await _fallback_generate(
            prompt, model, temperature, max_tokens, system_instruction
        )
    except (RuntimeError, OSError, ValueError) as e:
        logger.error("Cloud generation error: %s", e)
        return {
            "success": False,
            "error": str(e),
        }


async def _fallback_generate(
    prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    system_instruction: str | None,
) -> dict[str, Any]:
    """Fallback generation directly via Gemini adapter."""
    try:
        from aura_ia_mcp.services.model_gateway.adapters.cloud.gemini import (
            create_gemini_adapter,
        )

        adapter = create_gemini_adapter(model_id=model)
        result = await adapter.generate(
            prompt=prompt,
            user_id="mcp_tool",
            temperature=temperature,
            max_tokens=max_tokens,
            system_instruction=system_instruction,
        )

        return {
            "success": result.get("success", False),
            "response": result.get("response", ""),
            "model": model,
            "provider": "google",
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "is_free_tier": True,
            "is_fallback": True,
        }
    except (RuntimeError, OSError, ValueError, ImportError) as e:
        return {
            "success": False,
            "error": f"Fallback failed: {e}",
        }
