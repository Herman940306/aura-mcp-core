"""
Aura IA Chat Router

Intelligent routing of chat messages to appropriate models based on:
- Intent detection (mode classification)
- Model capability matching
- Resource-aware model selection

PRD Section 8.11 compliant - MCP Concierge integration
PRD Section 8.13 compliant - Ollama Agent Integration
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from .lifecycle import (
    MODE_TO_MODEL,
    MODEL_CONFIGS,
    ChatMode,
    ModelLifecycleManager,
    get_model_manager,
)

logger = logging.getLogger(__name__)


# Intent patterns for mode detection
INTENT_PATTERNS: dict[ChatMode, list[re.Pattern]] = {
    ChatMode.MCP_COMMAND: [
        re.compile(
            r"\b(run|execute|call|invoke|trigger)\b.*\b(tool|command|function|mcp)\b",
            re.I,
        ),
        re.compile(r"\b(mcp|tool)\b.*\b(call|execute|run)\b", re.I),
        re.compile(
            r"\b(list|show|get)\b.*\b(tools|commands|functions)\b", re.I
        ),
        re.compile(r"^/\w+", re.I),  # Slash commands
        re.compile(r"\b(check|get|show)\s+(health|status|metrics)\b", re.I),
        re.compile(r"\bdiagnose\b", re.I),
    ],
    ChatMode.DEBUG: [
        re.compile(r"\b(debug|trace|inspect|diagnose)\b", re.I),
        re.compile(
            r"\b(error|exception|bug|issue|problem)\b.*\b(fix|solve|help)\b",
            re.I,
        ),
        re.compile(r"\b(stack\s*trace|traceback)\b", re.I),
        re.compile(r"\b(why|what)\b.*\b(fail|error|crash|broke)\b", re.I),
        re.compile(
            r"\b(code|function|class|module)\b.*\b(not\s+work|broken|wrong)\b",
            re.I,
        ),
    ],
    ChatMode.DEBATE: [
        re.compile(r"\b(debate|argue|discuss|compare)\b", re.I),
        re.compile(r"\bpros?\s+(and|&|vs)\s+cons?\b", re.I),
        re.compile(r"\b(which|what)\s+is\s+better\b", re.I),
        re.compile(r"\bstart\s+debate\b", re.I),
        re.compile(r"\bmodel\s+vs\s+model\b", re.I),
    ],
    ChatMode.CONCIERGE: [
        re.compile(r"\b(help|assist|guide|explain|teach)\b", re.I),
        re.compile(r"\b(how|why|what|when|where)\b.*\?", re.I),
        re.compile(r"\b(recommend|suggest|advise)\b", re.I),
        re.compile(r"\b(tell\s+me|explain|describe)\b", re.I),
        re.compile(r"\b(plan|strategy|approach)\b", re.I),
        re.compile(r"\b(think|reason|analyze)\b", re.I),
    ],
    # CHAT is the default, so no patterns needed
}

# Keywords that boost certain modes
MODE_KEYWORDS: dict[ChatMode, set[str]] = {
    ChatMode.MCP_COMMAND: {
        "tool",
        "mcp",
        "command",
        "execute",
        "run",
        "invoke",
        "function",
    },
    ChatMode.DEBUG: {
        "debug",
        "error",
        "bug",
        "fix",
        "trace",
        "exception",
        "crash",
    },
    ChatMode.DEBATE: {"debate", "compare", "versus", "vs", "argue", "discuss"},
    ChatMode.CONCIERGE: {
        "help",
        "explain",
        "why",
        "how",
        "recommend",
        "guide",
        "think",
    },
    ChatMode.CHAT: {"hi", "hello", "hey", "thanks", "bye", "ok", "yes", "no"},
}


@dataclass
class RoutingDecision:
    """Result of chat routing decision."""

    mode: ChatMode
    model: str
    confidence: float
    reasoning: str
    is_fallback: bool = False
    detected_keywords: list[str] = None

    def __post_init__(self):
        if self.detected_keywords is None:
            self.detected_keywords = []


@dataclass
class ChatRequest:
    """Incoming chat request."""

    message: str
    user_id: str = "default"
    session_id: str = "default"
    explicit_mode: Optional[ChatMode] = None
    explicit_model: Optional[str] = None
    context: Optional[dict] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ChatRouter:
    """
    Routes chat messages to appropriate models based on intent.

    Routing Priority:
    1. Explicit model override (if specified)
    2. Explicit mode override (if specified)
    3. Intent-based mode detection
    4. Default to CHAT mode (phi3.5 for fast responses)
    """

    def __init__(self, model_manager: Optional[ModelLifecycleManager] = None):
        self._model_manager = model_manager
        self._routing_history: list[RoutingDecision] = []

    async def get_model_manager(self) -> ModelLifecycleManager:
        """Get model manager, initializing if needed."""
        if self._model_manager is None:
            self._model_manager = await get_model_manager()
        return self._model_manager

    def detect_mode(
        self, message: str
    ) -> tuple[ChatMode, float, str, list[str]]:
        """
        Detect the chat mode from message content.
        Returns (mode, confidence, reasoning, keywords).
        """
        message_lower = message.lower()
        words = set(re.findall(r"\w+", message_lower))

        # Score each mode
        scores: dict[ChatMode, float] = {mode: 0.0 for mode in ChatMode}
        detected_keywords: dict[ChatMode, list[str]] = {
            mode: [] for mode in ChatMode
        }

        # Pattern matching
        for mode, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(message):
                    scores[mode] += 2.0
                    detected_keywords[mode].append(
                        f"pattern:{pattern.pattern[:30]}..."
                    )

        # Keyword matching
        for mode, keywords in MODE_KEYWORDS.items():
            matching = words & keywords
            if matching:
                scores[mode] += len(matching) * 0.5
                detected_keywords[mode].extend(matching)

        # Question marks boost CONCIERGE
        if "?" in message:
            scores[ChatMode.CONCIERGE] += 0.5

        # Short messages (< 10 words) boost CHAT
        word_count = len(message.split())
        if word_count < 10:
            scores[ChatMode.CHAT] += 1.0

        # Find highest scoring mode
        best_mode = max(scores, key=lambda m: scores[m])
        best_score = scores[best_mode]

        # If no strong signal, default to CHAT
        if best_score < 1.0:
            return (
                ChatMode.CHAT,
                0.8,
                "No strong intent detected, using fast CHAT mode",
                [],
            )

        # Calculate confidence based on score margin
        second_best = sorted(scores.values(), reverse=True)[1]
        margin = best_score - second_best
        confidence = min(0.95, 0.5 + (margin * 0.15))

        reasoning = f"Detected {best_mode.value} mode (score: {best_score:.1f}, margin: {margin:.1f})"

        return (best_mode, confidence, reasoning, detected_keywords[best_mode])

    async def route(self, request: ChatRequest) -> RoutingDecision:
        """
        Route a chat request to the appropriate model.
        """
        manager = await self.get_model_manager()

        # Priority 1: Explicit model override
        if request.explicit_model:
            model = request.explicit_model
            mode = self._infer_mode_from_model(model)
            decision = RoutingDecision(
                mode=mode,
                model=model,
                confidence=1.0,
                reasoning="Explicit model override",
            )
            # Ensure model is loaded
            actual_model, is_primary = (
                await manager.ensure_loaded_with_fallback(model)
            )
            if not is_primary:
                decision.model = actual_model
                decision.is_fallback = True
                decision.reasoning = f"Fallback from {model} to {actual_model}"

            self._routing_history.append(decision)
            return decision

        # Priority 2: Explicit mode override
        if request.explicit_mode:
            mode = request.explicit_mode
            model = MODE_TO_MODEL.get(mode, "phi3.5:3.8b")
            decision = RoutingDecision(
                mode=mode,
                model=model,
                confidence=1.0,
                reasoning=f"Explicit mode override: {mode.value}",
            )

            # Ensure model is loaded
            actual_model, is_primary = (
                await manager.ensure_loaded_with_fallback(model)
            )
            if not is_primary:
                decision.model = actual_model
                decision.is_fallback = True
                decision.reasoning = (
                    f"Mode {mode.value} fallback: {model} → {actual_model}"
                )

            self._routing_history.append(decision)
            return decision

        # Priority 3: Intent-based detection
        mode, confidence, reasoning, keywords = self.detect_mode(
            request.message
        )
        model = MODE_TO_MODEL.get(mode, "phi3.5:3.8b")

        decision = RoutingDecision(
            mode=mode,
            model=model,
            confidence=confidence,
            reasoning=reasoning,
            detected_keywords=keywords,
        )

        # Ensure model is loaded
        actual_model, is_primary = await manager.ensure_loaded_with_fallback(
            model
        )
        if not is_primary:
            decision.model = actual_model
            decision.is_fallback = True
            decision.reasoning = (
                f"{reasoning} (fallback: {model} → {actual_model})"
            )

        self._routing_history.append(decision)
        logger.info(
            f"Routed to {decision.model} ({decision.mode.value}) "
            f"[confidence={decision.confidence:.2f}]"
        )

        return decision

    def _infer_mode_from_model(self, model_name: str) -> ChatMode:
        """Infer chat mode from model name."""
        config = MODEL_CONFIGS.get(model_name)
        if config and config.primary_mode:
            return config.primary_mode

        # Guess from model name
        model_lower = model_name.lower()
        if "coder" in model_lower or "code" in model_lower:
            return ChatMode.MCP_COMMAND
        if "deepseek" in model_lower:
            return ChatMode.DEBATE
        if "llama" in model_lower:
            return ChatMode.CONCIERGE

        return ChatMode.CHAT

    def get_routing_stats(self) -> dict:
        """Get statistics about routing decisions."""
        if not self._routing_history:
            return {"total_routes": 0}

        mode_counts = {}
        model_counts = {}
        fallback_count = 0
        avg_confidence = 0.0

        for decision in self._routing_history:
            mode_counts[decision.mode.value] = (
                mode_counts.get(decision.mode.value, 0) + 1
            )
            model_counts[decision.model] = (
                model_counts.get(decision.model, 0) + 1
            )
            if decision.is_fallback:
                fallback_count += 1
            avg_confidence += decision.confidence

        avg_confidence /= len(self._routing_history)

        return {
            "total_routes": len(self._routing_history),
            "mode_distribution": mode_counts,
            "model_distribution": model_counts,
            "fallback_rate": fallback_count / len(self._routing_history),
            "average_confidence": round(avg_confidence, 3),
        }

    def clear_history(self) -> None:
        """Clear routing history."""
        self._routing_history = []


# Singleton instance
_chat_router: Optional[ChatRouter] = None


async def get_chat_router() -> ChatRouter:
    """Get or create the chat router singleton."""
    global _chat_router
    if _chat_router is None:
        _chat_router = ChatRouter()
    return _chat_router


async def route_message(
    message: str,
    user_id: str = "default",
    mode: Optional[str] = None,
    model: Optional[str] = None,
) -> RoutingDecision:
    """
    Convenience function to route a message.

    Args:
        message: The chat message to route
        user_id: User identifier
        mode: Optional explicit mode override
        model: Optional explicit model override

    Returns:
        RoutingDecision with the selected model and mode
    """
    router = await get_chat_router()

    explicit_mode = None
    if mode:
        try:
            explicit_mode = ChatMode(mode.lower())
        except ValueError:
            logger.warning(f"Unknown mode '{mode}', will auto-detect")

    request = ChatRequest(
        message=message,
        user_id=user_id,
        explicit_mode=explicit_mode,
        explicit_model=model,
    )

    return await router.route(request)
