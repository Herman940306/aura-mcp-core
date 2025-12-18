"""Token budgeting algorithm for model inference.

Implements rolling average prediction + dynamic summarization fallback
to prevent context overflow during multi-turn conversations.
"""

from __future__ import annotations

from collections import deque
from typing import Any


class TokenBudget:
    """Manages token allocation across conversation turns."""

    def __init__(
        self,
        max_tokens: int = 4096,
        alpha: float = 0.6,
        beta: float = 0.4,
        safety_margin: float = 0.15,
        history_window: int = 5,
    ):
        """Initialize token budgeting.

        Args:
            max_tokens: Maximum total tokens (input + output)
            alpha: Weight for historical input average
            beta: Weight for expected output
            safety_margin: Reserve fraction (e.g., 0.15 = 15% buffer)
            history_window: Number of past turns to track
        """
        self.max_tokens = max_tokens
        self.alpha = alpha
        self.beta = beta
        self.safety_margin = safety_margin
        self.history_window = history_window
        self._input_history: deque[int] = deque(maxlen=history_window)
        self._output_history: deque[int] = deque(maxlen=history_window)

    def record_turn(self, input_tokens: int, output_tokens: int) -> None:
        """Record token usage from completed turn."""
        self._input_history.append(input_tokens)
        self._output_history.append(output_tokens)

    def forecast_usage(self, current_input: int) -> dict[str, Any]:
        """Predict next turn token usage.

        Returns:
            dict with keys: forecast_total, available, needs_truncation
        """
        if not self._input_history:
            # Cold start: conservative estimate
            expected_output = int(current_input * 0.5)
        else:
            avg_in = sum(self._input_history) / len(self._input_history)
            avg_out = sum(self._output_history) / len(self._output_history)
            expected_output = int(self.alpha * avg_in + self.beta * avg_out)

        forecast_total = current_input + expected_output
        safety_reserve = int(self.max_tokens * self.safety_margin)
        available = self.max_tokens - safety_reserve
        needs_truncation = forecast_total > available

        return {
            "forecast_total": forecast_total,
            "available": available,
            "needs_truncation": needs_truncation,
            "recommended_input": (
                available - expected_output
                if needs_truncation
                else current_input
            ),
        }

    def suggest_truncation(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Truncate messages to fit budget (placeholder for semantic compression).

        Args:
            messages: Conversation history

        Returns:
            Truncated message list
        """
        # Simple heuristic: keep system + last N user/assistant pairs
        system = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        # Keep last 3 exchanges
        truncated = system + non_system[-6:]
        return truncated


__all__ = ["TokenBudget"]
