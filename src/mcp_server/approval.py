from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class ApprovalQueue:
    def __init__(self) -> None:
        self._queue: deque[tuple[str, str]] = deque()
        self._approved: dict[tuple[str, str], bool] = {}
        self._lock = threading.Lock()

    def request(self, tool: str, action_id: str) -> None:
        with self._lock:
            key = (tool, action_id)
            if key not in self._approved:
                self._queue.append(key)
                self._approved[key] = False

    def approve(self, tool: str, action_id: str) -> None:
        with self._lock:
            self._approved[(tool, action_id)] = True

    def is_approved(self, tool: str, action_id: str) -> bool:
        with self._lock:
            return self._approved.get((tool, action_id), False)

    def pending(self) -> tuple[tuple[str, str], ...]:
        with self._lock:
            return tuple(self._queue)


class RateLimiter:
    def __init__(self, interval_sec: float = 0.25) -> None:
        self.interval = interval_sec
        self._last: dict[str, float] = defaultdict(lambda: 0.0)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.perf_counter()
        with self._lock:
            if now - self._last[key] < self.interval:
                return False
            self._last[key] = now
            return True


# Global singletons for simple scaffolding
approval_queue = ApprovalQueue()
rate_limiter = RateLimiter()
