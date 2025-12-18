# MCP Git Tool Integration

This document describes how MCP agents and operators call the git/worktree/sandbox endpoints.

## Endpoints
- `POST /internal/git/sync` — incremental smart sync
  - body: `{ "repo_path": "/abs/path", "remote": "https://...", "ref": "origin/main" }`
- `POST /internal/git/worktree/add` — create a worktree branch
  - body: `{ "repo_path": "/abs/path", "branch": "ai/proposal/..." }`
- `POST /internal/git/worktree/remove` — remove worktree
  - body: `{ "repo_path": "/abs/path", "branch": "ai/proposal/..." }`
- `POST /internal/git/sandbox` — run a command in sandbox runner
  - body: `{ "repo_path": "/abs/path", "cmd": "pytest -q", "timeout": 60 }`

## Security & governance
- Only identities with roles in `ALLOWED_ROLES` are permitted.
- All requests/outputs are recorded via `ops.role_engine.audit_provenance.append_event`.
- Sandbox runner must be hardened in production (use Docker with `--network none` and read-only mounts).

## Usage
1. Agent calls `/internal/git/sync` to ensure repo up-to-date.
2. Agent calls `/internal/git/worktree/add` to get a private worktree path.
3. Agent writes files into the worktree path.
4. Agent calls `/internal/git/sandbox` to run tests.
5. Agent requests PR creation with `tools/self_pr_tool.py` (existing SICD PR helper).
6. Human reviews evaluation artifacts and merges.

