import json
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from .config import get_settings


def write_audit_log(record: dict[str, Any]) -> None:
    settings = get_settings()
    path = settings.AUDIT_LOG_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    record["ts"] = datetime.now(UTC).isoformat()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def audit_policy_decision(
    decision,
    context: dict[str, Any],
    route: str,
) -> None:
    payload = {
        "event": "policy_decision",
        "route": route,
        "action": decision.action,
        "allowed": decision.allowed,
        "reason": decision.reason,
        "risk_score": decision.risk_score,
        "role": decision.role,
        "context": context,
    }
    write_audit_log(payload)


def audit_safe_mode_transition(
    active: bool,
    actor: str,
    capabilities: dict[str, bool],
) -> None:
    write_audit_log(
        {
            "event": "safe_mode_transition",
            "active": active,
            "actor": actor,
            "capabilities": capabilities,
        }
    )


def audit_capability_state(
    actor: str,
    changed: dict[str, bool],
    full_state: dict[str, bool],
) -> None:
    write_audit_log(
        {
            "event": "capability_state",
            "actor": actor,
            "changed": changed,
            "state": full_state,
        }
    )


def audit_tool_registry_loaded(tool_names: Iterable[str]) -> None:
    write_audit_log(
        {
            "event": "tool_registry_loaded",
            "tools": list(tool_names),
        }
    )
