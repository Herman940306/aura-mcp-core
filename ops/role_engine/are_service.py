#!/usr/bin/env python3
"""
ARE Service - Autonomous Role Engine (overdrive)

Project Creator: Herman Swanepoel
Document Version: 2.0
Last Updated: December 13, 2025

Provides:
 - /roles GET/POST/PUT (versioned)
 - /propose POST (auto-propose role modifications)
 - /evaluate POST (role selection candidates)
 - /simulate POST (simulate role behavior in sandbox)
 - /ws/governance WebSocket for real-time governance updates
 - /api/governance/roles REST endpoint for role hierarchy
 - /api/governance/audit-logs REST endpoint for security audit events
Safety: changes default to draft; AUTO_APPROVE env controls auto-commit.
"""
import asyncio
import json
import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    Body,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from jsonschema import ValidationError, validate
from pydantic import BaseModel

REG_FILE = "ops/role_engine/role_registry_v2.json"
SCHEMA_FILE = "ops/role_engine/role_schema.json"
DRAFTS_DIR = "ops/role_engine/drafts"
SIM_DIR = "simulator"
LOG_DIR = "/app/logs"  # Container path
AUTO_APPROVE = os.getenv("AUTO_APPROVE", "false").lower() == "true"
FORBIDDEN_PREFIXES = os.getenv("FORBIDDEN_ROLE_PREFIXES", "").split(",")
MAX_AUTOGEN_RISK = float(os.getenv("MAX_AUTOGEN_RISK", "0.6"))

app = FastAPI(title="ARE+ Service")

# Allow Dashboard to connect directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_registry():
    return json.load(open(REG_FILE))


def save_registry(obj):
    with open(REG_FILE, "w") as f:
        json.dump(obj, f, indent=2)


class RoleSpec(BaseModel):
    name: str
    purpose: str
    responsibilities: list
    behaviors: list = []
    interactions: list = []
    scoring_profile: dict
    version: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/roles")
def list_roles():
    return load_registry()


@app.post("/roles")
def create_role(spec: RoleSpec):
    # validate schema
    try:
        schema = json.load(open(SCHEMA_FILE))
        validate(instance=spec.dict(), schema=schema)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # safety: forbidden prefixes
    for p in FORBIDDEN_PREFIXES:
        if spec.name.lower().startswith(p.lower()):
            raise HTTPException(
                status_code=403, detail="forbidden role name prefix"
            )
    # store as draft
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    draft_id = str(uuid.uuid4())
    draft_path = os.path.join(DRAFTS_DIR, f"{draft_id}.json")
    draft = {
        "id": draft_id,
        "spec": spec.dict(),
        "meta": {"ts": time.time(), "status": "draft"},
    }
    open(draft_path, "w").write(json.dumps(draft, indent=2))
    # auto-approve if env allows and risk low
    risk = spec.scoring_profile.get("risk_factor", 0.5)
    if AUTO_APPROVE and risk <= MAX_AUTOGEN_RISK:
        reg = load_registry()
        reg["roles"][spec.name] = spec.dict()
        reg["meta"]["last_updated"] = time.time()
        save_registry(reg)
        draft["meta"]["status"] = "committed"
        open(draft_path, "w").write(json.dumps(draft, indent=2))
        return {"ok": True, "committed": True, "role": spec.name}
    return {"ok": True, "draft_id": draft_id, "committed": False}


@app.post("/propose")
def propose_role_change(payload: dict = Body(...)):
    """
    payload: {
      "reason":"text",
      "evidence":[...], // logs or patterns
      "proposal": { RoleSpec }
    }
    This endpoint uses heuristics to propose role edits.
    """
    proposal = payload.get("proposal")
    if not proposal:
        raise HTTPException(status_code=400, detail="missing proposal")
    # basic risk heuristics: if proposal increases risk over threshold, mark high-risk
    risk = proposal.get("scoring_profile", {}).get("risk_factor", 0.5)
    draft_id = str(uuid.uuid4())
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    draft_path = os.path.join(DRAFTS_DIR, f"{draft_id}.json")
    draft = {
        "id": draft_id,
        "proposal": proposal,
        "reason": payload.get("reason"),
        "evidence": payload.get("evidence", []),
        "meta": {"ts": time.time(), "risk": risk, "status": "proposed"},
    }
    open(draft_path, "w").write(json.dumps(draft, indent=2))
    return {"ok": True, "draft_id": draft_id, "risk": risk}


