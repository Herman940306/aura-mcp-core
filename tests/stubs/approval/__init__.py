"""Approval workflow stubs for tests.

Provides approval_required and record_approval functions.
"""

from __future__ import annotations

import time
from typing import Any, Dict

_APPROVAL_LOG: list[dict[str, Any]] = []


def approval_required(action: str) -> bool:
    # Always require approval for mutation actions in SAFE MODE.
    return action.startswith("mutate")


def record_approval(action: str, approved: bool) -> dict[str, Any]:
    entry = {"action": action, "approved": approved, "ts": time.time()}
    _APPROVAL_LOG.append(entry)
    return entry
