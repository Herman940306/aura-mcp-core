"""Unit tests for conversation governance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.mcp_server.conversation_governance import (
    ConversationGovernance,
    PIIDetector,
)


def test_pii_detector_email():
    """Verify email detection and redaction."""
    detector = PIIDetector()
    text = "Contact me at user@example.com for details."
    detections = detector.detect(text)
    assert len(detections) == 1
    assert detections[0]["type"] == "email"

    redacted, _ = detector.redact(text)
    assert "user@example.com" not in redacted
    assert "[REDACTED_EMAIL]" in redacted


def test_pii_detector_phone():
    """Verify phone number detection."""
    detector = PIIDetector()
    text = "Call 555-123-4567 or 5551234567."
    detections = detector.detect(text)
    assert len(detections) >= 1
    assert any(d["type"] == "phone" for d in detections)


def test_pii_detector_allowlist():
    """Verify allowlist prevents false positives."""
    detector = PIIDetector()
    text = "Visit localhost:8000 or example.com."
    detections = detector.detect(text)
    # Should not detect allowlisted terms
    assert len(detections) == 0


def test_conversation_logging_basic(tmp_path: Path):
    """Verify basic conversation turn logging."""
    governance = ConversationGovernance(
        log_dir=tmp_path, enable_pii_detection=False
    )
    entry = governance.log_conversation_turn(
        conversation_id="conv-001",
        trace_id="trace-123",
        role="user",
        content="Hello, world!",
    )
    assert entry["conversation_id"] == "conv-001"
    assert entry["role"] == "user"
    assert "hash" in entry
    assert "hash_prev" in entry

    # Verify file written
    log_file = tmp_path / "conv-001.jsonl"
    assert log_file.exists()


def test_conversation_pii_redaction(tmp_path: Path):
    """Verify PII is redacted in logged conversations."""
    governance = ConversationGovernance(
        log_dir=tmp_path, enable_pii_detection=True
    )
    entry = governance.log_conversation_turn(
        conversation_id="conv-002",
        trace_id="trace-456",
        role="user",
        content="My email is sensitive@domain.com.",
    )
    assert "sensitive@domain.com" not in entry["content"]
    assert "[REDACTED_EMAIL]" in entry["content"]
    assert "email" in entry["pii_tags"]


def test_hash_chain_integrity(tmp_path: Path):
    """Verify hash chain integrity validation."""
    governance = ConversationGovernance(log_dir=tmp_path)
    governance.log_conversation_turn(
        "conv-003", "trace-1", "user", "Message 1"
    )
    governance.log_conversation_turn(
        "conv-003", "trace-2", "assistant", "Message 2"
    )
    governance.log_conversation_turn(
        "conv-003", "trace-3", "user", "Message 3"
    )

    result = governance.verify_integrity("conv-003")
    assert result["status"] == "valid"
    assert result["entries_verified"] == 3


def test_hash_chain_tamper_detection(tmp_path: Path):
    """Verify tamper detection in hash chain."""
    governance = ConversationGovernance(log_dir=tmp_path)
    governance.log_conversation_turn(
        "conv-004", "trace-1", "user", "Message 1"
    )
    governance.log_conversation_turn(
        "conv-004", "trace-2", "assistant", "Message 2"
    )

    # Tamper with log file
    log_file = tmp_path / "conv-004.jsonl"
    lines = log_file.read_text().splitlines()
    entry = json.loads(lines[1])
    entry["content"] = "TAMPERED"
    lines[1] = json.dumps(entry)
    log_file.write_text("\n".join(lines) + "\n")

    result = governance.verify_integrity("conv-004")
    assert result["status"] == "tampered"
    assert "entry_index" in result


def test_retention_pruning(tmp_path: Path):
    """Verify retention policy pruning."""
    governance = ConversationGovernance(log_dir=tmp_path, retention_days=0)
    governance.log_conversation_turn(
        "conv-005", "trace-1", "user", "Message 1"
    )

    # Prune immediately (retention_days=0)
    result = governance.prune_expired()
    assert result["pruned_count"] == 1
    assert result["total_count"] == 1
