#!/usr/bin/env bash
set -euo pipefail
python -m pip install --upgrade pip >/dev/null
pip install pip-audit safety licensechecker || true
echo "Running pip-audit"; pip-audit || true
echo "Running safety"; safety check || true
if command -v licensechecker >/dev/null 2>&1; then
  echo "Running license checker"; licensechecker || true
fi
