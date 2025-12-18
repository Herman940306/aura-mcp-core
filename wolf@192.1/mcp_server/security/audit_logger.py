"""Enterprise audit logger.

Captures security-relevant events: approvals requested/granted, rate limits,
command executions, and tool failures.
"""

from __future__ import annotations

import gzip
import json
import threading
import time
from pathlib import Path
from typing import Any, Dict

_AUDIT_DIR = Path("logs")
_AUDIT_FILE = _AUDIT_DIR / "security_audit.jsonl"
_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
_MAX_FILES = 5
_PURGE_AFTER = 10  # hard cap beyond rotated gzip archives
_ROTATION_INTERVAL_SEC = 24 * 3600  # daily
_lock = threading.Lock()
_META_FILE = _AUDIT_DIR / "security_audit.meta.json"


def _rotate_if_needed() -> None:
    try:
        stat = _AUDIT_FILE.stat()
        meta = {}
        if _META_FILE.exists():
            meta = json.loads(_META_FILE.read_text(encoding="utf-8"))
        last_ts = meta.get("last_rotation_ts", stat.st_mtime)
        need_rotation = (
            stat.st_size > _MAX_SIZE_BYTES
            or (time.time() - last_ts) > _ROTATION_INTERVAL_SEC
        )
        if not need_rotation:
            return
        # Find next index
        for idx in range(_MAX_FILES, 0, -1):
            old = _AUDIT_DIR / f"security_audit.{idx}.jsonl"
            newer = _AUDIT_DIR / f"security_audit.{idx+1}.jsonl"
            if newer.exists():
                newer.unlink(missing_ok=True)  # type: ignore[arg-type]
            if old.exists():
                old.rename(newer)
        rotated_path = _AUDIT_DIR / "security_audit.1.jsonl"
        _AUDIT_FILE.rename(rotated_path)
        # gzip compress rotated file
        try:
            raw = rotated_path.read_bytes()
            with gzip.open(rotated_path.with_suffix(".jsonl.gz"), "wb") as gz:
                gz.write(raw)
            rotated_path.unlink(missing_ok=True)  # type: ignore[arg-type]
        except OSError:
            pass
        # Purge archives beyond purge limit
        for extra in range(_PURGE_AFTER, _MAX_FILES + 1, -1):
            p = _AUDIT_DIR / f"security_audit.{extra}.jsonl.gz"
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        _AUDIT_FILE.write_text("", encoding="utf-8")
        meta["last_rotation_ts"] = time.time()
        _META_FILE.write_text(json.dumps(meta), encoding="utf-8")
    except FileNotFoundError:
        return
    except OSError:
        return


def _ensure() -> None:
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def record(event_type: str, data: Dict[str, Any]) -> None:
    _ensure()
    _rotate_if_needed()
    entry = {"ts": time.time(), "type": event_type, **data}
    line = json.dumps(entry, ensure_ascii=False)
    with _lock:
        with _AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


# Convenience wrappers


def approval_requested(tool: str, action_id: str) -> None:
    record("approval_requested", {"tool": tool, "action_id": action_id})


def approval_granted(tool: str, action_id: str) -> None:
    record("approval_granted", {"tool": tool, "action_id": action_id})


def rate_limited(key: str) -> None:
    record("rate_limited", {"key": key})


def command_executed(
    command: str,
    success: bool,
    exit_code: int | None = None,
) -> None:
    record(
        "command_executed",
        {"command": command, "success": success, "exit_code": exit_code},
    )


def tool_failure(tool: str, error_code: str) -> None:
    record("tool_failure", {"tool": tool, "error_code": error_code})


def safe_mode_active(enabled: bool) -> None:
    """Record SAFE MODE activation state for governance evidence."""
    record("safe_mode_status", {"active": enabled})
