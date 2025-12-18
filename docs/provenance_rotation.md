# Provenance Secret Rotation Procedure

## Overview
This document defines the procedure for rotating the `PROV_SECRET` used for cryptographic provenance of conversation logs and tool outputs.

## Rotation Schedule
- **Frequency**: Monthly (1st of every month).
- **Trigger**: Automated alert or manual execution.

## Procedure

### 1. Generate New Secret
Generate a new high-entropy secret (min 32 bytes).
```bash
openssl rand -hex 32
```

### 2. Update Environment
Update the `.env` file or secrets manager with the new value:
```bash
PROV_SECRET=<new_secret>
PROV_SECRET_PREV=<old_secret>  # Retain for verification of recent logs
```

### 3. Restart Services
Restart the MCP server to pick up the new secret.
```bash
docker compose restart mcp-server
```

### 4. Verify Rotation
Run the verification script to ensure the new secret is active and signing correctly.
```bash
python scripts/verify_provenance.py --test-sign
```

### 5. Archive Old Key
Store the old key in the secure vault with a timestamp for historical audit capability.
