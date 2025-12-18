# Aura IA Security Module
# PII filtering, policy enforcement, and audit logging

from .pii_filter import PIIFilter, PIIPattern, PIIType, RedactionResult

try:
    from .pii_filter import PIIFilterMiddleware
except ImportError:
    PIIFilterMiddleware = None

__all__ = [
    "PIIFilter",
    "PIIType",
    "PIIPattern",
    "RedactionResult",
    "PIIFilterMiddleware",
]
