#!/usr/bin/env bash
set -e
echo "=== SANITY: ARE+ ==="
python3 - <<'PY'
import json
r=json.load(open('ops/role_engine/role_registry_v2.json'))
print('roles_count:',len(r['roles']))
PY
python3 mcp/roles/selector_advanced.py "run tests and prepare patch"
echo "=== DONE ==="
