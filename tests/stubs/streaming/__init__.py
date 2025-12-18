"""Minimal streaming stubs for tests.
Provides start_server / stop_server that simulate SSE and load endpoints.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

_STATE: dict[str, Any] = {"running": False, "connections": 0}


async def start_server(port: int | None = None) -> dict[str, Any]:
    # Simulate async startup delay
    await asyncio.sleep(0.01)
    _STATE["running"] = True
    return {"port": port or 0, "status": "started"}


async def stop_server() -> dict[str, Any]:
    await asyncio.sleep(0.005)
    _STATE["running"] = False
    return {"status": "stopped", "connections": _STATE.get("connections", 0)}
    return {"status": "stopped", "connections": _STATE.get("connections", 0)}
