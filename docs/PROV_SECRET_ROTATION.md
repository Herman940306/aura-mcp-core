# PROV_SECRET Rotation Procedure

Purpose: Maintain integrity and forward-trust of provenance / audit chains while enabling scheduled or emergency secret rotation without breaking verification.

## 1. Overview

`PROV_SECRET` is used to derive HMAC / hash digests (e.g., SHA-256 / BLAKE3) for provenance entries, linking tool invocation events, model inferences, and approval decisions. Rotating it periodically reduces long-term exposure risk and supports cryptographic agility.

Rotation Modes:

- Scheduled (standard cadence; e.g. every 90 days)
- Emergency (compromise suspected or confirmed)
- Architectural (algorithm upgrade, length adjustment)

## 2. Key Principles

- Never commit raw secrets to the repository.
- Store secrets only in secure vault / secrets manager (Azure Key Vault, AWS Secrets Manager, HashiCorp Vault, etc.).
- Support dual-write window: old + new secret concurrently applied for a bounded interval (e.g., 24h) to avoid gaps.
- Maintain an immutable audit record of rotation events.
- All provenance entries must indicate which key version signed them.

## 3. Versioning Strategy

Use monotonically increasing integer or date-based versions, e.g.:

```
PROV_SECRET_V1=<old>
PROV_SECRET_V2=<new>
PROV_SECRET_ACTIVE_VERSION=2
```

Application selects secret by `PROV_SECRET_ACTIVE_VERSION`. Older versions retained only for validation window, then purged.

## 4. Generation (Platform Examples)

Linux / macOS:

```bash
openssl rand -hex 32  # 256-bit hex
```

PowerShell (Windows):

```powershell
[Convert]::ToHexString((New-Object byte[] 32 | % { (Get-Random -Min 0 -Max 256) }))
```

Python (ad-hoc):

```python
import secrets; print(secrets.token_hex(32))
```

Minimum length: 32 bytes (256 bits) recommended.

## 5. Dual-Write Transition

1. Introduce `PROV_SECRET_V_NEXT` alongside current version.
2. Begin writing new provenance records using active version (NEXT).
3. Continue accepting validation requests signed with previous version for a grace period.
4. Monitor verification error rate; must remain 0.
5. After window expires, decommission old secret: remove from environment and vault (or mark disabled).

## 6. Rotation Steps (Scheduled)

| Step | Action | Output |
|------|--------|--------|
| 1 | Generate new secret | Secure random 256-bit value |
| 2 | Store in vault with incremented version | Vault entry `provenance/secret/v2` |
| 3 | Update deployment manifests / `.env` (no commit of value) | New env vars applied |
| 4 | Redeploy services with dual-write validation | Logs show both versions recognized |
| 5 | Record rotation event in `security_audit.jsonl` | Immutable audit line |
| 6 | Monitor & verify digests for 24h | 0 verification errors |
| 7 | Remove old secret from active set | Only v2 remains |
| 8 | Finalize: mark rotation complete | Audit completion entry |

## 7. Emergency Rotation

Trigger Conditions: suspected leak, anomalous access, hash chain tampering.
Procedure delta:

- Reduce or eliminate grace period (immediate invalidation of prior version if risk high).
- Perform forced re-sign of any cached ephemeral provenance needing continuity (optional).
- Increase monitoring frequency (e.g. every 5 minutes integrity check).

## 8. Audit Logging Template

Append JSON lines to `logs/security_audit.jsonl`:

```json
{
  "ts": "2025-11-24T13:05:12Z",
  "event": "prov_secret.rotation.begin",
  "new_version": 2,
  "mode": "scheduled",
  "actor": "automation.pipeline"
}
{
  "ts": "2025-11-25T13:05:14Z",
  "event": "prov_secret.rotation.complete",
  "active_version": 2,
  "retired_version": 1
}
```

For emergency:

```json
{
  "ts": "2025-11-24T13:05:12Z",
  "event": "prov_secret.rotation.emergency",
  "new_version": 3,
  "revoked_versions": [1,2],
  "reason": "suspected compromise",
  "actor": "security.engineer"
}
```

## 9. Validation & Integrity Checks

- Hash Chain Continuity: verify previous record hash matches `prev_digest` pointer.
- Key Version Coverage: no records without `key_version` attribute.
- Drift Detection: track count of failed validations; threshold triggers alert.

Suggested metrics (integrate with taxonomy):

- `provenance_rotation_events_total{mode}`
- `provenance_validation_failures_total`
- `provenance_active_key_version`

## 10. Security Considerations

- All secrets must be rotated out of memory on shutdown (zeroization for in-memory objects if feasible).
- Prevent exposure via logs (log only version, never value).
- Restrict secret environment variable access to container scope (no exec into container for non-admin roles).
- Enable Vault policies enforcing read-only access and no historical list for general service accounts.

## 11. Testing Strategy

Unit:

- Simulate dual-write: confirm validation passes for old + new.
- Verify invalid version fails.
Integration:
- Deploy with active v1 then rotate to v2, confirm post-rotation validation success.
Security:
- Attempt provenance replay with retired secret → must fail.

## 12. Rollback Strategy

If rotation causes unexpected verification failures:

1. Pause ingestion (set SAFE MODE if critical).
2. Re-enable prior version temporarily (`PROV_SECRET_ACTIVE_VERSION` rollback).
3. Diagnose diff (hash algorithm mismatch? truncation?).
4. Re-run validation test suite.
5. Re-attempt rotation with corrected parameters.

## 13. Automation Hooks

- CI pipeline step to prepare next version (no activation).
- GitOps diff detection: if `PROV_SECRET_ACTIVE_VERSION` increments, auto-run validation smoke tests.
- Alert if active version age > policy threshold (e.g. > 100 days).

## 14. Future Enhancements

- Merkle tree or blockchain-style anchor for external notarization.
- Hardware-backed sealing (TPM / HSM integration).
- Split secret derivation (Shamir shares for high-assurance environments).
- Post-quantum algorithm agility placeholder.

---
Document owner: Security Engineering / Provenance Subsystem
Revision: 2025-11-24 (initial)
