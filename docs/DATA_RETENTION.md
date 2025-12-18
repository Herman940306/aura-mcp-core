# Data Retention Policy

## Scope

Applies to audit logs, metrics, and transient training artifacts.

## Retention Periods

| Data Type | Path / System | Retention | Action After |
|-----------|---------------|-----------|--------------|
| Audit Logs | logs/security_audit.jsonl | 30 days | Rotate + archive (compressed) |
| Metrics Time Series | Prometheus TSDB | 15 days | Compaction + remote write (optional) |
| Training Episodes (stub) | training/episodes/ | 7 days | Purge |
| SBOMs | SBOM/ | 90 days | Replace on regeneration |

## Purge Mechanism

Scheduled CI job invokes `python scripts/purge_artifacts.py --dry-run` and then `--apply` on approval.

## Compliance

Retention changes require security approval and PR documentation.
