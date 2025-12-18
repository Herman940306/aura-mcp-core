# Capability Flags & SAFE MODE

This document defines the governance and operational semantics of the runtime control flags.

## Flags

| Variable | Default | Description | Requires SAFE MODE Off | Combined Gate |
|----------|---------|-------------|------------------------|---------------|
| `AURA_SAFE_MODE` | `true` | Global kill switch restricting privileged routes. | N/A | N/A |
| `ENABLE_AUTONOMY` | `false` | Enables autonomous action loops beyond single request scope. | Yes | `not SAFE_MODE and ENABLE_AUTONOMY` |
| `ENABLE_TRAINING` | `false` | Allows initiation of training episodes / simulations. | Yes | `not SAFE_MODE and ENABLE_TRAINING` |
| `ENABLE_ROLE_MUTATION` | `false` | Permits role/permission mutation endpoints. | Yes | `not SAFE_MODE and ENABLE_ROLE_MUTATION` |

## Transition Auditing

State transitions emit two audit events:

These events are appended to `logs/security_audit.jsonl` and must be included in integration evidence bundles when altering flags through PRs.

## Change Control

1. All flag changes occur via PR.
2. Reviewers validate risk and attach evidence (tests, audit log excerpt).
3. SAFE MODE may only be disabled after completion of Phases 0–8 and green test suite.
4. Bulk enabling of all capabilities requires explicit security approval.

## Testing Matrix (Example)

| SAFE_MODE | AUTONOMY | TRAINING | ROLE_MUTATION | Expected Restricted Response |
|-----------|----------|----------|---------------|------------------------------|
| true | any | any | any | 423 Locked |
| false | false | true | false | 403 Forbidden (training gated by autonomy false) |
| false | true | false | true | 200 OK for role mutation; training endpoints 403 |
| false | true | true | true | 200 OK for all enabled capability routes |

## Observability

Metrics counters recommended:

- `capability_transition_total{flag="name",to="value"}`
- `safe_mode_active` gauge (0/1)

Centralizing capability gating assures consistent enforcement and auditability, enabling defensible activation of higher-risk behaviors only after maturity milestones.
