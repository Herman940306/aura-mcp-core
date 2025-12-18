# Policy Versioning and Migration Guide

## Overview

The Aura IA MCP policy management system provides version control, safe migrations, and rollback capabilities for OPA (Open Policy Agent) policies.

## Architecture

### Components

1. **PolicyVersionManager** - Manages policy versions and metadata
2. **PolicyMigrator** - Handles migrations with backup and rollback
3. **Policy Routes** - REST API for policy management
4. **Audit Trail** - Full history of all policy changes

### Directory Structure

```
aura_ia_mcp/ops/role_engine/
├── policy_versions/          # Version storage
│   ├── manifest.json         # Version registry
│   ├── 1.0.0/
│   │   ├── policy.rego       # Policy content
│   │   ├── metadata.json     # Version metadata
│   │   └── migration.py      # Optional migration script
│   └── 1.1.0/
│       └── ...
├── policies/                 # Active policies
├── backups/                  # Migration backups
└── migration_audit.json      # Migration history
```

## Usage

### Creating a New Policy Version

```bash
POST /admin/policies/versions
{
  "version": "1.1.0",
  "description": "Add new role constraints",
  "policy_content": "package authz\n\n...",
  "created_by": "admin@example.com"
}
```

### Listing Versions

```bash
GET /admin/policies/versions
```

Response:
```json
{
  "current_version": "1.0.0",
  "versions": [
    {
      "version": "1.0.0",
      "description": "Initial policy",
      "created_at": "2025-11-29T23:00:00Z",
      "created_by": "system"
    }
  ]
}
```

### Migrating to a New Version

#### Dry Run (Validate Only)

```bash
POST /admin/policies/migrate
{
  "to_version": "1.1.0",
  "dry_run": true
}
```

#### Actual Migration

```bash
POST /admin/policies/migrate
{
  "to_version": "1.1.0",
  "dry_run": false
}
```

Response:
```json
{
  "migration_id": "migration_20251129_230000",
  "status": "completed",
  "from_version": "1.0.0",
  "to_version": "1.1.0",
  "backup_path": ".../backups/backup_1.0.0_20251129_230000"
}
```

### Rolling Back a Migration

```bash
POST /admin/policies/rollback/migration_20251129_230000
```

### Viewing Migration History

```bash
GET /admin/policies/migrations
```

## Policy Validation

All policies are validated before creation/migration:

- Package declaration present
- Balanced braces and brackets
- Non-empty content
- Valid Rego syntax (basic checks)

## Audit Trail

Every policy change is logged with:
- Migration ID
- Timestamp
- Source and target versions
- Status (pending, completed, failed, rolled_back)
- Backup location
- Error details (if failed)

## Best Practices

### 1. Semantic Versioning

Use semantic versioning for policies:
- `MAJOR.MINOR.PATCH`
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### 2. Always Test with Dry Run

```bash
# 1. Dry run first
POST /admin/policies/migrate { "to_version": "1.1.0", "dry_run": true }

# 2. Review validation results

# 3. Apply if valid
POST /admin/policies/migrate { "to_version": "1.1.0", "dry_run": false }
```

### 3. Document Changes

Include detailed descriptions:
```json
{
  "version": "1.1.0",
  "description": "Add role-based access to /admin/policies endpoints. Requires 'policy_admin' role.",
  "policy_content": "..."
}
```

### 4. Migration Scripts

For complex migrations, include a migration script:

```python
# migration.py
def migrate():
    """
    Migrate user roles from old to new format.
    """
    # Update user role mappings
    # Notify affected users
    # etc.
```

### 5. Regular Backups

Backups are automatic, but verify backup integrity:
```bash
GET /admin/policies/migrations
# Check backup_path for recent migrations
```

## Security

### Access Control

Policy management endpoints require `policy_admin` role:

```rego
package authz

allow {
    input.path = "/admin/policies"
    input.user.roles[_] = "policy_admin"
}
```

### Provenance Chain

All policy changes are cryptographically signed:
- Version checksums (SHA-256)
- Timestamp verification
- Creator attribution

## Rollback Safety

Rollbacks are only allowed for:
- Completed migrations
- Migrations with valid backups
- Recent migrations (configurable retention)

## Monitoring

Track policy health with metrics:
- `policy_migrations_total` - Total migrations
- `policy_migrations_failed` - Failed migrations
- `policy_rollbacks_total` - Total rollbacks
- `policy_validation_errors` - Validation failures

## Troubleshooting

### Migration Failed

1. Check validation errors:
   ```bash
   POST /admin/policies/migrate { "to_version": "X", "dry_run": true }
   ```

2. Review migration history:
   ```bash
   GET /admin/policies/migrations
   ```

3. Rollback if needed:
   ```bash
   POST /admin/policies/rollback/{migration_id}
   ```

### Rollback Failed

- Verify backup exists
- Check file permissions
- Review audit log

### Policy Validation Errors

Common issues:
- Missing package declaration
- Syntax errors (unbalanced braces)
- Empty content

## Example Workflow

```bash
# 1. Create new version
POST /admin/policies/versions
{
  "version": "2.0.0",
  "description": "Major refactor - new RBAC model",
  "policy_content": "package authz\n\ndefault allow = false\n..."
}

# 2. Validate migration
POST /admin/policies/migrate
{
  "to_version": "2.0.0",
  "dry_run": true
}

# 3. Apply migration
POST /admin/policies/migrate
{
  "to_version": "2.0.0",
  "dry_run": false
}

# 4. Monitor (if issues occur)
GET /admin/policies/migrations

# 5. Rollback if needed
POST /admin/policies/rollback/{migration_id}
```

## Compliance

Policy versioning supports:
- **SOC2**: Complete audit trail
- **GDPR**: Policy change tracking
- **HIPAA**: Access control versioning
