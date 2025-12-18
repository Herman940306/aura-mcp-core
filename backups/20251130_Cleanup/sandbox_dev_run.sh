#!/usr/bin/env bash
PORT=${1:-9200}
export AURA_SAFE_MODE=true
python -m uvicorn aura_ia_mcp.main:app --host 0.0.0.0 --port "$PORT" --reload
