"""Persistent personality profile store.

Uses JSON file on disk to retain last adjusted personality traits and mood.
Thread-safe writes; simple read-modify-write semantics.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_STORE_DIR = Path("data")
_STORE_FILE = _STORE_DIR / "personality_profile.json"
_lock = threading.Lock()

_DEFAULT_PROFILE = {
    "tone": "professional",
    "mood": "stable",
    "adaptive": True,
    "traits": [],
    "updated_ts": None,
}


def load_profile() -> dict[str, Any]:
    if not _STORE_FILE.exists():
        return dict(_DEFAULT_PROFILE)
    try:
        raw = _STORE_FILE.read_bytes()
        key = os.getenv("PERSONA_KEY")
        if key:
            kbytes = key.encode("utf-8")
            raw = bytes(b ^ kbytes[i % len(kbytes)] for i, b in enumerate(raw))
        data = json.loads(raw.decode("utf-8"))
        for k, v in _DEFAULT_PROFILE.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return dict(_DEFAULT_PROFILE)


def save_profile(update: dict[str, Any]) -> dict[str, Any]:
    prof = load_profile()
    prof.update(update)
    prof["updated_ts"] = time.time()
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(prof, ensure_ascii=False, indent=2).encode("utf-8")
    key = os.getenv("PERSONA_KEY")
    if key:
        kbytes = key.encode("utf-8")
        payload = bytes(
            b ^ kbytes[i % len(kbytes)] for i, b in enumerate(payload)
        )
    with _lock:
        _STORE_FILE.write_bytes(payload)
    return prof
