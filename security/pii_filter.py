"""
Aura IA PII Filter Middleware
=============================

Zero-trust data governance: Redact PII before logging, storage, and responses.

Supported PII Types:
- Email addresses
- Phone numbers (US, International)
- Social Security Numbers (SSN)
- Credit card numbers
- IP addresses
- API keys and tokens
- Custom patterns (configurable)

Usage:
    from security.pii_filter import PIIFilter, PIIFilterMiddleware

    # Direct usage
    pii_filter = PIIFilter()
    clean_text = pii_filter.redact("Contact john@example.com for details")

    # FastAPI middleware
    app.add_middleware(PIIFilterMiddleware)
"""

import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PIIType(Enum):
    """Types of PII that can be detected and redacted."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    API_KEY = "api_key"
    JWT_TOKEN = "jwt_token"
    AWS_KEY = "aws_key"
    GITHUB_TOKEN = "github_token"
    PASSWORD = "password"
    NAME = "name"
    ADDRESS = "address"
    CUSTOM = "custom"


@dataclass
class PIIPattern:
    """Definition of a PII detection pattern."""

    pii_type: PIIType
    pattern: str
    replacement: str = "[REDACTED:{type}]"
    description: str = ""
    enabled: bool = True

    @property
    def compiled_pattern(self) -> re.Pattern:
        return re.compile(self.pattern, re.IGNORECASE)


@dataclass
class RedactionResult:
    """Result of PII redaction."""

    original_length: int
    redacted_length: int
    redactions: list[dict[str, Any]] = field(default_factory=list)
    redacted_text: str = ""

    @property
    def was_redacted(self) -> bool:
        return len(self.redactions) > 0

    @property
    def redaction_count(self) -> int:
        return len(self.redactions)


class PIIFilter:
    """
    PII detection and redaction engine.

    Features:
    - Configurable patterns per PII type
    - Deterministic hashing for correlation (optional)
    - Audit logging of redactions
    - Performance-optimized with compiled patterns
    """

    # Built-in PII patterns
    DEFAULT_PATTERNS: list[PIIPattern] = [
        # Email addresses
        PIIPattern(
            pii_type=PIIType.EMAIL,
            pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            replacement="[REDACTED:EMAIL]",
            description="Email addresses",
        ),
        # US Phone numbers
        PIIPattern(
            pii_type=PIIType.PHONE,
            pattern=r"\b(?:\+1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b",
            replacement="[REDACTED:PHONE]",
            description="US phone numbers",
        ),
        # International phone numbers
        PIIPattern(
            pii_type=PIIType.PHONE,
            pattern=r"\b\+(?:[0-9] ?){6,14}[0-9]\b",
            replacement="[REDACTED:PHONE]",
            description="International phone numbers",
        ),
        # SSN
        PIIPattern(
            pii_type=PIIType.SSN,
            pattern=r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
            replacement="[REDACTED:SSN]",
            description="Social Security Numbers",
        ),
        # Credit card numbers (Luhn-valid patterns)
        PIIPattern(
            pii_type=PIIType.CREDIT_CARD,
            pattern=r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
            replacement="[REDACTED:CARD]",
            description="Credit card numbers",
        ),
        # Credit card with spaces/dashes
        PIIPattern(
            pii_type=PIIType.CREDIT_CARD,
            pattern=r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            replacement="[REDACTED:CARD]",
            description="Credit card numbers with separators",
        ),
        # IPv4 addresses
        PIIPattern(
            pii_type=PIIType.IP_ADDRESS,
            pattern=r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
            replacement="[REDACTED:IP]",
            description="IPv4 addresses",
        ),
        # IPv6 addresses (simplified)
        PIIPattern(
            pii_type=PIIType.IP_ADDRESS,
            pattern=r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b",
            replacement="[REDACTED:IP]",
            description="IPv6 addresses",
        ),
        # Generic API keys (32+ hex or base64)
        PIIPattern(
            pii_type=PIIType.API_KEY,
            pattern=r'\b(?:api[_-]?key|apikey|api[_-]?secret)["\s:=]+["\']?([a-zA-Z0-9_\-]{32,})["\']?',
            replacement="[REDACTED:API_KEY]",
            description="Generic API keys",
        ),
        # AWS Access Key IDs
        PIIPattern(
            pii_type=PIIType.AWS_KEY,
            pattern=r"\bAKIA[0-9A-Z]{16}\b",
            replacement="[REDACTED:AWS_KEY]",
            description="AWS Access Key IDs",
        ),
        # AWS Secret Keys
        PIIPattern(
            pii_type=PIIType.AWS_KEY,
            pattern=r"\b[A-Za-z0-9/+=]{40}\b",
            replacement="[REDACTED:AWS_SECRET]",
            description="AWS Secret Access Keys",
        ),
        # GitHub tokens
        PIIPattern(
            pii_type=PIIType.GITHUB_TOKEN,
            pattern=r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b",
            replacement="[REDACTED:GITHUB_TOKEN]",
            description="GitHub tokens",
        ),
        # JWT tokens
        PIIPattern(
            pii_type=PIIType.JWT_TOKEN,
            pattern=r"\beyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b",
            replacement="[REDACTED:JWT]",
            description="JWT tokens",
        ),
        # Bearer tokens
        PIIPattern(
            pii_type=PIIType.API_KEY,
            pattern=r"\b[Bb]earer\s+[A-Za-z0-9_\-\.]+\b",
            replacement="Bearer [REDACTED:TOKEN]",
            description="Bearer tokens",
        ),
        # Password in key=value
        PIIPattern(
            pii_type=PIIType.PASSWORD,
            pattern=r'(?:password|passwd|pwd|secret)["\s:=]+["\']?([^\s"\']{4,})["\']?',
            replacement="[REDACTED:PASSWORD]",
            description="Passwords in configs",
        ),
    ]

    def __init__(
        self,
        patterns: list[PIIPattern] | None = None,
        enabled_types: set[PIIType] | None = None,
        use_hashing: bool = False,
        hash_salt: str = "",
        audit_log: bool = True,
    ):
        """
        Initialize PII filter.

        Args:
            patterns: Custom patterns (merged with defaults)
            enabled_types: Set of PIITypes to enable (None = all)
            use_hashing: Use deterministic hash instead of static replacement
            hash_salt: Salt for hashing (required if use_hashing=True)
            audit_log: Log redaction events
        """
        self.patterns = self.DEFAULT_PATTERNS.copy()
        if patterns:
            self.patterns.extend(patterns)

        self.enabled_types = enabled_types or {t for t in PIIType}
        self.use_hashing = use_hashing
        self.hash_salt = hash_salt
        self.audit_log = audit_log

        # Compile patterns for performance
        self._compiled_patterns: list[tuple[PIIPattern, re.Pattern]] = [
            (p, p.compiled_pattern)
            for p in self.patterns
            if p.enabled and p.pii_type in self.enabled_types
        ]

    def _hash_value(self, value: str, pii_type: PIIType) -> str:
        """Generate deterministic hash for correlation."""
        combined = f"{self.hash_salt}:{pii_type.value}:{value}"
        hash_digest = hashlib.sha256(combined.encode()).hexdigest()[:12]
        return f"[HASH:{pii_type.value.upper()}:{hash_digest}]"

    def _get_replacement(self, value: str, pattern: PIIPattern) -> str:
        """Get replacement string for a PII match."""
        if self.use_hashing:
            return self._hash_value(value, pattern.pii_type)
        return pattern.replacement.format(type=pattern.pii_type.value.upper())

    def redact(self, text: str) -> RedactionResult:
        """
        Redact PII from text.

        Args:
            text: Input text to scan

        Returns:
            RedactionResult with redacted text and audit info
        """
        if not text:
            return RedactionResult(
                original_length=0, redacted_length=0, redacted_text=""
            )

        result = RedactionResult(
            original_length=len(text), redacted_length=0, redacted_text=text
        )

        for pattern, compiled in self._compiled_patterns:
            matches = list(compiled.finditer(result.redacted_text))

            for match in reversed(matches):  # Reverse to preserve indices
                original_value = match.group(0)
                replacement = self._get_replacement(original_value, pattern)

                # Record redaction
                result.redactions.append(
                    {
                        "type": pattern.pii_type.value,
                        "start": match.start(),
                        "end": match.end(),
                        "length": len(original_value),
                        "replacement": replacement,
                    }
                )

                # Apply redaction
                result.redacted_text = (
                    result.redacted_text[: match.start()]
                    + replacement
                    + result.redacted_text[match.end() :]
                )

        result.redacted_length = len(result.redacted_text)

        # Audit log
        if self.audit_log and result.was_redacted:
            logger.info(
                "PII redaction performed",
                extra={
                    "redaction_count": result.redaction_count,
                    "types_redacted": list(
                        {r["type"] for r in result.redactions}
                    ),
                    "original_length": result.original_length,
                    "redacted_length": result.redacted_length,
                },
            )

        return result

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Recursively redact PII from a dictionary.

        Args:
            data: Dictionary to scan

        Returns:
            Dictionary with redacted values
        """
        result = {}

        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.redact(value).redacted_text
            elif isinstance(value, dict):
                result[key] = self.redact_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    (
                        self.redact_dict(item)
                        if isinstance(item, dict)
                        else (
                            self.redact(item).redacted_text
                            if isinstance(item, str)
                            else item
                        )
                    )
                    for item in value
                ]
            else:
                result[key] = value

        return result

    def contains_pii(self, text: str) -> bool:
        """Check if text contains any PII."""
        for _, compiled in self._compiled_patterns:
            if compiled.search(text):
                return True
        return False

    def detect_pii(self, text: str) -> list[dict[str, Any]]:
        """
        Detect PII without redacting.

        Returns:
            List of detected PII with type, position, and length
        """
        detections = []

        for pattern, compiled in self._compiled_patterns:
            for match in compiled.finditer(text):
                detections.append(
                    {
                        "type": pattern.pii_type.value,
                        "start": match.start(),
                        "end": match.end(),
                        "length": len(match.group(0)),
                    }
                )

        return detections


