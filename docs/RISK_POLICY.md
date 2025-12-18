# Risk Policy

## Scoring Bands

| Band | Range | Reviewer Action |
|------|-------|-----------------|
| Low | 0-19 | Auto-approve if tests green |
| Medium | 20-49 | Single security reviewer sign-off |
| High | 50+ | Dual approval (security + owner), evidence bundle required |

## Evidence Bundle Contents (High)

- Policy decision log excerpt (last 5 entries)
- Test matrix results
- Capability state diff
- SBOM hash + container scan summary

## Escalation

High risk changes trigger creation of a GitHub issue labeled `risk-review` prior to merge.

## Audit Correlation

Each policy decision includes `risk_score`; monitoring dashboards aggregate average and P95. Spikes above threshold emit alert.
