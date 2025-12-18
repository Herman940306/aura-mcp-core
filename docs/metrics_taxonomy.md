# Metrics Taxonomy

Purpose: Provide a stable naming / classification framework for all observability metrics (Prometheus/OpenTelemetry) across the MCP stack: core services, model inference, tooling, governance, scaling, and provenance.

## Naming Conventions

- Format: `snake_case`.
- Suffix guidance:
  - `_total` for monotonically increasing counters.
  - `_seconds` / `_seconds_total` for durations.
  - `_bytes` for memory / payload sizes.
  - `_ratio` or `_percent` for normalized gauges (0–1 / 0–100).
  - Histograms: base name + `_seconds` (e.g., `request_latency_seconds`).
- Labels should remain low-cardinality: `endpoint`, `status`, `model`, `tool`, `version`, `mode`, `key_version`, `decision`, `region`.
- Avoid dynamic user identifiers in labels (use aggregation streams if needed).

## 1. Core Service Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | counter | `endpoint`, `status` | Count of HTTP requests by endpoint & status code class |
| `request_latency_seconds` | histogram | `endpoint` | Latency distribution per endpoint |
| `uptime_seconds_total` | counter | `service` | Monotonic seconds since service start |
| `active_connections` | gauge | `service` | Current open HTTP/SSE/WebSocket connections |
| `latency_spread_ms` | gauge | `endpoint` | Difference between max/min latency over sample window |

## 2. Model Inference Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `model_inference_requests_total` | counter | `model`, `status` | Inference request count |
| `model_inference_latency_seconds` | histogram | `model` | Distribution of model inference times |
| `tokens_in_total` | counter | `model` | Total input tokens processed |
| `tokens_out_total` | counter | `model` | Total output tokens generated |
| `token_throughput_tokens_per_second` | gauge | `model` | Moving window throughput |
| `inference_cost_usd_total` | counter | `model` | Accumulated cost approximation |
| `model_cache_hit_ratio` | gauge | `model` | Short-term ratio of cache hits |

## 3. Tool Invocation Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `tool_invocations_total` | counter | `tool`, `outcome` | Count of tool calls (success/failure) |
| `tool_latency_seconds` | histogram | `tool` | Tool execution latency distribution |
| `tool_failure_rate_percent` | gauge | `tool` | Rolling failure percentage |
| `tool_queue_depth` | gauge | `tool` | Pending queued tool executions |

## 4. Governance & Risk Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `approval_requests_total` | counter | `decision`, `source` | Count of approval events (granted/denied) |
| `approvals_pending` | gauge |  | Current queued approvals |
| `safe_mode_enabled` | gauge |  | 1 if SAFE MODE active else 0 |
| `risk_score_distribution` | histogram | `model` | Distribution of computed risk scores |
| `provenance_validation_failures_total` | counter | `reason` | Chain integrity failure count |
| `provenance_rotation_events_total` | counter | `mode` | Secret rotation events |
| `provenance_active_key_version` | gauge |  | Current active provenance key version |

## 5. Performance & Quality Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `anomaly_events_total` | counter | `type` | Detected anomalies (latency, error spike, drift) |
| `readiness_cache_staleness_seconds` | gauge |  | Age of readiness cache snapshot |
| `backend_health_failures_total` | counter | `component` | Health probe failures |
| `backend_health_latency_seconds` | histogram | `component` | Health probe round-trip times |

## 6. Scaling & Predictive Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `autoscale_predictions_total` | counter | `strategy` | Count of predictive autoscale evaluations |
| `autoscale_prediction_cpu_percent` | gauge | `strategy` | Predicted CPU load percent |
| `autoscale_decisions_total` | counter | `action` | Scale in/out decisions |
| `queue_backlog_depth` | gauge | `queue` | Items waiting across core processing queues |

## 7. Resource & Runtime Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `process_cpu_percent` | gauge | `service` | CPU usage percent |
| `process_memory_bytes` | gauge | `service`, `segment` | Memory consumption split (rss, heap, cache) |
| `cache_hit_ratio` | gauge | `cache` | Generic cache hit ratio (0–1) |
| `disk_usage_bytes` | gauge | `mount` | Disk usage by mount path |
| `open_file_descriptors` | gauge | `service` | FD count |

## 8. Security & Compliance Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `security_audit_events_total` | counter | `category` | Audit events logged |
| `policy_violations_total` | counter | `policy` | Policy violation occurrences |
| `sbom_components_total` | counter | `status` | SBOM components counted (verified/unverified) |
| `image_signature_verifications_total` | counter | `result` | Image signature check outcomes |

