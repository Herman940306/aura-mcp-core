#!/usr/bin/env bash
# start role manager and approval queue (dev)
echo "Start role manager (uvicorn recommended) and approval queue (uvicorn recommended)"
python3 ops/role_engine/are_service.py &
python3 ops/approvals/approval_service.py &
echo "Started (background). Check logs or run uvicorn for production."
