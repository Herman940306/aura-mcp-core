import json
from pathlib import Path

from aura_ia_mcp.core.audit import audit_safe_mode_transition
from aura_ia_mcp.core.capabilities import load_capabilities

AUDIT_PATH = Path("logs/security_audit.jsonl")


def test_safe_mode_transition_event_logged():
    state = load_capabilities()
    audit_safe_mode_transition(False, "test-actor", state.export())
    # Read last line
    last = None
    for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last = line
    assert last is not None
    payload = json.loads(last)
    assert payload.get("event") == "safe_mode_transition"
    assert payload.get("active") is False
    assert payload.get("active") is False