## 9. Data & Drift Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `model_drift_score` | gauge | `model` | Continuous drift score (0–1 normalized) |
| `regression_failures_total` | counter | `suite` | Regression test failures |
| `data_lineage_gaps_total` | counter | `stage` | Missing lineage link count |

## 10. RAG & Retrieval Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `rag_queries_total` | counter | `source` | Retrieval augmented queries |
| `rag_latency_seconds` | histogram | `source` | RAG retrieval latency |
| `rag_topk_mean` | gauge | `source` | Mean top-K relevance score |
| `rag_cache_hit_ratio` | gauge | `source` | RAG layer cache hit ratio |

## 11. Cost & Sustainability Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `inference_energy_joules_total` | counter | `model` | Estimated energy usage |
| `carbon_intensity_grams_total` | counter | `region` | CO2 grams estimate |
| `cost_usd_total` | counter | `category` | Aggregated operational cost segments |

## 12. Streaming & Real-Time Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `stream_tokens_emitted_total` | counter | `model` | Streaming output tokens |
| `stream_latency_first_token_seconds` | histogram | `model` | Time to first streamed token |
| `partial_frame_drops_total` | counter | `reason` | Dropped streaming frames |

## 13. Multi-Region & Failover Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `failover_events_total` | counter | `from_region`, `to_region` | Failover occurrences |
| `replication_lag_seconds` | gauge | `region` | Inter-region state sync lag |
| `federated_query_latency_seconds` | histogram | `region` | Latency for federated requests |

## 14. Tenant & Quota Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `tenant_requests_total` | counter | `tenant`, `status` | Per-tenant request count (sampled / aggregated) |
| `tenant_quota_utilization_percent` | gauge | `tenant` | Quota consumption percent |
| `tenant_throttle_events_total` | counter | `tenant` | Throttle occurrences (may use hashed tenant ids) |

## 15. Advanced Governance / Semantic Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `semantic_diff_risk_total` | counter | `risk_level` | Risk scoring events from semantic diff analysis |
| `generated_tests_total` | counter | `suite` | AI-generated test cases created |
| `incident_reconstructions_total` | counter | `severity` | Incident timeline auto-reconstruction runs |

## Aggregation & Cardinality Control

- High-cardinality risks: `tenant`, `tool`, `model`. Apply hashing or sampling where needed.
- Roll-up strategy: periodic aggregation jobs produce summary metrics (e.g., hourly cost buckets).
- Deletion / expiry: ephemeral histogram series pruned automatically using retention policies.

## Metric Lifecycle

1. Draft (defined here) → 2. Implemented (instrumented in code) → 3. Validated (dashboards & alerts) → 4. Maintained (review quarterly) → 5. Deprecated (marked, retained for N release cycles) → 6. Removed.

## Alerting Examples

| Metric | Condition | Severity |
|--------|-----------|----------|
| `tool_failure_rate_percent` | > 5% for 5m | High |
| `latency_spread_ms` | > 300ms sustained | Medium |
| `provenance_validation_failures_total` | any increase | Critical |
| `autoscale_prediction_cpu_percent` | > 85% predicted for next interval | Medium |
| `risk_score_distribution` | P95 > threshold | High |

## OpenTelemetry Mapping

Prometheus metrics map to OTEL instruments:

- Counter → `Counter`
- Gauge → `ObservableGauge`
- Histogram → `Histogram`

Resource attributes to include:

- `service.name`, `service.version`, `deployment.environment`, `region`, `git.commit`, `runtime.language`.

## Future Extensions

- Exemplar linking (trace IDs attached to histogram exemplars).
- RED / USE methodology overlays (Rate, Errors, Duration / Utilization, Saturation, Errors).
- SLO annotations (e.g., `request_latency_seconds` target 95% < 750ms).
- Adaptive metrics: dynamic label suppression under cardinality pressure.

## Implementation Checklist

- [ ] Create base instrumentation module exporting metric objects.
- [ ] Register counters & histograms at import time (lazy no-op until registry init).
- [ ] Add unit tests validating label sets & units.
- [ ] Wire into dashboards (Grafana panels) grouped by taxonomy sections.
- [ ] Configure alert rules referencing canonical metric names.

---
Document owner: Observability / Platform Team
Revision: 2025-11-24 (initial)
