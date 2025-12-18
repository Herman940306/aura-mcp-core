# SAFE MODE Transition Plan

This document defines the governed procedure to evaluate and, if approved, flip `AURA_SAFE_MODE` from `true` to `false` in the Aura IA MCP stack.

## 1. Preconditions

- PRD alignment passes (`scripts/verify_prd_alignment.py --ci`).
- Structure audit clean (`scripts/audit_structure.py`).
- Gating & policy tests green (CI: PRD Compliance & Gating).
- Audit log shows stable decisions without unexpected denies.
- Transient staging artifacts removed.
- Reviewer consensus (minimum 2 approvals) on readiness.

\n## 2. Required PR Label
Add one of the following labels to the transition PR to bypass SAFE MODE enforcement in CI:
`allow-safe-mode-off`, `transition-approved`, or `approve-safe-mode-off`.

Without a label, the workflow `check_safe_mode_transition.py` will block a PR that changes the default.

## 3. Scope of the Transition PR

Changes limited strictly to:

1. Flip default in `aura_ia_mcp/core/config.py` (`AURA_SAFE_MODE: bool = False`).
2. (Optional) enable one capability flag at a time; defaults remain secure unless justified.
3. Update docs: Integration Checklist Phase 9 to reflect transition completion.
4. Add evidence section in PR description citing last 20 audit log lines post-flip (local dry-run).

No other refactors or feature additions are permitted in the transition PR.

## 4. Rollout Steps

1. Create branch `feature/safe-mode-transition`.
2. Apply default flip; keep capability flags off initially.
3. Run local compliance commands:

```bash
python scripts/verify_prd_alignment.py --ci
python scripts/audit_structure.py
pytest -q tests/test_policy_gateway.py tests/test_safe_mode_gating.py tests/test_training_policy.py
python scripts/generate_audit_sample.py
```

4. Capture audit tail (`tail -n 20 logs/security_audit.jsonl`).
5. Open PR with required label and template evidence.
6. Await reviewer approval; address any governance comments.
7. Merge; confirm CI green on push.

## 5. Post-Transition Monitoring

- Monitor `logs/security_audit.jsonl` for increased mutation or training requests.
- Add temporary alert (future enhancement) if > N denies or risk scores spike.
- Confirm no unauthorized capability flips.

## 6. Rollback Procedure

If unexpected behavior occurs:

1. Revert commit flipping SAFE MODE.
2. Re-run targeted tests to ensure gating restored.
3. Re-add label only after root cause analysis documented.

## 7. Capability Flag Enablement (Separate PRs)

After stable operation with SAFE MODE off:

- Submit one PR per flag (`ENABLE_TRAINING`, `ENABLE_AUTONOMY`, `ENABLE_ROLE_MUTATION`).
- Each PR must include: audit tail, justification, risk assessment, and pass policy tests.

## 8. Evidence Template Snippet

```markdown
### SAFE MODE Transition Evidence
PRD Alignment: PASS
Structure Audit: PASS
Targeted Tests: 10 passed
Audit Tail (last 10 lines):
```jsonl
<paste lines>
```
```

## 9. Approval Criteria Summary
| Criterion | Status | Notes |
|----------|--------|-------|
| PRD Alignment | Required | Must be clean |
| Structure Audit | Required | No unexpected entries |
| Tests | Required | Gating & policy suite green |
| Audit Stability | Required | No anomalous denies |
| Reviewer Approvals | ≥2 | Governance sign-off |
| Transition Label | Present | One approved label |

## 10. Non‑Goals
- Enabling all capabilities simultaneously.
- Introducing new tool types or policy engines.
- Altering risk scoring heuristics in the same PR.

---
Maintain strict scope: governance-first; minimize surface area of transition change.
