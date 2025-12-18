# Aura IA MCP Integration Checklist

This checklist provides a governed, auditable sequence for integrating (or validating) the unified Aura IA MCP stack inside an existing repository. All steps must conform to `AURA_IA_MCP_PRD.md` and Section 8.

## Phase 0: Preparation

- [x] Read `AURA_IA_MCP_PRD.md` (ports, structure, SAFE MODE, Section 8)
- [x] Confirm Python >= 3.11 and Docker available
- [x] Verify ports 9200–9206 are free
- [x] Export secrets needed (PROV_SECRET, API_KEY) separately (rotation procedure documented)
- [x] Set `AURA_SAFE_MODE=true` for initial activation

## Phase 1: Backup & Staging

 [x] Launch core: `python aura_ia_mcp/main.py` or `./sandbox_dev_run.sh`
 [x] Start full stack: `docker compose up --build` (use task "Docker: compose up (build)")
 [x] Verify stack health: `python scripts/verify_compose_stack.py` or task "Verify: MCP stack health"

- [x] Confirm presence of staging artifact (if using generator) or new package skeleton
 [x] SBOM + signing workflow present (`.github/workflows/sbom-signing.yml`)

 [x] Confirm `PROV_SECRET` rotation procedure documented (`docs/PROV_SECRET_ROTATION.md`)
 [x] Confirm `PROV_SECRET` rotated before production per doc

 [x] Prometheus metrics exposed (`/metrics`) where enabled; add scrape jobs accordingly
 [x] OpenTelemetry tracing optional via env (`OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`)

- [x] Copy/merge `services/`, `ops/`, `training/`, `scripts/`, `logs/`
 [x] Metrics taxonomy document (`docs/metrics_taxonomy.md`)
 [x] Model adapter interface (Ollama / OpenAI)
 [x] OpenTelemetry tracing (service spans, model inference attributes)
 [x] Token budgeting algorithm (rolling forecast + summarization)
 [x] Dual-model arbitration logic (divergence + safety composite)
 [x] Conversation log governance (hash chain + PII tags + retention)
 [x] Canary deploy workflow (gradual traffic shift; `.github/workflows/canary-deploy.yml`)
 [x] Model safety filter tiers (moderation / escalation)
 [ ] Predictive autoscaling (forecast-based scale decisions) – PLANNED
 [x] RAG retrieval integration (semantic compression)
 [x] Wave 5: Retrieval + Intelligence complete (30/30 tests passing)
  - Hybrid scoring (cosine + BM25)
  - Token budget enforcement
  - Graceful fallback on Qdrant unavailability
  - Prometheus metrics (latency, hits)
  - Optional audit logging for failures
  - Wired into DualModelEngine with feature flags
 [x] Cost & usage metrics (tokens, USD, duration)
 [x] Chaos & resilience test suite (fault injection invariants)
- [x] Confirm audit log path (default): `AUDIT_LOG_PATH=logs/security_audit.jsonl`

## Phase 4: Bootstrap & Bring-Up

- [x] Launch core: `python aura_ia_mcp/main.py` or `./sandbox_dev_run.sh`
- [x] Start full stack: `docker compose up --build` (health verification integrated)
- [x] Confirm health endpoints: `/healthz`, `/readyz`, `/livez`
- [x] Validate each service binding matches port map
- [x] Observe SAFE MODE: restricted operations must return 423 Locked or 403 Forbidden

## Phase 5: Alignment & Governance

- [x] Run structural audit: `python scripts/audit_structure.py` (no unexpected entries)
- [x] Run PRD alignment: `python scripts/verify_prd_alignment.py --ci`
- [x] Confirm SAFE MODE logging message appears
- [x] Check logs structure under `./logs/`
- [x] Ensure staging folders (e.g. `upgraded_mcp_universal/`) removed post-merge
  - Transient dirs to remove: `temp_migration_matrix`,
    `temp_migration_matrix_perm`, `temp_migration_test`,
    `upgraded_mcp_universal`.
  - Helper commands:
    - List targets: `python scripts/cleanup_transient_artifacts.py --list`
    - Delete targets: `python scripts/cleanup_transient_artifacts.py --yes`
  - CI enforces this hygiene on push to main; PRs are not blocked.
- [x] Verify policy audit logging: decisions persisted to `logs/security_audit.jsonl`
- [x] Verify capability gating: restricted routes require both SAFE MODE off and flag enabled

## Phase 6: Tool & Service Validation

