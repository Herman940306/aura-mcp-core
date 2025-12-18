import os
import sys
import threading
import time
from pathlib import Path

import httpx

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from mcp_server.real_backend_server import run_server as backend_run

BASE = os.getenv("IDE_AGENTS_BACKEND_URL", "http://127.0.0.1:8001")

_started = False


def _ensure():
    global _started
    if _started:
        return
    th = threading.Thread(
        target=backend_run,
        kwargs={"host": "127.0.0.1", "port": 8001},
        daemon=True,
    )
    th.start()
    _started = True
    time.sleep(0.2)


def test_list_topics():
    _ensure()
    r = httpx.get(f"{BASE}/documentation")
    assert r.status_code == 200
    data = r.json()
    assert "topics" in data and isinstance(data["topics"], list)


def test_fetch_topic():
    _ensure()
    r = httpx.get(f"{BASE}/documentation", params={"topic": "command"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("topic") == "command"
    assert "documentation" in data
    assert "summary" in data["documentation"]
