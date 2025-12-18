"""
Model Management MCP Tool.

Provides model listing, health checking, budget tracking, and recommendations.

Actions:
- list_models: List all available models (local + cloud)
- get_model_info: Get details for a specific model
- health_check: Check health of model backends
- budget_stats: Get budget/usage statistics per provider
- recommend_model: Get model recommendation based on task

FREE TIER FIRST - Always prioritizes free models!
"""

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


# Task-to-model recommendations (FREE TIER FIRST!)
MODEL_RECOMMENDATIONS: dict[str, list[dict[str, Any]]] = {
    "code": [
        {
            "model": "gemini-1.5-pro",
            "reason": "Best for code - 2M context, FREE tier (50/day)",
            "is_free": True,
        },
        {
            "model": "gemini-1.5-flash",
            "reason": "Fast code completion - FREE tier (1500/day)",
            "is_free": True,
        },
        {
            "model": "qwen3-coder-480b",
            "reason": "Qwen3 Coder 480B - Best for code (128K context)",
            "is_free": False,
        },
        {
            "model": "qwen-max",
            "reason": "Strong code capabilities",
            "is_free": False,
        },
    ],
    "chat": [
        {
            "model": "gemini-1.5-flash",
            "reason": "Fast conversational - FREE tier (1500/day)",
            "is_free": True,
        },
        {
            "model": "gemini-1.5-flash-8b",
            "reason": "Lightweight chat - FREE tier (1500/day)",
            "is_free": True,
        },
        {
            "model": "kimi-k2-8k",
            "reason": "Good chat, 8K context",
            "is_free": False,
        },
    ],
    "analysis": [
        {
            "model": "gemini-1.5-pro",
            "reason": "Best analysis - 2M context FREE (50/day)",
            "is_free": True,
        },
        {
            "model": "gemini-2.0-flash-exp",
            "reason": "Experimental - strong analysis FREE",
            "is_free": True,
        },
        {
            "model": "kimi-k2-128k",
            "reason": "Long context analysis",
            "is_free": False,
        },
    ],
    "translation": [
        {
            "model": "gemini-1.5-flash",
            "reason": "Multi-language - FREE tier (1500/day)",
            "is_free": True,
        },
        {
            "model": "qwen-turbo",
            "reason": "Strong Chinese/English translation",
            "is_free": False,
        },
        {
            "model": "minimax-m2",
            "reason": "Chinese specialist",
            "is_free": False,
        },
    ],
    "general": [
        {
            "model": "gemini-1.5-flash",
            "reason": "Best all-around - FREE tier (1500/day)",
            "is_free": True,
        },
        {
            "model": "gemini-2.0-flash-exp",
            "reason": "Cutting edge - FREE tier",
            "is_free": True,
        },
        {
            "model": "gemini-1.5-pro",
            "reason": "Most capable - FREE tier (50/day)",
            "is_free": True,
        },
    ],
}


