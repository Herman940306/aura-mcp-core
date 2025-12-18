# tests/test_audio_pii_redaction.py
import os
import sys

# Add audio_service to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "audio_service")
)

from main import pii_filter, policy_check_transcript


def test_pii_redaction_email():
    """Test that email addresses are redacted."""
    text = "Contact me at alice@example.com for details"
    out, redacted = pii_filter(text)
    assert redacted is True
    assert "[REDACTED]" in out
    assert "alice@example.com" not in out


def test_pii_redaction_ssn():
    """Test that SSN-like patterns are redacted."""
    text = "My SSN is 123-45-6789"
    out, redacted = pii_filter(text)
    assert redacted is True
    assert "[REDACTED]" in out


def test_pii_redaction_credit_card():
    """Test that credit card patterns are redacted."""
    text = "Card number: 4111 1111 1111 1111"
    out, redacted = pii_filter(text)
    assert redacted is True
    assert "[REDACTED]" in out


def test_no_pii():
    """Test that text without PII is not modified."""
    text = "Hello world this is a test"
    out, redacted = pii_filter(text)
    assert redacted is False
    assert out == text


def test_multiple_pii():
    """Test that multiple PII patterns are all redacted."""
    text = "Email alice@test.com SSN 123-45-6789"
    out, redacted = pii_filter(text)
    assert redacted is True
    assert out.count("[REDACTED]") >= 2


# Policy check tests
def test_policy_allows_normal_text():
    """Test that normal text passes policy check."""
    assert policy_check_transcript("Hello, how are you?") is True
    assert policy_check_transcript("Please help me with my code") is True


def test_policy_blocks_banned_commands():
    """Test that banned commands are blocked by policy."""
    assert policy_check_transcript("delete all files now") is False
    assert policy_check_transcript("override policy settings") is False
    assert policy_check_transcript("run sudo rm -rf /") is False


def test_policy_case_insensitive():
    """Test that policy check is case insensitive."""
    assert policy_check_transcript("DELETE ALL") is False
    assert policy_check_transcript("Override Policy") is False