@app.post("/evaluate")
def evaluate_task(task: dict = Body(...)):
    """
    Expect: {"task":"text","context":{...},"topk":3}
    Returns scored candidate roles (heuristic + model hook)
    """
    task_text = task.get("task", "").lower()
    reg = load_registry()["roles"]
    candidates = []
    for name, spec in reg.items():
        score = 0.0
        # match keywords in purpose/responsibilities
        txt = (
            spec.get("purpose", "")
            + " "
            + " ".join(spec.get("responsibilities", []))
        ).lower()
        for w in set(task_text.split()):
            if len(w) > 2 and w in txt:
                score += 1.0
        # boost with priority
        p = spec.get("scoring_profile", {}).get("priority", 5)
        score = score * (p / 10.0)
        candidates.append({"role": name, "score": score, "priority": p})
    candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)
    # return topk
    return {
        "candidates": candidates[: task.get("topk", 3)],
        "meta": {"task": task_text},
    }


@app.post("/simulate")
def simulate_role(role_name: str = Body(...), scenario: dict = Body(...)):
    """
    Run an isolated simulation of what role would do (sandbox stub).
    This writes to simulator/ and returns a synthetic verdict.
    """
    sim_id = str(uuid.uuid4())
    sim_path = os.path.join(SIM_DIR, sim_id + ".json")
    # naive simulation: score how many keywords match
    content = scenario.get("text", "")
    reg = load_registry()["roles"]
    spec = reg.get(role_name)
    if not spec:
        raise HTTPException(status_code=404, detail="role not found")
    score = 0
    for r in spec.get("responsibilities", []):
        for w in r.split():
            if w.lower() in content.lower():
                score += 1
    verdict = {"role": role_name, "sim_score": score, "ok": score > 0}
    open(sim_path, "w").write(
        json.dumps(
            {"id": sim_id, "verdict": verdict, "ts": time.time()}, indent=2
        )
    )
    return {"sim_id": sim_id, "verdict": verdict}


@app.get("/audit-log")
def get_audit_log(limit: int = 50):
    """
    Read latest security audit logs.
    """
    log_file = os.path.join(LOG_DIR, "security_audit.jsonl")
    if not os.path.exists(log_file):
        # Fallback for local testing
        log_file = "logs/security_audit.jsonl"

    if not os.path.exists(log_file):
        return {"events": []}

    events = []
    try:
        # Read file in reverse effectively by reading all and slicing end
        # For large files, seek() is better, but this is simple for now
        with open(log_file, "r") as f:
            lines = f.readlines()
            for line in reversed(lines):
                try:
                    if len(events) >= limit:
                        break
                    events.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        print(f"Error reading audit log: {e}")

    return {"events": events}


# ─────────────────────────────────────────────────────────────────────────────
# Governance API Endpoints (Dashboard Integration)
# ─────────────────────────────────────────────────────────────────────────────

# Track active WebSocket connections for governance updates
_governance_connections: dict = {}


def _build_role_hierarchy() -> Dict[str, Any]:
    """
    Build a hierarchical representation of roles for dashboard display.
    Returns role tree with capabilities and trust levels.
    """
    registry = load_registry()
    roles = registry.get("roles", {})

    hierarchy = {
        "root": {
            "name": "System",
            "trust_level": 10,
            "children": []
        },
        "roles": [],
        "meta": {
            "total_roles": len(roles),
            "last_updated": registry.get("meta", {}).get("last_updated", 0)
        }
    }

    # Group roles by trust level / priority
    for role_name, role_spec in roles.items():
        scoring = role_spec.get("scoring_profile", {})
        role_info = {
            "name": role_name,
            "purpose": role_spec.get("purpose", ""),
            "trust_level": scoring.get("priority", 5),
            "risk_factor": scoring.get("risk_factor", 0.5),
            "capabilities": role_spec.get("responsibilities", []),
            "behaviors": role_spec.get("behaviors", []),
            "interactions": role_spec.get("interactions", []),
            "version": role_spec.get("version", "1.0")
        }
        hierarchy["roles"].append(role_info)

    # Sort by trust level (priority) descending
    hierarchy["roles"].sort(
        key=lambda r: r.get("trust_level", 0),
        reverse=True
    )

    return hierarchy