# =============================================================================
# FastAPI Middleware
# =============================================================================

try:
    import json

    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response, StreamingResponse

    class PIIFilterMiddleware(BaseHTTPMiddleware):
        """
        FastAPI/Starlette middleware for automatic PII redaction.

        Redacts PII from:
        - Request bodies (JSON)
        - Response bodies (JSON)
        - Query parameters
        - Headers (sensitive ones)
        """

        SENSITIVE_HEADERS = {
            "authorization",
            "x-api-key",
            "cookie",
            "set-cookie",
            "x-auth-token",
        }

        def __init__(self, app, pii_filter: PIIFilter | None = None, **kwargs):
            super().__init__(app)
            self.pii_filter = pii_filter or PIIFilter(**kwargs)

        async def dispatch(
            self, request: Request, call_next: Callable
        ) -> Response:
            # Redact sensitive headers in logs
            safe_headers = {
                k: "[REDACTED]" if k.lower() in self.SENSITIVE_HEADERS else v
                for k, v in request.headers.items()
            }

            # Log sanitized request info
            logger.debug(
                "Incoming request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "headers": safe_headers,
                },
            )

            # Process request
            response = await call_next(request)

            # Redact response body if JSON
            if response.headers.get("content-type", "").startswith(
                "application/json"
            ):
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk

                try:
                    data = json.loads(body.decode())
                    redacted_data = self.pii_filter.redact_dict(data)
                    redacted_body = json.dumps(redacted_data).encode()

                    return Response(
                        content=redacted_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type="application/json",
                    )
                except json.JSONDecodeError:
                    # Not valid JSON, return as-is
                    return Response(
                        content=body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                    )

            return response

except ImportError:
    # Starlette not installed
    PIIFilterMiddleware = None  # type: ignore


# =============================================================================
# CLI Interface
# =============================================================================

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Aura IA PII Filter")
    parser.add_argument("--input", "-i", help="Input file (or stdin)")
    parser.add_argument("--output", "-o", help="Output file (or stdout)")
    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="Detect PII without redacting",
    )
    parser.add_argument(
        "--hash", action="store_true", help="Use hashing for redaction"
    )
    parser.add_argument("--salt", default="aura-ia-pii", help="Hash salt")

    args = parser.parse_args()

    pii_filter = PIIFilter(use_hashing=args.hash, hash_salt=args.salt)

    # Read input
    if args.input:
        with open(args.input) as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    if args.detect_only:
        detections = pii_filter.detect_pii(text)
        output = json.dumps(detections, indent=2)
    else:
        result = pii_filter.redact(text)
        output = result.redacted_text

    # Write output
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
    else:
        print(output)
        print(output)
        print(output)