def run(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Run model management action.

    Args:
        payload: Dict with action and parameters

    Returns:
        Dict with action results
    """
    start = time.time()

    action = payload.get("action", "list_models")

    handlers = {
        "list_models": _handle_list_models,
        "get_model_info": _handle_get_model_info,
        "health_check": _handle_health_check,
        "budget_stats": _handle_budget_stats,
        "recommend_model": _handle_recommend_model,
    }

    handler = handlers.get(action)
    if not handler:
        return {
            "success": False,
            "error": f"Unknown action: {action}",
            "available_actions": list(handlers.keys()),
        }

    result = handler(payload)

    latency_ms = int((time.time() - start) * 1000)
    result["latency_ms"] = latency_ms
    result["action"] = action

    return result


def _handle_list_models(_payload: dict[str, Any]) -> dict[str, Any]:
    """List all available models."""
    try:
        from aura_ia_mcp.services.model_gateway.adapters.cloud.factory import (
            get_cloud_factory,
        )

        factory = get_cloud_factory()
        models = factory.list_available_models()

        # Separate free and paid
        free_models = [m for m in models if m.get("is_free_tier")]
        paid_models = [m for m in models if not m.get("is_free_tier")]

        return {
            "success": True,
            "models": models,
            "total": len(models),
            "free_tier_count": len(free_models),
            "paid_count": len(paid_models),
            "free_models": [m["model_id"] for m in free_models],
        }
    except ImportError:
        # Fallback to static list
        return {
            "success": True,
            "models": _get_static_model_list(),
            "note": "Static list - factory not available",
        }


def _handle_get_model_info(payload: dict[str, Any]) -> dict[str, Any]:
    """Get details for a specific model."""
    model_id = payload.get("model_id")
    if not model_id:
        return {
            "success": False,
            "error": "model_id is required for get_model_info",
        }

    try:
        from aura_ia_mcp.services.model_gateway.adapters.cloud.base_cloud import (
            ALL_CLOUD_MODELS,
        )

        config = ALL_CLOUD_MODELS.get(model_id)
        if not config:
            return {
                "success": False,
                "error": f"Unknown model: {model_id}",
                "available_models": list(ALL_CLOUD_MODELS.keys()),
            }

        return {
            "success": True,
            "model_info": {
                "model_id": config.model_id,
                "display_name": config.display_name,
                "provider": config.provider.value,
                "context_window": config.context_window,
                "rate_limit_rpm": config.rate_limit_rpm,
                "rate_limit_tpm": config.rate_limit_tpm,
                "is_free_tier": config.is_free_tier,
                "free_tier_daily_limit": config.free_tier_daily_limit,
                "input_cost_per_1k": config.input_cost_per_1k,
                "output_cost_per_1k": config.output_cost_per_1k,
                "api_endpoint": config.api_endpoint,
            },
        }
    except ImportError:
        return {
            "success": False,
            "error": "Model info not available - cloud module not loaded",
        }


def _handle_health_check(_payload: dict[str, Any]) -> dict[str, Any]:
    """Check health of all backends."""
    try:
        from aura_ia_mcp.services.model_gateway.adapters.cloud.gateway import (
            get_unified_gateway,
        )

        gateway = get_unified_gateway()

        # Run async health check
        try:
            health = asyncio.get_event_loop().run_until_complete(
                gateway.health_check()
            )
        except RuntimeError:
            health = asyncio.run(gateway.health_check())

        return {
            "success": True,
            "health": health,
        }
    except ImportError:
        return {
            "success": True,
            "health": {
                "local": {"status": "unknown"},
                "cloud": {"status": "unknown"},
                "note": "Gateway not available",
            },
        }


def _handle_budget_stats(_payload: dict[str, Any]) -> dict[str, Any]:
    """Get budget statistics per provider."""
    try:
        from aura_ia_mcp.services.model_gateway.adapters.cloud.factory import (
            get_cloud_factory,
        )

        factory = get_cloud_factory()
        budget_stats = factory.get_budget_stats()

        return {
            "success": True,
            "budget": budget_stats,
            "providers": list(budget_stats.keys()),
        }
    except ImportError:
        return {
            "success": True,
            "budget": {
                "google": {
                    "daily_budget_usd": 0.0,
                    "daily_request_limit": 1500,
                    "note": "FREE TIER",
                },
                "minimax": {"daily_budget_usd": 5.0},
                "moonshot": {"daily_budget_usd": 5.0},
                "alibaba": {"daily_budget_usd": 5.0},
            },
            "note": "Static budget info - factory not available",
        }


def _handle_recommend_model(payload: dict[str, Any]) -> dict[str, Any]:
    """Recommend model based on task type and requirements."""
    task_type = payload.get("task_type", "general")
    prefer_free = payload.get("prefer_free", True)
    context_size = payload.get("context_size", 0)

    recommendations = MODEL_RECOMMENDATIONS.get(
        task_type, MODEL_RECOMMENDATIONS["general"]
    )

    # Filter by context size if specified
    if context_size > 0:
        try:
            from aura_ia_mcp.services.model_gateway.adapters.cloud.base_cloud import (
                ALL_CLOUD_MODELS,
            )

            valid_recs = []
            for rec in recommendations:
                config = ALL_CLOUD_MODELS.get(rec["model"])
                if config and config.context_window >= context_size:
                    rec["context_window"] = config.context_window
                    valid_recs.append(rec)

            if valid_recs:
                recommendations = valid_recs
        except ImportError:
            pass

    # Sort by free tier preference
    if prefer_free:
        recommendations = sorted(
            recommendations, key=lambda x: (not x.get("is_free", False), 0)
        )

    # Pick top recommendation
    top_rec = recommendations[0] if recommendations else None

    return {
        "success": True,
        "recommendation": top_rec,
        "alternatives": (
            recommendations[1:3] if len(recommendations) > 1 else []
        ),
        "task_type": task_type,
        "prefer_free": prefer_free,
        "context_size_required": context_size,
    }


def _get_static_model_list() -> list[dict[str, Any]]:
    """Static fallback model list."""
    return [
        {
            "model_id": "gemini-1.5-flash",
            "display_name": "Gemini 1.5 Flash",
            "provider": "google",
            "is_free_tier": True,
            "rate_limit_rpm": 15,
            "context_window": 1048576,
        },
        {
            "model_id": "gemini-1.5-flash-8b",
            "display_name": "Gemini 1.5 Flash 8B",
            "provider": "google",
            "is_free_tier": True,
            "rate_limit_rpm": 15,
            "context_window": 1048576,
        },
        {
            "model_id": "gemini-2.0-flash-exp",
            "display_name": "Gemini 2.0 Flash Experimental",
            "provider": "google",
            "is_free_tier": True,
            "rate_limit_rpm": 10,
            "context_window": 1048576,
        },
        {
            "model_id": "gemini-1.5-pro",
            "display_name": "Gemini 1.5 Pro",
            "provider": "google",
            "is_free_tier": True,
            "rate_limit_rpm": 2,
            "context_window": 2097152,
        },
        {
            "model_id": "minimax-m2",
            "display_name": "Minimax M2",
            "provider": "minimax",
            "is_free_tier": False,
            "rate_limit_rpm": 60,
            "context_window": 245760,
        },
        {
            "model_id": "kimi-k2-128k",
            "display_name": "Kimi K2 128K",
            "provider": "moonshot",
            "is_free_tier": False,
            "rate_limit_rpm": 60,
            "context_window": 131072,
        },
        {
            "model_id": "qwen-turbo",
            "display_name": "Qwen Turbo",
            "provider": "alibaba",
            "is_free_tier": False,
            "rate_limit_rpm": 60,
            "context_window": 8192,
        },
    ]