- [x] Tool registry loads baseline tools
- [x] RAG stub or real implementation responds (query returns stub payload or results)
- [x] LLM echo/generate endpoints respond (stub mode)
- [x] Embedding endpoint returns vector placeholder
- [x] Role engine gateway returns allow decision
- [x] Role mutation requires approval payload and capability:
  - `POST /roles/mutate` with body `{ "approved": true }`
  - Expect 403 when not approved, or 423 if SAFE MODE active
  - Response includes `risk_score`
- [x] Role load endpoint:
  - `GET /roles/load` responds with allowed decision and `risk_score`
- [x] Training start requires policy and capability compliance:
  - `POST /training/start` with optional body `{ run_id?, episodes>=1, dry_run? }`
  - Requires `ENABLE_TRAINING=true` and `ENABLE_AUTONOMY=true` and SAFE MODE off
  - Response includes `risk_score` and echoes run params
- [x] SICD training components present (stub module integrated)

## Phase 7: Testing & CI

- [x] Execute `pytest` (health + port + gateway tests pass)
- [x] Lint: `ruff check .` passes or yields only purposeful TODOs
- [x] Type check: `mypy aura_ia_mcp` passes (allowing configured ignores)
- [x] Verify GitHub workflows present (`lint.yml`, `type-check.yml`, `tests.yml`, `security.yml`)
- [x] Dependabot workflow present (actions + pip)
- [x] SBOM workflow present (Syft/CycloneDX via `.github/workflows/sbom-signing.yml`)
- [ ] HTTP tests use explicit ASGI transport (no deprecated `TestClient(app=...)` shortcut)
  - Use `httpx.ASGITransport` or a sync wrapper helper

## Phase 8: Security & Policy (Initial)

- [x] Confirm `PROV_SECRET` placeholder rotated before production (per rotation doc)
- [x] Verify kill switch (`AURA_SAFE_MODE`) can be toggled
- [ ] (Future) Add OPA/Rego evaluation integration script
- [x] Validate that policy decisions (allow/deny/reasons/risk_score) are audited

## Phase 9: Transition Out of SAFE MODE

- [ ] All audits clean (structure + alignment)
- [ ] All tests pass consistently
- [ ] No unapproved port changes
- [ ] Formal PR reviewed and approved
- [ ] Set `AURA_SAFE_MODE=false` (commit change via approved PR)
- [ ] If enabling restricted capabilities, set flags deliberately via PR:
  - `ENABLE_TRAINING=true`, `ENABLE_AUTONOMY=true`, `ENABLE_ROLE_MUTATION=true` (as applicable)

## Phase 10: Post-Integration Hardening

- [x] Add performance metrics export (/performance endpoint + uptime, backend health gauges)
- [ ] Expand policy checks (hallucination, honesty enforcement) – NOT STARTED
- [x] Implement provenance logging (tool invocation + SICD episodes)
- [x] Add extended service readiness tests (concurrency + latency stability)

## Phase 11: Advanced Hardening & Roadmap (Planning)

- [ ] Predictive autoscaling (forecast-based scale decisions)
- [ ] Policy-as-code rollout (OPA/Gatekeeper baseline policies)
- [ ] WASM sandbox for untrusted tool plugins
- [ ] Semantic diff risk scoring pipeline
- [ ] Data lineage & provenance chain v2 (Merkle root per session)
- [ ] Self-healing anomaly remediation agent
- [ ] GPU & heterogeneous scheduling layer
- [ ] Federated multi-region failover strategy
- [ ] Real-time streaming incremental token output
- [ ] Green compute optimization module
- [ ] Generative test case synthesizer
- [ ] Incident timeline auto-reconstruction
- [ ] Energy usage metrics (kWh/CO₂ estimations)

## Phase 12: Wave 6 Candidates (Post Wave 5)

- [ ] Real embeddings integration (sentence-transformers)
- [ ] Re-ranking with cross-encoder
- [ ] Query expansion and rewriting
- [ ] Multi-vector search strategies
- [ ] Connection pooling for Qdrant
- [ ] Retry logic with exponential backoff
- [ ] Rate limiting per collection
- [ ] Context compression algorithms
- [ ] Relevance feedback loop
- [ ] A/B testing framework for retrieval strategies

## Quick Command Summary

```bash
# Install & initialize
pip install -e .
pre-commit install

# Run alignment & structural checks
python scripts/verify_prd_alignment.py --ci || true
python scripts/audit_structure.py

# Run tests
pytest -q

# Launch sandbox (SAFE MODE)
./sandbox_dev_run.sh 9200
```

## Exit Criteria

All phases completed with documented evidence in an integration PR. Any deviation requires explicit PRD amendment and reviewer approval.

---
Maintain traceability: log each step completion in the integration PR description.
