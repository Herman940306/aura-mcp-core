#!/usr/bin/env python3
import hashlib
import hmac
import json
import os
import time

AUDIT_LOG = "logs/role_provenance.log"
SECRET = os.getenv("PROV_SECRET", "prov-dev-secret")


def append_event(evt: dict):
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    evt_with_ts = {"ts": time.time(), **evt}
    raw = json.dumps(evt_with_ts, separators=(",", ":"))
    sig = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    record = {"entry": evt_with_ts, "sig": sig}
    open(AUDIT_LOG, "a").write(json.dumps(record) + "\\n")
    return record
