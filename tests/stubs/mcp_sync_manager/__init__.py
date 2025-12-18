"""MCP sync manager stub.
Provides MCPSyncManager with minimal interface used in tests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class SyncResult:
    success: bool
    files_copied: int
    files_failed: int
    backup_path: str | None
    errors: list[str]
    timestamp: datetime
    duration_seconds: float


class MCPSyncManager:
    def __init__(
        self,
        source_dir=None,
        target_dir=None,
        backup_dir=None,
    ) -> None:
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.backup_dir = backup_dir
        self._events: list[dict[str, Any]] = []
        self.started = time.time()

    def register(self, name: str, meta: dict[str, Any] | None = None) -> None:
        self._events.append(
            {
                "event": "register",
                "name": name,
                "meta": meta,
                "ts": time.time(),
            }
        )

    def sync(self) -> dict[str, Any]:
        # Simulate a sync outcome
        result = {
            "status": "ok",
            "count": len(self._events),
            "age": time.time() - self.started,
        }
        self._events.append(
            {
                "event": "sync",
                "ts": time.time(),
                "result": result,
            }
        )
        return result

    def last(self) -> dict[str, Any] | None:
        return self._events[-1] if self._events else None

    # Extended interface methods referenced in tests (stubs)
    def compare_directories(self):  # pragma: no cover - simple struct stub
        class _Comp:
            total_source_files = 0
            total_target_files = 0
            files_only_in_source: list[str] = []
            files_only_in_target: list[str] = []
            files_different: list[str] = []
            files_same: list[str] = []

        return _Comp()

    def sync_files(self):  # pragma: no cover
        return SyncResult(
            success=True,
            files_copied=0,
            files_failed=0,
            backup_path=str(self.backup_dir) if self.backup_dir else None,
            errors=[],
            timestamp=datetime.now(),
            duration_seconds=0.0,
        )

    def verify_sync(self):  # pragma: no cover
        return True

    def cleanup_old_backups(self, keep_count=5):  # pragma: no cover
        return {"kept": keep_count}

    def log_sync_operation(self, result):  # pragma: no cover
        self._events.append(
            {
                "event": "sync_log",
                "result": getattr(result, "success", True),
            }
        )

    def generate_sync_report(self, result):  # pragma: no cover
        return {
            "success": getattr(result, "success", True),
            "files_copied": getattr(result, "files_copied", 0),
            "files_failed": getattr(result, "files_failed", 0),
        }
