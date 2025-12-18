"""Unit tests for token budgeting algorithm."""

from __future__ import annotations

from src.mcp_server.token_budget import TokenBudget


def test_cold_start_forecast():
    """Verify initial forecast without history."""
    budget = TokenBudget(max_tokens=4096, safety_margin=0.15)
    result = budget.forecast_usage(current_input=500)
    # Cold start: expected_output = 0.5 * input = 250
    assert result["forecast_total"] == 750  # 500 + 250
    assert result["available"] == int(4096 * 0.85)  # 3481
    assert not result["needs_truncation"]


def test_forecast_after_history():
    """Verify forecast uses rolling average."""
    budget = TokenBudget(max_tokens=4096, alpha=0.6, beta=0.4)
    budget.record_turn(input_tokens=400, output_tokens=300)
    budget.record_turn(input_tokens=420, output_tokens=320)
    # avg_in = 410, avg_out = 310
    # expected_output = 0.6*410 + 0.4*310 = 246 + 124 = 370
    result = budget.forecast_usage(current_input=450)
    assert result["forecast_total"] == 450 + 370
    assert not result["needs_truncation"]


def test_truncation_needed():
    """Verify truncation signal when forecast exceeds budget."""
    budget = TokenBudget(max_tokens=1000, safety_margin=0.1)
    budget.record_turn(input_tokens=600, output_tokens=500)
    result = budget.forecast_usage(current_input=700)
    # available = 900; forecast > available
    assert result["needs_truncation"]
    assert result["recommended_input"] < 700


def test_message_truncation():
    """Verify message list truncation keeps system + recent pairs."""
    budget = TokenBudget()
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2"},
        {"role": "user", "content": "Q3"},
        {"role": "assistant", "content": "A3"},
        {"role": "user", "content": "Q4"},
    ]
    truncated = budget.suggest_truncation(messages)
    # Should keep system + last 6 non-system (last 3 exchanges)
    assert len(truncated) == 7  # system + 6
    assert truncated[0]["role"] == "system"
    assert truncated[-1]["content"] == "Q4"
