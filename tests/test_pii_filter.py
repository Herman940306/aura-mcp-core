"""
Tests for Aura IA PII Filter
"""

import pytest

from security.pii_filter import PIIFilter, PIIPattern, PIIType, RedactionResult


class TestPIIFilter:
    """Test suite for PII detection and redaction."""

    @pytest.fixture
    def pii_filter(self) -> PIIFilter:
        return PIIFilter()

    @pytest.fixture
    def hashing_filter(self) -> PIIFilter:
        return PIIFilter(use_hashing=True, hash_salt="test-salt")

    # =========================================================================
    # Email Tests
    # =========================================================================

    def test_redact_email(self, pii_filter: PIIFilter):
        """Test email redaction."""
        text = "Contact john.doe@example.com for details"
        result = pii_filter.redact(text)

        assert "[REDACTED:EMAIL]" in result.redacted_text
        assert "john.doe@example.com" not in result.redacted_text
        assert result.was_redacted
        assert result.redaction_count == 1

    def test_redact_multiple_emails(self, pii_filter: PIIFilter):
        """Test multiple email redaction."""
        text = "Contact john@example.com or jane@test.org"
        result = pii_filter.redact(text)

        assert result.redacted_text.count("[REDACTED:EMAIL]") == 2
        assert result.redaction_count == 2

    # =========================================================================
    # Phone Tests
    # =========================================================================

    def test_redact_us_phone(self, pii_filter: PIIFilter):
        """Test US phone number redaction."""
        test_cases = [
            "Call 555-123-4567",
            "Call (555) 123-4567",
            "Call 555.123.4567",
            "Call +1 555 123 4567",
        ]

        for text in test_cases:
            result = pii_filter.redact(text)
            assert (
                "[REDACTED:PHONE]" in result.redacted_text
            ), f"Failed for: {text}"

    def test_redact_international_phone(self, pii_filter: PIIFilter):
        """Test international phone number redaction."""
        text = "Call +44 20 7946 0958"
        result = pii_filter.redact(text)

        assert "[REDACTED:PHONE]" in result.redacted_text

    # =========================================================================
    # SSN Tests
    # =========================================================================

    def test_redact_ssn(self, pii_filter: PIIFilter):
        """Test SSN redaction."""
        test_cases = [
            "SSN: 123-45-6789",
            "SSN: 123 45 6789",
            "SSN: 123456789",
        ]

        for text in test_cases:
            result = pii_filter.redact(text)
            assert (
                "[REDACTED:SSN]" in result.redacted_text
            ), f"Failed for: {text}"

    # =========================================================================
    # Credit Card Tests
    # =========================================================================

    def test_redact_credit_card(self, pii_filter: PIIFilter):
        """Test credit card redaction."""
        test_cases = [
            "Card: 4111111111111111",  # Visa
            "Card: 5500000000000004",  # Mastercard
            "Card: 4111-1111-1111-1111",
            "Card: 4111 1111 1111 1111",
        ]

        for text in test_cases:
            result = pii_filter.redact(text)
            assert (
                "[REDACTED:CARD]" in result.redacted_text
            ), f"Failed for: {text}"

    # =========================================================================
    # IP Address Tests
    # =========================================================================

    def test_redact_ipv4(self, pii_filter: PIIFilter):
        """Test IPv4 address redaction."""
        text = "User connected from 192.168.1.100"
        result = pii_filter.redact(text)

        assert "[REDACTED:IP]" in result.redacted_text
        assert "192.168.1.100" not in result.redacted_text

    # =========================================================================
    # API Key & Token Tests
    # =========================================================================

    def test_redact_github_token(self, pii_filter: PIIFilter):
        """Test GitHub token redaction."""
        text = "Use token ghp_1234567890abcdefghijklmnopqrstuvwxyz1234"
        result = pii_filter.redact(text)

        assert "[REDACTED:GITHUB_TOKEN]" in result.redacted_text

    def test_redact_jwt(self, pii_filter: PIIFilter):
        """Test JWT token redaction."""
        text = "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = pii_filter.redact(text)

        assert "[REDACTED:JWT]" in result.redacted_text

    def test_redact_aws_key(self, pii_filter: PIIFilter):
        """Test AWS key redaction."""
        text = "AWS Key: AKIAIOSFODNN7EXAMPLE"
        result = pii_filter.redact(text)

        assert "[REDACTED:AWS_KEY]" in result.redacted_text

    def test_redact_bearer_token(self, pii_filter: PIIFilter):
        """Test Bearer token redaction."""
        text = "Authorization: Bearer abc123xyz456"
        result = pii_filter.redact(text)

        assert "[REDACTED:TOKEN]" in result.redacted_text

    # =========================================================================
    # Hashing Mode Tests
    # =========================================================================

    def test_hashing_produces_consistent_output(
        self, hashing_filter: PIIFilter
    ):
        """Test that hashing is deterministic."""
        text = "Contact john@example.com"

        result1 = hashing_filter.redact(text)
        result2 = hashing_filter.redact(text)

        assert result1.redacted_text == result2.redacted_text
        assert "[HASH:EMAIL:" in result1.redacted_text

    def test_hashing_different_for_different_values(
        self, hashing_filter: PIIFilter
    ):
        """Test that different emails produce different hashes."""
        text1 = "Contact john@example.com"
        text2 = "Contact jane@example.com"

        result1 = hashing_filter.redact(text1)
        result2 = hashing_filter.redact(text2)

        assert result1.redacted_text != result2.redacted_text

    # =========================================================================
    # Dictionary Redaction Tests
    # =========================================================================

    def test_redact_dict(self, pii_filter: PIIFilter):
        """Test dictionary redaction."""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "nested": {"phone": "555-123-4567"},
            "list": ["jane@test.org", "normal text"],
        }

        result = pii_filter.redact_dict(data)

        assert "[REDACTED:EMAIL]" in result["email"]
        assert "[REDACTED:PHONE]" in result["nested"]["phone"]
        assert "[REDACTED:EMAIL]" in result["list"][0]
        assert result["list"][1] == "normal text"

    # =========================================================================
    # Detection Tests
    # =========================================================================

    def test_contains_pii(self, pii_filter: PIIFilter):
        """Test PII detection."""
        assert pii_filter.contains_pii("Contact john@example.com")
        assert pii_filter.contains_pii("Call 555-123-4567")
        assert not pii_filter.contains_pii("No PII here")

    def test_detect_pii(self, pii_filter: PIIFilter):
        """Test PII detection without redaction."""
        text = "Email john@example.com and call 555-123-4567"
        detections = pii_filter.detect_pii(text)

        assert len(detections) >= 2
        types = {d["type"] for d in detections}
        assert "email" in types
        assert "phone" in types

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_empty_string(self, pii_filter: PIIFilter):
        """Test empty string handling."""
        result = pii_filter.redact("")

        assert result.redacted_text == ""
        assert not result.was_redacted

    def test_no_pii(self, pii_filter: PIIFilter):
        """Test text without PII."""
        text = "This is a normal message without any sensitive data."
        result = pii_filter.redact(text)

        assert result.redacted_text == text
        assert not result.was_redacted

    def test_mixed_content(self, pii_filter: PIIFilter):
        """Test mixed PII and normal content."""
        text = """
        Hello John,

        Your order #12345 has been shipped.
        Contact support@company.com if you have questions.
        Your tracking number is ABC123456789.

        Thanks,
        Support Team
        """

        result = pii_filter.redact(text)

        # Email should be redacted
        assert "[REDACTED:EMAIL]" in result.redacted_text
        # Order number and tracking should NOT be redacted (not PII)
        assert "#12345" in result.redacted_text
        assert "ABC123456789" in result.redacted_text

    # =========================================================================
    # Custom Pattern Tests
    # =========================================================================

    def test_custom_pattern(self):
        """Test custom PII pattern."""
        custom = PIIPattern(
            pii_type=PIIType.CUSTOM,
            pattern=r"ACME-\d{6}",
            replacement="[REDACTED:ACME_ID]",
            description="ACME internal IDs",
        )

        pii_filter = PIIFilter(patterns=[custom])
        text = "Your ACME ID is ACME-123456"
        result = pii_filter.redact(text)

        assert "[REDACTED:ACME_ID]" in result.redacted_text

    # =========================================================================
    # Type Filtering Tests
    # =========================================================================

    def test_enabled_types_filter(self):
        """Test filtering by PII type."""
        pii_filter = PIIFilter(enabled_types={PIIType.EMAIL})
        text = "Email: john@example.com, Phone: 555-123-4567"
        result = pii_filter.redact(text)

        # Email should be redacted
        assert "[REDACTED:EMAIL]" in result.redacted_text
        # Phone should NOT be redacted
        assert "555-123-4567" in result.redacted_text


class TestRedactionResult:
    """Tests for RedactionResult dataclass."""

    def test_was_redacted_true(self):
        result = RedactionResult(
            original_length=100,
            redacted_length=90,
            redactions=[{"type": "email"}],
            redacted_text="test",
        )
        assert result.was_redacted

    def test_was_redacted_false(self):
        result = RedactionResult(
            original_length=100,
            redacted_length=100,
            redactions=[],
            redacted_text="test",
        )
        assert not result.was_redacted

    def test_redaction_count(self):
        result = RedactionResult(
            original_length=100,
            redacted_length=80,
            redactions=[{"type": "email"}, {"type": "phone"}],
            redacted_text="test",
        )
        assert result.redaction_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
    pytest.main([__file__, "-v"])
    pytest.main([__file__, "-v"])
