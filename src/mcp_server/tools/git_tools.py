# mcp/server/git_tools.py
"""
MCP server router to expose git/sandbox tool operations to agents via authenticated endpoints.

Endpoints:
  POST /internal/git/sync         -> {"repo_path": "...", "remote": "..."}
  POST /internal/git/worktree/add -> {"repo_path": "...", "branch": "..."}
  POST /internal/git/worktree/rm  -> {"repo_path": "...", "branch": "..."}
  POST /internal/git/sandbox      -> {"repo_path": "...", "cmd":"pytest -q", "timeout":60}
  GET  /internal/git/worktrees    -> list current worktrees (porcelain)

Security:
- Requires identity from mcp.server.auth_roles.get_current_identity()
- Requires role membership (Lead Engineer or Full-Stack Guru) by default; configurable
- All calls are audit-logged via ops.role_engine.audit_provenance.append_event()
"""

import json
import os
import subprocess

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

# try to import helper modules present in the repo
try:
    from mcp.server.auth_roles import (
        get_current_identity,  # returns dict with 'username'/'roles'
    )
except Exception:
    # fallback stub: allow all (when running in dev without auth_roles)
    def get_current_identity():
        return {"username": "unknown", "roles": ["Unknown"]}


try:
    from ops.role_engine.audit_provenance import append_event
except Exception:

    def append_event(evt):
        # best-effort fallback: append to logs/role_provenance.log
        import json
        import os
        import time

        LOG = "logs/role_provenance.log"
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        evt_with_ts = {"ts": time.time(), **evt}
        open(LOG, "a").write(json.dumps(evt_with_ts) + "\n")
        return evt_with_ts


router = APIRouter(prefix="/internal/git", tags=["internal-git"])

# policy: allowed roles to perform destructive operations
ALLOWED_ROLES = {"Lead Engineer", "Full-Stack Guru", "Senior Architect"}


def run_cmd(cmd, cwd=None, timeout=120):
    """Run shell command and return structured result (capture_output)."""
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "rc": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def assert_authorized(identity: dict, action: str):
    roles = set(identity.get("roles", []))
    if roles & ALLOWED_ROLES:
        return True
    raise HTTPException(
        status_code=403, detail=f"insufficient role to perform {action}"
    )


class SyncReq(BaseModel):
    repo_path: str
    remote: str | None = None
    ref: str | None = "origin/main"


@router.post("/sync")
def sync_repo(req: SyncReq, identity: dict = Depends(get_current_identity)):
    """Smart incremental sync (calls ops/git/smart_sync.py)."""
    assert_authorized(identity, "sync")
    script = os.path.join(os.getcwd(), "ops", "git", "smart_sync.py")
    payload = {
        "repo": req.repo_path,
        "remote": req.remote,
        "ref": req.ref,
        "mode": "incremental",
    }
    event = {
        "actor": identity.get("username"),
        "action": "git.sync.request",
        "payload": payload,
    }
    append_event(event)
    if not os.path.exists(script):
        raise HTTPException(
            status_code=404, detail="smart_sync.py not found on server"
        )
    cmd = f"python3 {script} --repo {req.repo_path} --remote { (req.remote or '') } --ref {req.ref} --mode incremental"
    try:
        out = run_cmd(cmd, timeout=180)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="sync timeout")
    result = {"ok": True, "cmd": cmd, "result": out}
    append_event(
        {
            "actor": identity.get("username"),
            "action": "git.sync.result",
            "payload": result,
        }
    )
    return result


class WorktreeReq(BaseModel):
    repo_path: str
    branch: str
    worktrees_dir: str | None = ".worktrees"


@router.post("/worktree/add")
def add_worktree(
    req: WorktreeReq, identity: dict = Depends(get_current_identity)
):
    assert_authorized(identity, "worktree_add")
    script = os.path.join(os.getcwd(), "ops", "git", "worktree_manager.py")
    payload = {
        "repo": req.repo_path,
        "branch": req.branch,
        "worktrees_dir": req.worktrees_dir,
        "action": "add",
    }
    append_event(
        {
            "actor": identity.get("username"),
            "action": "git.worktree.add.request",
            "payload": payload,
        }
    )
    if not os.path.exists(script):
        raise HTTPException(
            status_code=404, detail="worktree_manager.py not found"
        )
    cmd = f"python3 {script} --repo {req.repo_path} --worktrees_dir {req.worktrees_dir} --action add --branch {req.branch}"
    try:
        out = run_cmd(cmd, timeout=60)
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504, detail="worktree creation timeout"
        )
    append_event(
        {
            "actor": identity.get("username"),
            "action": "git.worktree.add.result",
            "payload": out,
        }
    )
    return {"ok": True, "cmd": cmd, "result": out}


@router.post("/worktree/remove")
def remove_worktree(
    req: WorktreeReq, identity: dict = Depends(get_current_identity)
):
    assert_authorized(identity, "worktree_remove")
    script = os.path.join(os.getcwd(), "ops", "git", "worktree_manager.py")
    payload = {"repo": req.repo_path, "branch": req.branch, "action": "remove"}
    append_event(
        {
            "actor": identity.get("username"),
            "action": "git.worktree.remove.request",
            "payload": payload,
        }
    )
    if not os.path.exists(script):
        raise HTTPException(
            status_code=404, detail="worktree_manager.py not found"
        )
    cmd = f"python3 {script} --repo {req.repo_path} --action remove --branch {req.branch}"
    try:
        out = run_cmd(cmd, timeout=60)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="worktree removal timeout")
    append_event(
        {
            "actor": identity.get("username"),
            "action": "git.worktree.remove.result",
            "payload": out,
        }
    )
    return {"ok": True, "cmd": cmd, "result": out}


class SandboxReq(BaseModel):
    repo_path: str
    cmd: str = "pytest -q"
    timeout: int = 30


@router.post("/sandbox")
def run_in_sandbox(
    req: SandboxReq, identity: dict = Depends(get_current_identity)
):
    assert_authorized(identity, "sandbox_run")
    script = os.path.join(os.getcwd(), "sandbox", "run_in_sandbox.py")
    if not os.path.exists(script):
        raise HTTPException(status_code=404, detail="sandbox runner not found")
    payload = {"cmd": req.cmd, "cwd": req.repo_path, "timeout": req.timeout}
    append_event(
        {
            "actor": identity.get("username"),
            "action": "git.sandbox.request",
            "payload": payload,
        }
    )
    try:
        p = subprocess.run(
            ["python3", script],
            input=json.dumps(payload).encode(),
            capture_output=True,
            timeout=req.timeout + 10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="sandbox timeout")
    out = None
    try:
        out = json.loads(p.stdout.decode())
    except Exception:
        out = {
            "raw": p.stdout.decode(),
            "stderr": p.stderr.decode(),
            "rc": p.returncode,
        }
    append_event(
        {
            "actor": identity.get("username"),
            "action": "git.sandbox.result",
            "payload": out,
        }
    )
    return {"ok": True, "result": out}
