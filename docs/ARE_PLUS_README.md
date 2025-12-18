# ARE+ (Autonomous Role Engine - OVERDRIVE)
Quick start:
1) Review ops/role_engine/INSTALL_OPTIONS.env and tune AUTO_APPROVE, secrets.
2) Run role service:
   python3 ops/role_engine/are_service.py
   or: uvicorn ops.role_engine.are_service:app --host 0.0.0.0 --port 9700
3) Start approval and role services for HITL:
   python3 ops/approvals/approval_service.py
4) Run OPA (optional):
   ./scripts/run_opa.sh
5) Use selector:
   python3 mcp/roles/selector_advanced.py "run tests and propose patch"
Security notes: change JWT_SECRET, set AUTO_APPROVE=false until you trust automation.
