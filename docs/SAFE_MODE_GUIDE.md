# SAFE MODE Operational Guide

## Purpose

SAFE MODE provides a controlled execution envelope limiting mutating or high-risk capabilities while preserving core observability, provenance logging, and read/analysis tools. It enables:

- Rapid incident containment
- Forensic trace integrity
- Deterministic low-variance behavior for evaluation

## Activation

Set the environment variable before launching the MCP server:

```powershell
$env:IDE_AGENTS_SAFE_MODE = "1"
python start_mcp_with_backend.py
```

Or using Linux/macOS shell:

```bash
IDE_AGENTS_SAFE_MODE=1 python start_mcp_with_backend.py
```

## Effects

When SAFE MODE is enabled:

- Tool execution gating: `ide_agents_command` requires explicit approval for all `run` method calls.
- High-risk / mutation tools may be hidden or return approval envelopes.
- Background ML / ULTRA pipelines are disabled unless explicitly whitelisted.
- Provenance logging continues (tool success/failure and duration) into `logs/provenance.jsonl`.
- Security anomaly detector remains active; thresholds unchanged.
- Rate limiting remains enforced to prevent burst escalation.

## Verification Checklist

After enabling SAFE MODE execute:

```powershell
python scripts/check_readyz.py
python scripts/verify_stack.ps1
python scripts/test_mcp_client.py
```

Confirm:

- `readyz.status` is `ready` or `degraded` with `backend_ok` reflecting backend health.
- No unapproved command runs succeed (receive `approval_required` envelope).
- Metrics endpoint `/metrics` exposes tool counters and backend health gauges.
- Provenance file growing with tool invocation entries.

## Approval Flow

1. Attempt a command tool invocation.
2. Server returns JSON error envelope with `approval_required`.
3. An operator reviews pending actions (via admin surface or future `ide_agents_approval_list`).
4. Operator sets approval (future stub) or injects simulated approval in tests.
5. Re-run command; execution proceeds with audit log entry.

## Rollback / Deactivation

Unset the flag and restart services:

```powershell
Remove-Item Env:IDE_AGENTS_SAFE_MODE
python start_mcp_with_backend.py
```

Or:

```bash
unset IDE_AGENTS_SAFE_MODE
python start_mcp_with_backend.py
```

## Observability

Key metrics to monitor while in SAFE MODE:

- `tool_invocations_total{tool=...}` success/failure trends.
- `backend_health_success_total` vs `backend_health_failure_total`.
- `backend_health_latency_ms` histogram or gauge distribution.
- Performance summary (`/performance`) for throughput drift post activation.

## Security & Provenance

- All tool failures are logged with exception class.
- Approval denials produce audit entries enabling later reconstruction.
- SICD training stub continues to record episodes safely if invoked (non-mutating).

## Recommended Response Procedure

1. Activate SAFE MODE.
2. Capture baseline snapshot (`ide_agents_metrics_snapshot`, `/performance`).
3. Drain / pause mutation workflows (CI auto-deploy, command exec loops).
4. Investigate anomalies via `ide_agents_security_anomalies` tool.
5. Apply targeted fixes (with manual approvals).
6. Exit SAFE MODE once metrics stabilize for two consecutive observation windows.

## Future Extensions

- Add `ide_agents_safe_status` tool for explicit SAFE MODE state reporting.
- Implement approval persistence layer (encrypted queue).
- Integrate dynamic capability profile switching based on anomaly severity.

Maintained: November 24, 2025
