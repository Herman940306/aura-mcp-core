#!/usr/bin/env python3
import json
import time
import uuid

from fastapi import FastAPI

QUEUE = "ops/approvals/queue.jsonl"
app = FastAPI(title="ApprovalQueue")


def append(q):
    open(QUEUE, "a").write(json.dumps(q) + "\\n")


@app.post("/submit")
def submit(action: dict):
    rec = {
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "action": action,
        "status": "pending",
    }
    append(rec)
    return {"ok": True, "id": rec["id"]}


@app.post("/approve/{id}")
def approve(id: str):
    # naive: mark as approved in file (append)
    rec = {"id": id, "ts": time.time(), "action": "approve"}
    append(rec)
    return {"ok": True}
