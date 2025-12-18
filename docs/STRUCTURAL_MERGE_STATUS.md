# Structural Merge Status (Phase 2)

Date: 2025-11-24

## Overview

Tracking completion of Phase 2 items from `INTEGRATION_CHECKLIST.md`.

## Targets & Current State

| Item | Present | Notes |
|------|---------|-------|
| `aura_ia_mcp/` package | Yes | Contains `core/`, `main.py`, nested `ops/`, `services/` (inside package), `training/` |
| Top-level `services/` dir | Yes | Added with re-export gateway; implementation remains in-package. |
| Top-level `ops/` dir | Yes | Contains approvals, git, opa, role_engine, tests |
| Top-level `training/` dir | Yes | ML + roles subdirs |
| `scripts/` | Yes | Extensive governance & utility scripts present |
| `logs/` | Yes | `security_audit.jsonl`, spans file present |
| Obsolete top-level files | Legacy installers still whitelisted | Scheduled for removal in cleanup branch |
| `pyproject.toml` | Yes | Present; verify tool config completeness next |
| Tool registry under `mcp/tools/` | No | To be implemented (baseline loader + schemas) |

## Gaps

1. (Resolved) Top-level `services/` directory added as visibility layer.
2. Missing tool registry structure (`mcp/tools/<tool_name>/`).
3. Legacy installer scripts still in whitelist (pending removal).
4. Checklist items for capability flags, docker-compose override, SAFE MODE off transition not yet addressed.

## Decisions Needed

- Confirm whether PRD requires both a top-level `services/` and in-package `aura_ia_mcp/services/` or just one canonical location.
- Define initial tool list to scaffold (e.g., `role_policy`, `rag_query`, `embedding_generate`).

## Proposed Next Actions

1. Clarify canonical service layout; if top-level required, extract or symlink from package.
2. Create `mcp/tools/` with initial tool folders and minimal `schema.json` + `tool.py` stubs.
3. Prepare `docker-compose.override.yml` with port map (9200–9206) and capability env flags placeholders.
4. Remove legacy installer root files and adjust structural whitelist.
5. Add capability flags to `.env.example` and document in README.
6. Implement SAFE MODE off transition test + audit event.

## Audit Verification

- Structural audit currently returns no unexpected entries after whitelist expansion.
- PRD alignment script reports no missing dirs/files/ports.

## Checklist Mapping

- Copy `aura_ia_mcp/` package directory: EFFECTIVELY PRESENT (mark complete once service layout confirmed).
- Copy/merge `services/`, `ops/`, `training/`, `scripts/`, `logs/`: PARTIAL (services top-level missing).
- Add / merge `docker-compose.override.yml`: PENDING.
- Ensure `pyproject.toml` present: DONE.
- Place tools under `mcp/tools/<tool_name>`: PENDING.
- Remove obsolete top-level files not whitelisted: PENDING (legacy installers).

## Status Summary

Phase 2 is partially complete; main blockers are service directory decision, tool registry creation, docker override, and cleanup of legacy installers.
