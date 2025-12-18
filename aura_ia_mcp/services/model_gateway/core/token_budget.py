class TokenBudgetManager:
    """Manages token budgets and context windows."""

    def __init__(self, max_tokens: int = 4096):
        self.max_tokens = max_tokens
        # Maintain rolling history of (input_tokens, output_tokens)
        self.history: list[tuple[int, int]] = []

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (simple approximation: 4 chars/token)."""
        # Round up to avoid underestimation for small strings
        return max(0, (len(text) + 3) // 4)

    def check_budget(self, prompt: str, max_new_tokens: int = 512) -> bool:
        """Check if the request fits within the budget."""
        input_tokens = self.estimate_tokens(prompt)
        return (input_tokens + max_new_tokens) <= self.max_tokens

    def truncate(self, text: str, limit: int) -> str:
        """Truncate text to fit within the limit."""
        current_tokens = self.estimate_tokens(text)
        if current_tokens <= limit:
            return text

        # Simple character-based truncation
        char_limit = limit * 4
        return text[:char_limit] + "..."

    def record_turn(self, input_tokens: int, output_tokens: int) -> None:
        """Record a completed conversation turn for forecasting."""
        self.history.append((int(input_tokens), int(output_tokens)))
        # cap history length to a reasonable window (e.g., last 20 turns)
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def _rolling_averages(self) -> tuple[float, float]:
        if not self.history:
            return (0.0, 0.0)
        total_in = sum(h[0] for h in self.history)
        total_out = sum(h[1] for h in self.history)
        n = len(self.history)
        return (total_in / n, total_out / n)

    def forecast_usage(
        self, current_input: int, safety_margin: float = 0.1
    ) -> dict:
        """
        Forecast total token usage for the next turn based on history.

        Returns dict with keys:
          - forecast_total: int (current_input + predicted_output)
          - available: int (remaining tokens within max)
          - needs_truncation: bool
          - recommended_input: int (optional, only when truncation is needed)
        """
        avg_in, avg_out = self._rolling_averages()
        # Predict output proportional to historical output; fall back to simple ratio 1.0 if no history
        predicted_out = avg_out if self.history else int(current_input * 1.0)
        # apply safety margin
        predicted_out = int(predicted_out * (1 + safety_margin))

        forecast_total = int(current_input) + predicted_out
        available = max(0, self.max_tokens - forecast_total)
        needs_truncation = forecast_total > self.max_tokens

        result: dict[str, int | bool] = {
            "forecast_total": forecast_total,
            "available": available,
            "needs_truncation": needs_truncation,
        }

        if needs_truncation:
            # Recommend an input size that leaves room for predicted output
            # Ensure at least 1 token available for output
            recommended_input = max(0, self.max_tokens - max(predicted_out, 1))
            result["recommended_input"] = recommended_input

        return result
