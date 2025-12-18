# Full Agent Implementation Guide (Deep Specification)

This document instructs an agent (autonomous developer) how to implement, test, and integrate features into the MCP mono-repo in a safe, auditable, and reversible manner. The guide assumes the agent has access to the MCP sandbox, CI, and the role registry with appropriate permissions.

---

## Goals
1. Implement new features or modify existing ones according to MCP Spec v3.0.
2. Maintain security, quality, and auditability.
3. Use sandboxed development, CI verification, and a gated merge process.
4. Produce clear manifests, tests, and documentation for every change.

---

## High-Level Workflow (Agent Execution Plan)
1. **Intake & Scope**
   - Accept user instruction or internal self-assessment ticket with an objective.
   - Create a short proposal: purpose, success criteria (metrics), estimated artifacts, and tests.
   - Register proposal in `ops/approvals` for audit; if AUTO_APPROVE disabled, submit to Approval Queue.

2. **Research & Feasibility**
   - Run `deep_researcher_start` to gather documentation, libraries, and prior art.
   - Score candidate approaches on: Security, Complexity, Dependencies, Cost, Performance.
   - Produce a Research Summary (save to `data/learning/<timestamp>_research.json`).

3. **Design**
   - Produce an interface contract (JSON Schema) for any new tool/endpoint.
   - Create a spec fragment: routes, arguments, return types, ACL requirements.
   - Draft tests (unit & integration) that will validate the contract.

4. **Sandboxed Prototype**
   - Create isolated workspace under `sandbox/workspaces/<ticket-id>`.
   - Generate code scaffold (use templates from `agents/templates/`).
   - Use `sandbox/runner.py` to execute the prototype with simulated inputs.
   - Log runtime traces to `sandbox/logs/<ticket-id>.log`.

5. **Automated Tests**
   - Add unit tests under `tests/` mirroring the contract.
   - Add integration tests simulating interactions with mocked services (e.g., mocked model endpoints).
   - Run tests locally via `mcp-dev test` and capture outputs.

6. **Quality Gates**
   - Enforce linting (flake8), formatting (black), and type checks (mypy) in the workspace.
   - Ensure code coverage threshold (configurable; default 85%).
   - Ensure hallucination safeguards present: evidence assertions, confidence scoring, external verification calls for low-confidence outputs.

7. **SBOM & Dependency Check**
   - Update `requirements.txt` if dependencies added.
   - Run `syft` to produce SBOM and run CVE lookup (OSV/GitHub security API if available).
   - If vulnerable packages found, either select alternatives or submit security exception via `ops/approvals`.

8. **PR Generation (Self-PR Tool)**
   - Generate a draft PR branch using `ops/role_engine/pr_helper.py` or git worktree.
   - Include:
     - Description referencing Spec sections
     - Automated test results
     - SBOM artifact
     - Sandbox logs
     - Risk assessment and rollback plan

9. **CI & Sandbox Validation**
   - Trigger CI workflow `ci.yml` in a sandbox context (no merge).
   - Validate: tests pass, drift checks pass, linting OK, SBOM uploaded.
   - If CI fails, iterate locally until passing.

10. **Approval & Merge**
    - Submit PR for review or autosubmit if auto-merge policies satisfied.
    - If self-integration is enabled, mark PR with `self-generated` label and record change in `ops/role_engine/audit_provenance.py`.
    - Upon approval, merge and tag with version and changelog entry.

11. **Post-Merge Monitoring**
    - Run a canary deployment (model or route) if applicable.
    - Monitor metrics for configurable window (default 24-72 hours).
    - Capture telemetry and drift metrics.
    - If regressions found, initiate automatic rollback and create a hotfix ticket.

---

## Implementation Rules (MANDATORY)
- **Never** modify production code outside sandbox without a successful PR and tests.
- **Every** code change must include test(s).
- **All** new endpoints require OpenAPI schema entries.
- **Evidence-first**: outputs from agents that assert facts must include citations or references to source artifacts. If confidence < 0.6, call `ref_read_url` or `ref_search_documentation`.
- **Changelog**: append to `docs/CHANGELOG_SELF_IMPROVE.md` with timestamp, agent id, summary, and roll-forward plan.
- **Audit log**: write structured audit entries to `logs/security_audit.jsonl` and `logs/mcp_tool_spans.jsonl` for every action that changes state.

---

## Artifact Manifest (per task)
Each completed task must produce:
- `workspace/<ticket-id>/manifest.json`:
  - author (agent id)
  - ticket_id
  - description
  - files_changed (list)
  - tests (list)
  - sbom (path)
  - sandbox_log (path)
  - risk_level
- `docs/<ticket-id>_design.md` — human-readable design and decision log.
- PR branch with tests and CI report linked.

---

## Testing Strategy
- **Unit tests**: isolate functions, use dependency injection for model calls.
- **Integration tests**: use local mocks or containerized stubs for external services.
- **E2E tests**: run within sandboxed container replicating production environment variables.
- **Property tests**: for reasoning pipelines, validate invariants (e.g., output contains citation when answer claims fact).
- **Hallucination tests**:
  - Create negative cases (contradictory prompts).
  - Measure hallucination score; must be < 0.15 for production-critical features.
  - If score between 0.15–0.3, mark as canary-only with human approvals.

---

## Security & Compliance
- Secrets must be injected from vaults; never hard-coded.
- Use least privilege for any agent tokens.
- All internal reasoning logs containing sensitive data must be encrypted at rest.
- Approval required for any privilege escalation or host access; record in audit log.

---

## Self-Improvement Specifics
- Feature generation by agent must follow the same PR & approval workflow as human devs.
- Implement a "self-checklist" in `ops/self_improve/checklist.json` and verify all items before merge.
- Maintain a "safe-mode" flag to disable autonomous merges in sensitive environments.

---

## Debugging & Observability
- Ensure traces follow OpenTelemetry conventions.
- Each agent run must emit: correlation_id, start/end timestamps, actions performed, external calls, and confidence metrics.
- Expose a dashboard endpoint for pending self-improvement jobs and their status.

---

## Recovery & Rollback
- Each merge must create an automatic rollback point (git tag + snapshot of DB schema).
- Define rollback playbook in `docs/rollback_playbook.md`.
- In case of unsafe self-modification, auto-revert changes and notify operators via configured alerting channel.

---

## Agent Identity & Accountability
- Agents must sign artifacts with an internal agent id and key.
- Every PR and commit from an agent must include metadata: agent_id, model_version, policy_version, and evidence links.

---

## Final Notes
This guide is the authoritative instruction set for any automated agent that intends to implement or modify MCP. Agents must be conservative: prefer human approval for high-risk changes, use sandboxed execution, and always attach evidence and tests.
