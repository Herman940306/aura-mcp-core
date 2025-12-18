#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "=== MCP ARE++ OVERDRIVE Verification Test ==="
echo "Repo: $REPO_DIR"
echo

FAIL_COUNT=0

fail() {
    echo "❌ $1"
    FAIL_COUNT=$((FAIL_COUNT+1))
}

pass() {
    echo "✔ $1"
}

check_file() {
    local f="$REPO_DIR/$1"
    if [[ ! -f "$f" ]]; then
        fail "Missing file: $1"
    else
        pass "File present: $1"
    fi
}

check_dir() {
    local d="$REPO_DIR/$1"
    if [[ ! -d "$d" ]]; then
        fail "Missing directory: $1"
    else
        pass "Directory present: $1"
    fi
}

echo "=== Checking Directory Structure ==="

check_dir "ops/role_engine"
check_dir "ops/role_engine/schemas"
check_dir "ops/opa/policies"
check_dir "ops/approvals"
check_dir "mcp/roles"
check_dir "mcp/server"
check_dir "training/roles"
check_dir "docs"

echo
echo "=== Checking Critical Files ==="

check_file "ops/role_engine/role_registry.json"
check_file "ops/role_engine/role_service.py"
check_file "ops/role_engine/INSTALL_OPTIONS.env"
check_file "ops/role_engine/schemas/role_schema.json"
check_file "ops/role_engine/schemas/auto_role_patch_schema.json"

check_file "mcp/roles/selector.py"
check_file "mcp/roles/negotiator.py"
check_file "mcp/server/auth_roles.py"
check_file "mcp/server/role_audit.py"

check_file "ops/opa/policies/role_policy.rego"

check_file "training/roles/selector_training_stub.py"
check_file "training/roles/etl_pipeline_stub.py"

check_file "docs/ARE_PLUS_README.md"

echo
echo "=== Running Sanity Tests ==="

echo "- Testing role registry JSON validity..."
python3 - <<EOF
import json,sys,os
path=os.path.join("$REPO_DIR","ops/role_engine/role_registry.json")
try:
    json.load(open(path))
except Exception as e:
    print("❌ role_registry.json invalid:",e)
    sys.exit(1)
print("✔ role_registry.json is valid JSON")
EOF

echo "- Testing role API service imports..."
python3 - <<EOF
try:
    import importlib
    importlib.import_module("ops.role_engine.role_service")
    print("✔ Python role_service imported successfully")
except Exception as e:
    print("❌ Import failure:",e)
    exit(1)
EOF

echo "- Testing MCP auth modules..."
python3 - <<EOF
for mod in ["mcp.server.auth_roles","mcp.server.role_audit"]:
    try:
        __import__(mod)
        print(f"✔ {mod} imported")
    except Exception as e:
        print(f"❌ Failed to import {mod}:",e)
        exit(1)
EOF

echo
echo "=== Testing OPA Policy Parsing ==="
opa check "$REPO_DIR/ops/opa/policies/role_policy.rego" \
    && pass "OPA policy valid" \
    || fail "OPA policy invalid"

echo
echo "=== Testing Approval Queue ==="

if [[ -d "$REPO_DIR/ops/approvals" ]]; then
    touch "$REPO_DIR/ops/approvals/test.approval"
    if [[ -f "$REPO_DIR/ops/approvals/test.approval" ]]; then
        pass "Approval queue backend working"
    else
        fail "Approval queue write failed"
    fi
    rm -f "$REPO_DIR/ops/approvals/test.approval"
else
    fail "Missing approvals directory"
fi


echo
echo "=== Testing Auto-Improvement Hooks ==="

check_file "ops/role_engine/auto_improve_rules.json"
check_file "ops/role_engine/auto_improve_engine.py"

python3 - <<EOF
try:
    import ops.role_engine.auto_improve_engine
    print("✔ Auto-improvement engine import OK")
except Exception as e:
    print("❌ Auto-improve import failed:",e)
    exit(1)
EOF


echo
echo "=== Testing Logging & Memory Components ==="

check_dir "ops/memory"
check_file "ops/memory/vector_store_stub.py"
check_file "ops/memory/memory_etl.py"


echo
echo "=== FINAL RESULT ==="

if [[ "$FAIL_COUNT" -gt 0 ]]; then
    echo "❌ Verification FAILED — Issues found: $FAIL_COUNT"
    exit 1
else
    echo "🎉 ALL TESTS PASSED — ARE++ OVERDRIVE installed correctly"
    exit 0
fi
