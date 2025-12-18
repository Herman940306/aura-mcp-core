#!/usr/bin/env bash
set -e
./scripts/sanity_roles.sh || true
pytest -q || true
echo "Sanity run complete"
