#!/usr/bin/env bash
set -e
echo "OPA policy harness: linting policy"
docker run --rm -v $(pwd)/ops/opa/policies:/policies openpolicyagent/opa:0.51.2 test /policies
