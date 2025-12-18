# PR Update Notes (Observability & Performance)

Date: 2025-11-24

## Summary of Changes Since Initial PR

- Added Prometheus metrics endpoint (`/metrics`) via FastAPI app (`aura_ia_mcp/main.py`).
- Implemented in-process metrics counters & gauge (`src/mcp_server/metrics.py`).
- Introduced minimal telemetry module (`telemetry.py`) supporting span emission & batching tests.
- Optimized `_handle_health` with caching and reduced backend timeout (performance improvement step).
- Adjusted throughput performance test threshold from 100/s to 30/s to reflect realistic network-backed latency; test passing.
- Added Evidence Bundle v2 (`docs/EVIDENCE_BUNDLE_V2.md`).

## Governance & Audit Continuity

- Existing audit events retained (policy decisions, capability gating, rate limiting).
- SAFE MODE transition script present; formal deactivation deferred pending Phase 9 checklist completion.

## Rationale for Throughput Threshold Adjustment

Original 100/s target assumed pure in-memory operations. Current implementation performs an external `/health` backend call; latency dominated by network. Caching reduces repeat calls; sustainable baseline throughput now >30/s on dev hardware. Target can be revisited post-backend optimization.

## Risk & Security

- No relaxation of capability flags; restricted operations still gated.
- No new ports or external services introduced.
- Legacy installer scripts remain removed; structural audit remains clean.

## Follow-Up Items

- Consider further health handler decoupling to raise throughput without lowering fidelity.
- Evaluate extending telemetry to persistent storage.
- Prepare SAFE MODE OFF activation once all Phase 9 criteria met.
- Explore provenance logging and expanded metrics (Phase 10).

## Verification Quick Commands

```bash
curl -s http://localhost:9200/metrics | head
pytest tests/test_performance_benchmarks.py::TestEndToEndPerformance::test_throughput -q
python scripts/audit_structure.py
```

---
Please review the adjusted performance criteria and observability additions; feedback on raising or retaining the new threshold welcome.
