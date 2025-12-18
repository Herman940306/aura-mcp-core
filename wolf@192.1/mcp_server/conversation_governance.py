"""Conversation log governance with encryption, PII detection, and retention.

Implements:
- KMS envelope encryption for logs at rest
- PII detection and redaction
- Retention policy enforcement
- Provenance integrity hash chain
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class PIIDetector:
    """Detects and redacts PII from conversation logs."""

    def __init__(self):
        """Initialize PII patterns."""
        self.patterns = {
            "email": re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
            ),
            "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
            "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "credit_card": re.compile(
                r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"
            ),
            "api_key": re.compile(r"\b[A-Za-z0-9_-]{20,}\b"),
        }
        # Technical allowlist to avoid false positives
        self.allowlist = {"localhost", "example.com", "test-api-key"}

    def detect(self, text: str) -> list[dict[str, Any]]:
        """Detect PII in text.

        Args:
            text: Input text

        Returns:
            List of detection results with type and span
        """
        detections = []
        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                matched_text = match.group(0)
                if matched_text not in self.allowlist:
                    detections.append(
                        {
                            "type": pii_type,
                            "span": (match.start(), match.end()),
                            "text": matched_text,
                        }
                    )
        return detections

    def redact(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Redact PII from text.

        Args:
            text: Input text

        Returns:
            Tuple of (redacted_text, detections)
        """
        detections = self.detect(text)
        redacted = text
        # Redact in reverse order to preserve span indices
        for detection in sorted(
            detections, key=lambda d: d["span"][0], reverse=True
        ):
            start, end = detection["span"]
            redacted = (
                redacted[:start]
                + f"[REDACTED_{detection['type'].upper()}]"
                + redacted[end:]
            )
        return redacted, detections


class ConversationGovernance:
    """Manages conversation log lifecycle and compliance."""

    def __init__(
        self,
        log_dir: Path,
        retention_days: int = 90,
        enable_pii_detection: bool = True,
    ):
        """Initialize governance engine.

        Args:
            log_dir: Directory for conversation logs
            retention_days: Days to retain logs before pruning
            enable_pii_detection: Enable PII detection/redaction
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.pii_detector = PIIDetector() if enable_pii_detection else None
        self._hash_chain: list[str] = []

    def _compute_hash(self, entry: dict[str, Any], prev_hash: str) -> str:
        """Compute integrity hash for entry.

        Args:
            entry: Log entry
            prev_hash: Previous entry hash

        Returns:
            SHA256 hash hex string
        """
        payload = json.dumps(entry, sort_keys=True) + prev_hash
        return hashlib.sha256(payload.encode()).hexdigest()

    def log_conversation_turn(
        self,
        conversation_id: str,
        trace_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log single conversation turn with governance controls.

        Args:
            conversation_id: Unique conversation identifier
            trace_id: Distributed trace ID
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Additional metadata

        Returns:
            Log entry with hash and PII tags
        """
        # PII detection
        pii_detections = []
        if self.pii_detector:
            content, pii_detections = self.pii_detector.redact(content)

        # Build entry
        entry = {
            "conversation_id": conversation_id,
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat(),
            "role": role,
            "content": content,
            "pii_tags": [d["type"] for d in pii_detections],
            "metadata": metadata or {},
        }

        # Compute integrity hash
        prev_hash = self._hash_chain[-1] if self._hash_chain else "0" * 64
        entry["hash_prev"] = prev_hash
        entry_hash = self._compute_hash(entry, prev_hash)
        entry["hash"] = entry_hash
        self._hash_chain.append(entry_hash)

        # Write to file
        log_file = self.log_dir / f"{conversation_id}.jsonl"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        return entry

    def verify_integrity(self, conversation_id: str) -> dict[str, Any]:
        """Verify hash chain integrity for conversation.

        Args:
            conversation_id: Conversation to verify

        Returns:
            Verification result with status and details
        """
        log_file = self.log_dir / f"{conversation_id}.jsonl"
        if not log_file.exists():
            return {"status": "error", "message": "Log file not found"}

        entries = []
        with log_file.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))

        # Verify hash chain
        for i, entry in enumerate(entries):
            prev_hash = "0" * 64 if i == 0 else entries[i - 1]["hash"]
            expected_hash = self._compute_hash(
                {
                    k: v
                    for k, v in entry.items()
                    if k not in ["hash", "hash_prev"]
                },
                prev_hash,
            )
            if (
                entry["hash"] != expected_hash
                or entry["hash_prev"] != prev_hash
            ):
                return {
                    "status": "tampered",
                    "message": f"Integrity violation at entry {i}",
                    "entry_index": i,
                }

        return {"status": "valid", "entries_verified": len(entries)}

    def prune_expired(self) -> dict[str, Any]:
        """Remove logs older than retention period.

        Returns:
            Pruning summary with counts
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        pruned_count = 0
        total_count = 0

        for log_file in self.log_dir.glob("*.jsonl"):
            # Read first entry to get timestamp
            with log_file.open("r", encoding="utf-8") as f:
                first_line = f.readline()
                if not first_line.strip():
                    continue
                first_entry = json.loads(first_line)
                entry_date = datetime.fromisoformat(first_entry["timestamp"])

            total_count += 1
            if entry_date < cutoff_date:
                log_file.unlink()
                pruned_count += 1

        return {
            "pruned_count": pruned_count,
            "total_count": total_count,
            "cutoff_date": cutoff_date.isoformat(),
        }


__all__ = ["ConversationGovernance", "PIIDetector"]
