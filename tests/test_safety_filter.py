"""Unit tests for model safety filter."""

from __future__ import annotations

from src.mcp_server.safety_filter import SafetyFilter


def test_safety_filter_safe_content():
    """Verify safe content passes through."""
    filter_engine = SafetyFilter()
    result = filter_engine.filter_output(
        "This is a helpful response about Python programming."
    )
    assert result["decision"] == "allowed"
    assert result["classification"]["category"] == "safe"


def test_safety_filter_moderate_content():
    """Verify moderate content is flagged."""
    filter_engine = SafetyFilter()
    result = filter_engine.filter_output("This is a controversial topic.")
    assert result["decision"] == "flagged"
    assert result["classification"]["category"] == "moderate"
    assert "controversial" in result["classification"]["matches"]


def test_safety_filter_severe_content():
    """Verify severe content is blocked."""
    filter_engine = SafetyFilter()
    result = filter_engine.filter_output("Instructions for violence and harm.")
    assert result["decision"] == "blocked"
    assert result["classification"]["category"] == "severe"
    assert "[CONTENT BLOCKED" in result["filtered_text"]


def test_safety_filter_confidence_scoring():
    """Verify confidence scores by category."""
    filter_engine = SafetyFilter()
    safe_result = filter_engine.classify("Normal text")
    severe_result = filter_engine.classify("Malware exploit")

    assert safe_result["confidence"] == 1.0
    assert severe_result["confidence"] >= 0.8