def _parse_audit_logs(limit: int = 50, level_filter: str = "all") -> List[Dict]:
    """
    Parse and format audit log files for dashboard consumption.

    Args:
        limit: Maximum number of events to return
        level_filter: Filter by log level (all, error, warning, info)

    Returns:
        List of formatted audit events
    """
    log_file = os.path.join(LOG_DIR, "security_audit.jsonl")
    if not os.path.exists(log_file):
        log_file = "logs/security_audit.jsonl"

    if not os.path.exists(log_file):
        return []

    events = []
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
            for line in reversed(lines):
                if len(events) >= limit:
                    break
                try:
                    event = json.loads(line)
                    # Apply level filter
                    event_level = event.get("level", "info").lower()
                    if level_filter != "all" and event_level != level_filter:
                        continue

                    # Format event for dashboard
                    formatted = {
                        "timestamp": event.get("timestamp", ""),
                        "level": event_level,
                        "event_type": event.get("event", "unknown"),
                        "message": event.get("message", ""),
                        "details": {
                            k: v for k, v in event.items()
                            if k not in ["timestamp", "level", "event", "message"]
                        }
                    }
                    events.append(formatted)
                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception as e:
        print(f"Error parsing audit logs: {e}")

    return events


@app.get("/api/governance/roles")
async def get_governance_roles():
    """
    REST endpoint for role hierarchy data.
    Returns complete role hierarchy with capabilities and trust levels.
    """
    try:
        hierarchy = _build_role_hierarchy()
        return {
            "status": "ok",
            "data": hierarchy,
            "timestamp": datetime.now(UTC).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load role hierarchy: {str(e)}"
        )


@app.get("/api/governance/audit-logs")
async def get_governance_audit_logs(
    limit: int = 50,
    level: str = "all"
):
    """
    REST endpoint for security audit events.

    Args:
        limit: Maximum number of events to return (default: 50)
        level: Filter by level - all, error, warning, info (default: all)
    """
    try:
        events = _parse_audit_logs(limit=limit, level_filter=level)
        return {
            "status": "ok",
            "events": events,
            "count": len(events),
            "timestamp": datetime.now(UTC).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load audit logs: {str(e)}"
        )


@app.websocket("/ws/governance")
async def governance_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time governance updates.
    Streams role hierarchy and audit log updates to connected clients.
    """
    client_id = str(uuid.uuid4())[:8]
    await websocket.accept()
    _governance_connections[client_id] = websocket

    try:
        # Send initial data
        initial_data = {
            "type": "governance_init",
            "roles": _build_role_hierarchy(),
            "audit_logs": _parse_audit_logs(limit=20),
            "timestamp": datetime.now(UTC).isoformat()
        }
        await websocket.send_json(initial_data)

        # Keep connection alive and send periodic updates
        while True:
            try:
                # Wait for client messages or timeout for periodic updates
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=5.0
                    )
                    # Handle client requests
                    if data.get("type") == "refresh_roles":
                        await websocket.send_json({
                            "type": "roles_update",
                            "roles": _build_role_hierarchy(),
                            "timestamp": datetime.now(UTC).isoformat()
                        })
                    elif data.get("type") == "refresh_audit":
                        level = data.get("level", "all")
                        limit = data.get("limit", 50)
                        await websocket.send_json({
                            "type": "audit_update",
                            "audit_logs": _parse_audit_logs(
                                limit=limit,
                                level_filter=level
                            ),
                            "timestamp": datetime.now(UTC).isoformat()
                        })
                except asyncio.TimeoutError:
                    # Send periodic update
                    await websocket.send_json({
                        "type": "governance_update",
                        "roles": _build_role_hierarchy(),
                        "audit_logs": _parse_audit_logs(limit=10),
                        "timestamp": datetime.now(UTC).isoformat()
                    })
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket error: {e}")
                break
    finally:
        if client_id in _governance_connections:
            del _governance_connections[client_id]


async def broadcast_governance_update(update_type: str, data: Dict[str, Any]):
    """
    Broadcast governance updates to all connected WebSocket clients.

    Args:
        update_type: Type of update (role_change, audit_event, etc.)
        data: Update data to broadcast
    """
    message = {
        "type": update_type,
        "data": data,
        "timestamp": datetime.now(UTC).isoformat()
    }

    disconnected = []
    for client_id, ws in _governance_connections.items():
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(client_id)

    # Clean up disconnected clients
    for client_id in disconnected:
        if client_id in _governance_connections:
            del _governance_connections[client_id]


# run with: uvicorn ops.role_engine.are_service:app --host 0.0.0.0 --port 9700
