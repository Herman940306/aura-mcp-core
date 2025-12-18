# Pull Request: PRD Compliance & Gating Evidence

## Overview

Describe the scope and goals of this PR. Confirm adherence to `AURA_IA_MCP_PRD.md` and Section 8.

## SAFE MODE & Capabilities

- [ ] `AURA_SAFE_MODE` remains `true` (transition requires explicit reviewer-approved label)
- [ ] No capability flags enabled unless explicitly approved:
  - `ENABLE_TRAINING=false`
  - `ENABLE_AUTONOMY=false`
  - `ENABLE_ROLE_MUTATION=false`

## CI Jobs

Ensure the following workflow is green:

- [ ] PRD Compliance & Gating (`.github/workflows/compliance.yml`)
  - Verifies PRD alignment
  - Runs structure audit
  - Enforces SAFE MODE transition guard
  - Executes gating/policy tests
  - Uploads `logs/` artifact and appends audit tail to step summary

## Evidence

- CI run link: (paste URL)
- Logs artifact link: (paste URL)
- Audit tail (last ~20 lines from `logs/security_audit.jsonl`):

```jsonl
<paste audit tail here>
```

## Notes

- Do not flip SAFE MODE in this PR. Use label `allow-safe-mode-off` (or `transition-approved`) and a dedicated PR when reviewers approve.
- Transient staging dirs are tolerated in PR; they must be removed immediately after merge (push) per PRD hygiene.

## Summary

Describe the change and its motivation.

## PRD / Section 8 Alignment

- [ ] Ports unchanged or updated with approval
- [ ] Role Engine impact assessed
- [ ] SAFE_MODE respected

## Checklist

- [ ] Tests added/updated
- [ ] Docs updated
- [ ] Lint & type-check pass
- [ ] Structure audit passes

## Risk / Rollback

Outline rollback strategy.
 