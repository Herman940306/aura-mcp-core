# ARE+ Coding & Operational Guidelines

These guidelines enforce Section 8 of `AURA_IA_MCP_PRD.md` and system values (anti-hallucination, transparency, self-improvement, code quality, optimization).

## Core Principles

- Determinism: Prefer clear, testable logic; avoid hidden side effects.
- Transparency: Always disclose uncertainty; never fabricate sources.
- Safety: Respect SAFE MODE and capability flags; blocked actions return 423/403.
- Governance Alignment: All changes must align with PRD mission & port map.
- Minimal Diffs: Scope changes tightly; remove dead code while refactoring.
- Traceability: Every change must be auditable (log intent + outcome).

## Required Workflow (Agent Loop)

1. Ingest: Read PRD, relevant docs, constraints.
2. Plan: Produce structured change plan (scope, files, risks, tests).
3. Validate Safety: Port map, structure, role policy, SAFE MODE status.
4. Implement: Follow style, architecture boundaries, naming.
5. Test: Run unit + integration tests; ensure coverage >= 80% for governed modules.
6. Document: Update README/PRD if architecture or behavior changed.
7. Audit: Record reasoning, decisions, and structure compliance.
8. Output: Provide diff summary + confidence + risk assessment.

## Code Quality Standards

- Formatting: `black` auto-format; imports organized.
- Type Checking: Pyright strict; zero untyped public APIs.
- Linting: `flake8` (style + complexity) → fail on error.
- Security: Run `bandit` for high-risk modules (`ops/role_engine`, `mcp/server`).
- Coverage: Fail if < 80%; critical governance code target 90%+.
- Complexity: Functions over 40 logical lines require justification or refactor plan.

## Anti-Hallucination & No-Lie Enforcement

- LLM outputs must conform to `ops/guards/llm_output_schema.json`.
- Use `hallucination_checker.support_score()`; if score < 0.3 → mark `unverified` and propose retrieval.
- Provide rationale steps; never invent endpoints, ports, secrets, or repositories.

## SAFE MODE & Capability Gating

- Never disable SAFE MODE outside approved transition PR.
- Capability flags (`ENABLE_TRAINING`, etc.) must be validated before state changes.
- Endpoints requiring mutation/training escalate to approval workflow when gated.

## Role & Policy Integration

- Tool or role changes must update `ops/role_engine/role_registry_v2.json` via draft mechanism.
- Evaluate tasks through role selector + negotiator; record chosen roles & confidence.
- OPA policies (`role_policy_full.rego`, `no_lie.rego`) must be consulted for high-risk actions.

## Logging & Audit

- Append provenance events with HMAC (`audit_provenance.append_event`).
- Include: timestamp, actor roles, action, risk score, sources, verdict.
- Rotate logs when >5MB; maintain last N=5 archives.

## Folder Placement Rules

- New code must reside in: `aura_ia_mcp/`, `mcp/`, `ops/`, `training/`, `tools/`, `tests/`, `docs/`, `.vscode/`, `docker/`, `k8s/`.
- Reject root-level stray files; use `scripts/audit_root_new_files.py` in CI.

## Commit Discipline

- One logical feature per commit (or grouped minor hygiene).
- Include summary referencing PRD section if structural change.
- No large unreviewed vendor blobs; prefer requirements locking.

## Self-Improvement Signals

- After test failure or coverage dip: trigger SICD proposal (draft branch).
- Log improvement episodes with delta metrics (coverage change, risk reduction).
- Periodically recalibrate confidence scoring.

## Security & Secrets

- Never hardcode secrets; use env variables or secrets management.
- Validate external calls; avoid arbitrary shell without allowlist.

## Exception Handling

- Catch narrowly; propagate meaningful HTTP statuses.
- Avoid blanket `except Exception`; prefer specific error classes.

## Performance Considerations

- Use async for IO-bound FastAPI endpoints.
- Batch external requests (GitHub, embeddings) to reduce latency.
- Cache immutable config using singleton pattern.

## Review Checklist (Pre-merge)

- Ports unchanged (9200–9206) unless PRD updated.
- SAFE MODE still active (unless transition PR).
- No stray root artifacts.
- Logs contain provenance for new roles/tools.
- Tests green; coverage thresholds met.
- LLM tool outputs validate schema; hallucination guard active.

## Violation Handling

- Minor: Add fix commit + audit entry.
- Major (port change, SAFE MODE disable without approval): Reject PR; require governance escalation.
- Repeated violations: Trigger policy enforcement + role negotiation downgrade.

## Quick Reference Commands

```bash
# Type check
pyright
# Lint & style
flake8 && black --check .
# Security scan
bandit -r .
# Tests + coverage
coverage run -m pytest && coverage report
# Root hygiene audit
python scripts/audit_root_new_files.py
```

## Confidence & Risk Reporting Template

```json
{
  "change_id": "<uuid>",
  "scope": ["feature", "hygiene"],
  "risk": 0.15,
  "confidence": 0.88,
  "roles": ["Lead Engineer", "Security & Compliance Officer"],
  "safe_mode": true,
  "audit_ref": "logs/role_provenance.log"
}
```

Adherence to these guidelines is mandatory for agents and contributors until superseded by a PRD revision.
