# Aura IA MCP — Merge & Implementation Guide

This document defines the authoritative procedure for merging any existing MCP implementation with the unified Aura IA MCP (SUPER‑MCP) stack while maintaining governance, port compliance, and Section 8 behavioral constraints from `AURA_IA_MCP_PRD.md`.

## 1. Scope & Objectives

Provide a deterministic, auditable sequence that:

- Preserves a restorable backup.
- Introduces the SUPER‑MCP services and tooling without drift.
- Enforces canonical port map (9200–9206).
- Aligns directory layout with enterprise structure.
- Verifies operational readiness and governance alignment.

## 2. Prerequisites

1. Read and understand `AURA_IA_MCP_PRD.md` (especially ports, structural rules, Section 8).
2. Ensure local Python 3.11+ environment and Docker engine available.
3. Confirm no conflicting processes bound to ports 9200–9206.
4. Export any sensitive secrets before proceeding.

## 3. Backup (Mandatory)

Create a timestamped backup:

```bash
cp -r <your_mcp_dir> "${your_mcp_dir}_BACKUP_$(date +%Y%m%d)"
```

Store it outside the working tree. Do not proceed without backup confirmation.

## 4. Source (Staging) Artifact Verification

You should possess a generation output folder (e.g. `upgraded_mcp_universal/`) containing at minimum:

```text
upgraded_mcp_universal/
  services/
  mcp/
  ops/
  training/
  logs/
  docker-compose.override.yml
```

If missing any critical subtree, re‑generate before merging.

## 5. Canonical Port Compliance

Aura IA MCP fixed host ports (must match PRD):

| Component | Port |
|-----------|------|
| Root MCP Server | 9200 |
| ML Backend / LLM Proxy | 9201 |
| RAG / Vector DB | 9202 |
| Embeddings Service | 9203 |
| LLM / vLLM Stub (if separate) | 9204 |
| Dashboard / Monitor | 9205 |
| Role Engine / Policy Service | 9206 |

Any deviation requires an approved PRD update and reviewer sign‑off.

## 6. Merge Procedure

From your primary MCP root:

```bash
cd <your_current_mcp>
```

Copy necessary subtrees (exclude generation scripts / ephemeral build helpers):

```bash
cp -r /path/to/upgraded_mcp_universal/services .
cp -r /path/to/upgraded_mcp_universal/mcp .
cp -r /path/to/upgraded_mcp_universal/ops .
cp -r /path/to/upgraded_mcp_universal/training .
cp -r /path/to/upgraded_mcp_universal/logs .
cp /path/to/upgraded_mcp_universal/docker-compose.override.yml .
cp /path/to/upgraded_mcp_universal/agent_pipeline.py .
cp /path/to/upgraded_mcp_universal/main.py .
cp /path/to/upgraded_mcp_universal/requirements.txt .
```

## 7. Conflict Resolution

If an existing `mcp/server` directory already exists:
Retain the SUPER‑MCP versions of:

- `main.py`
- `registry.py`
- `discovery.py`
- `ui.py`

Preserve customized logic only if audited for compatibility (log differences in PR).

### 7.1 Tool Consolidation

Place all tools under `mcp/tools/<tool_name>` ensuring each contains:

- `schema.json` (formal interface contract)
- `tool.py` (implementation)

Convert legacy tools lacking schema. Reject merge if schema absent.

## 8. Component Adoption

New capabilities introduced:

| Capability | Location |
|------------|----------|
| RAG Tool | `mcp/tools/rag_tool` |
| LLM Tool | `mcp/tools/llm_tool` |
| Embeddings Service | `services/embeddings` |
| vLLM Stub | `services/vllm_stub` |
| Tool Updater | `ops/tool_updater/watcher.py` |
| SICD Training Engine | `training/sicd/` |

SICD Engine must include: `orchestrator.py`, `sandbox_executor.py`, `episode_logger.py`, `pr_generator.py`.

## 9. Docker Integration

Preferred (compose include directive):

```yaml
include:
  - docker-compose.override.yml
```

If unsupported, manually merge override service definitions into `docker-compose.yml` preserving port bindings (9200–9206) and service names defined in PRD.

## 10. Dependency Alignment

Replace or merge requirements:

```bash
pip install -r requirements.txt
```

If consolidating, ensure no pinned version regressions and run a dry test.

## 11. Governance & Kill Switch

Set `AURA_SAFE_MODE=true` in your environment or `.env` until full validation completes. This activates conservative execution pathways. Rotate `PROV_SECRET` if provenance auditing is adopted.

## 12. Initial Bring‑Up

Local:

```bash
python main.py
```

Docker:

```bash
docker compose up --build
```

Sandbox (single service):

```bash
./sandbox_dev_run.sh 9200
```

## 13. Verification Matrix

Run alignment and structure audits:

```bash
python scripts/verify_prd_alignment.py --ci || true
python scripts/audit_structure.py
```

| Component | Path | Required Status |
|-----------|------|-----------------|
| MCP Server | mcp/server/main.py | Running |
| Tool Registry | mcp/tools | Populated |
| Embeddings Service | services/embeddings | Healthy |
| vLLM Stub | services/vllm_stub | Responds 200 |
| RAG Tool | mcp/tools/rag_tool | Registers |
| LLM Tool | mcp/tools/llm_tool | Generates/Echoes |
| Tool Updater | ops/tool_updater | Auto‑reload active |
| SICD Trainer | training/sicd | Episodes log |

Optional script (future): `verify_super_mcp.sh` bundling checks.

## 14. Post‑Merge Cleanup

Remove staging generation folder to avoid drift:

```bash
rm -rf upgraded_mcp_universal/
```

Do not retain obsolete generation scripts in production root.

## 15. Success Criteria

All components pass health, readiness, and alignment scripts. Port map stable. No unauthorized top‑level files. SAFE_MODE may be disabled after signed verification PR.

## 16. Escalation & Rollback

If a critical service fails:

1. Re‑enable `AURA_SAFE_MODE=true`.
2. Compare diff against backup.
3. Restore backup selectively (tooling first, core server last).
4. Document incident in a PR template “Risk / Rollback” section.

## 17. Audit Trail

Record merge actions (commands executed) in the merge PR description. Attach outputs of alignment scripts. Include justification for any deviations from PRD.

---

All changes must remain traceable, reversible, and PRD‑aligned. Unapproved divergence is a policy violation.
