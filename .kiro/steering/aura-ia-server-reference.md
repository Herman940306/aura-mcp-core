---
inclusion: always
---

# Aura IA MCP Server - Complete Reference Guide

**Project Creator:** Herman Swanepoel  
**Document Version:** 2.2.0  
**Last Updated:** December 14, 2025  
**Status:** Production-Ready / Server Deployed / GPU Verified / Chat + Home Assistant + Media Automation Operational

## Executive Summary

The Aura IA MCP Server is a **production-ready, enterprise-grade AI control plane** currently **100% operational** on Ubuntu NAS server at `{{NAS_IP}}`. The system has completed all 9 phases of development and is running Dashboard V3 "Grand Unification" with comprehensive monitoring, governance, and intelligence capabilities.

## Current Production Environment

### Server Details

- **Host**: Ubuntu NAS at `{{NAS_IP}}`
- **SSH User**: Wolf
- **Path**: `/volume2/docker/Herman/MCP_Server/`
- **Status**: All 11 containers running and healthy
- **Version**: V2.0.0 (Dashboard V3 "Grand Unification" Edition)

### Service Architecture (Canonical Ports)

| Service            | Port | Container Name        | Status      | Description                                            |
| ------------------ | ---- | --------------------- | ----------- | ------------------------------------------------------ |
| **Gateway**        | 9200 | aura-ia-mcp-server    | ✅ Live     | Primary MCP endpoint, SSE transport, tool dispatch     |
| **ML Backend**     | 9201 | aura-ia-ml-backend    | ✅ Live     | Inference, embeddings, semantic scoring, debate engine |
| **RAG/Qdrant**     | 9202 | aura-ia-rag           | ✅ Live     | Vector database, semantic search, hybrid retrieval     |
| **Embeddings**     | 9203 | aura-ia-embeddings    | 🔧 Reserved | Future embedding generation service                    |
| **LLM Service**    | 9204 | aura-ia-llm           | 🔧 Reserved | Future text generation endpoint                        |
| **Dashboard**      | 9205 | aura-ia-dashboard     | ✅ Live     | Monitoring UI, MCP Concierge chat, tabbed interface    |
| **Role Engine**    | 9206 | aura-ia-role-engine   | ✅ Live     | ARE+ role/policy engine, permissions, governance       |
| **Ollama Service** | 9207 | aura-ia-ollama        | ✅ Live     | External LLM agent container, model management         |
| **PostgreSQL**     | 9208 | aura-ia-postgres      | ✅ Live     | Persistent memory, conversation history, debates       |
| **Audio Service**  | 8001 | aura-ia-audio-service | ✅ Live     | STT/TTS microservice gateway                           |
| **Vosk STT**       | 2700 | aura-ia-vosk          | ✅ Live     | Speech-to-Text engine                                  |
| **Coqui TTS**      | 5002 | aura-ia-coqui         | ✅ Live     | Text-to-Speech engine                                  |

### HNSC Architecture (6-Layer Safety System)

The system implements **Hybrid Neuro-Symbolic Control** with strict safety guarantees:

| Layer | Component            | Trust Level   | Purpose                                            |
| ----- | -------------------- | ------------- | -------------------------------------------------- |
| 6     | Safety/Policy Engine | Fully Trusted | Final rule-check, forbidden pattern prevention     |
| 5     | Tool Intelligence    | Trusted       | Specialized handlers validate tool-ready input     |
| 4     | Static Reasoning     | Trusted       | Non-LLM logic for sequences, planning, corrections |
| 3     | Workflow Engine      | Trusted       | Runs multi-step MCP pipelines deterministically    |
| 2     | Symbolic Router      | Trusted       | Enforces routing, tool access, field-level schema  |
| 1     | LLM (Phi-3 Mini)     | **Untrusted** | Token generator for language formatting **only**   |

> **Critical**: The LLM is treated as an **untrusted component**. All tool invocations, workflow steps, and safety decisions are executed by deterministic MCP layers.

## Key Operational Endpoints

### Health & Status Endpoints

- `GET http://{{NAS_IP}}:9200/healthz` - Gateway health check
- `GET http://{{NAS_IP}}:9200/readyz` - System readiness check
- `GET http://{{NAS_IP}}:9201/health` - ML Backend health
- `GET http://{{NAS_IP}}:9206/health` - Role Engine health
- `GET http://{{NAS_IP}}:9208/health` - PostgreSQL health

### Model Gateway API (7 Verified Endpoints)

- `GET /v1/models/status` - Returns loaded models, RAM usage, mode mappings
- `GET /v1/models/health` - Ollama connectivity, available models list
- `POST /v1/models/{name}/load` - Loads model into Ollama memory
- `POST /v1/models/{name}/unload` - Offloads model from memory
- `POST /v1/router/detect-mode` - Intent detection with confidence scoring
- `GET /v1/router/stats` - Routing statistics and history
- `POST /v1/chat/smart` - Full routing with RoutingDecision response

### Debate Engine API

- `GET /v1/debate/topics` - Returns 60 debate topics across 6 categories
- `GET /v1/debate/leaderboard` - Model ELO rankings and win/loss records
- `GET /v1/debate/history` - Historical debate results from PostgreSQL
- `POST /v1/debate/start` - Initiate new debate between models
- `GET /v1/debate/{id}/status` - Check specific debate status

### RAG & Knowledge API

- `POST /rag/upsert_texts` - Ingest documents with server-side embeddings
- `POST /rag/query` - Semantic search with hybrid scoring
- `GET /rag/health` - RAG service health and collection info

### Dashboard & Monitoring

- `GET /v1/dashboard/summary` - Comprehensive system status aggregation
- `GET http://{{NAS_IP}}:9205` - Dashboard V3 with tabbed interface

## MCP Concierge Specification

| Attribute          | Value                                                  |
| ------------------ | ------------------------------------------------------ |
| **Name**           | MCP Concierge                                          |
| **Model**          | phi3.5:3.8b (via Ollama)                               |
| **Source**         | Ollama Service at port 9207                            |
| **RAM**            | 3.0 GB (managed by Model Lifecycle Manager)            |
| **Interface**      | Dashboard Chat (port 9205)                             |
| **Architecture**   | HNSC (Hybrid Neuro-Symbolic Control)                   |
| **Loading Policy** | Always loaded (TTL: infinite)                          |
| **Tools**          | 47 dashboard-accessible tools (includes 4 audio tools) |

### Available Models (Model Lifecycle Manager)

- **phi3.5:3.8b** - Always loaded (MCP Concierge)
- **llama3.1:8b** - 15min TTL (General chat)
- **qwen2.5-coder:7b** - 10min TTL (Debug/coding)
- **deepseek-r1:8b** - 5min TTL (Reasoning/analysis)

## Database Schema (PostgreSQL)

### Tables

- **conversations** - Chat session persistence
- **messages** - Individual message history
- **debates** - Debate metadata and outcomes
- **debate_rounds** - Individual debate round data
- **model_rankings** - ELO ratings and statistics

### Connection Details

- **Host**: aura-ia-postgres (internal), localhost:9208 (external)
- **Database**: aura_db
- **User**: Admin
- **Auth**: Trust (no password required)
- **Driver**: asyncpg with SQLAlchemy 2.0+

## Dashboard V3 Features

### Tabbed Interface

1. **Cockpit** - Main control center with system overview
2. **Omni-Monitor** - Real-time system metrics (CPU, RAM, GPU, temperature)
3. **Intelligence** - Model arena, debate visualization, performance stats
4. **Governance** - Role hierarchy, audit logs, security monitoring

### Real-Time Capabilities

- **WebSocket Connections** - Live data updates without refresh
- **System Monitoring** - Native CPU/RAM/GPU monitoring via psutil
- **Debate Visualization** - Live debate progress and results
- **Model Statistics** - Win rates, performance metrics, match history

## Known Issues & Solutions

### Current Dashboard Issues (Identified)

1. **Governance Tab** - ✅ FIXED - Role hierarchy via gateway proxy
2. **AI System Panel** - ✅ FIXED - Ollama sync on status check
3. **Chat Performance** - ✅ FIXED - 180s timeout, direct Ollama routing
4. **Intelligence Arena** - Not showing real model data, needs stats/history
5. **Database Widget** - Missing live database monitoring widget
6. **Omni Monitor** - Data appears mocked, need real-time server data + GPU/temp

### Recent Fixes Applied (December 14, 2025)

- **RAG Connectivity**: Fixed 500 errors by updating VECTOR_SIZE=768
- **Readyz Endpoint**: Fixed backend_ok=false by disabling proxy (trust_env=False)
- **Debate Scheduler**: Implemented 6-hour automated debates
- **Model Architecture**: Consolidated to single Ollama source
- **Home Assistant**: ML Backend on macvlan for direct HA access ({{HOME_ASSISTANT_IP}})
- **Media Automation Gateway Proxy**: ML Backend → Gateway → Radarr/Sonarr (port 8000 internal)
- **Media Tracking Mode**: 15-day learning period with PostgreSQL logging
- **asyncpg**: Added to requirements-backend.txt for permanent installation
- **get_tracking_stats()**: Fixed event loop issue with fresh connection

## Deployment & Operations

### File Sync Commands (Local to NAS)

```bash
scp -r F:\Kiro_Projects\LATEST_MCP\aura_ia_mcp {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
scp -r F:\Kiro_Projects\LATEST_MCP\src {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
scp -r F:\Kiro_Projects\LATEST_MCP\ops {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
```

### Container Management

```bash
# Full stack with observability (recommended)
sudo docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d

# Rebuild specific service
sudo docker compose build --no-cache aura-ia-gateway
sudo docker compose up -d aura-ia-gateway

# Full stack restart
sudo docker compose down
sudo docker compose up -d --build

# Health check all services
sudo docker compose ps
```

### Running Containers (11 total)
- **Core:** aura_ia_gateway, aura_ia_ml, aura_ia_dashboard, aura_ia_postgres, aura_ia_ollama, aura_ia_rag, aura_ia_role_engine
- **Observability:** aura_ia_jaeger (16686), aura_ia_grafana (3000), aura_ia_prometheus (9090), aura_ia_blackbox (9115)

### Critical Paths

- **Local Workspace**: `F:\Kiro_Projects\LATEST_MCP`
- **NAS Path**: `/volume2/docker/Herman/MCP_Server/`
- **Container Logs**: `sudo docker compose logs [service-name]`
- **Database Access**: `sudo docker exec -it aura_ia_postgres psql -U Admin -d aura_db`

## Testing Status

| Test Suite        | Tests | Status            |
| ----------------- | ----- | ----------------- |
| Unit Tests        | 151+  | ✅ 82.4% coverage |
| Integration Tests | 77+   | ✅ 100% passing   |
| HNSC Tests        | 26/26 | ✅ 100% passing   |
| Sanity Checks     | 10/10 | ✅ 100% passing   |
| E2E Playwright    | 20/20 | ✅ 100% passing   |
| Governance Tests  | 90+   | ✅ 100% passing   |

## Security & Compliance

### Enterprise Governance (PRD Section 9)

- **Zero Trust Agent Layer** - All agent-to-agent interactions validated
- **PII Detection/Redaction** - 15+ patterns (email, phone, SSN, etc.)
- **Supply Chain Security** - SBOM generation, Cosign image signing
- **Policy as Code** - OPA Gatekeeper with 8 constraint templates
- **Human Override Protocol** - Safe emergency bypass mechanism

### Observability Stack

- **Prometheus** - Metrics collection and alerting
- **Grafana** - Visualization dashboards
- **OpenTelemetry** - Distributed tracing
- **Loki** - Log aggregation and correlation

## Development Phases Completed

### ✅ All Phases Complete (1-9)

- **Phase 1**: Standardization & Migration (V.1.1)
- **Phase 2**: Reliability & Scaling (V.1.2)
- **Phase 3**: Security Hardening (V.1.3)
- **Phase 4**: Advanced Intelligence (V.1.4)
- **Phase 5**: Observability Platform (V.1.5)
- **Phase 6**: Strategic & Futuristic (V.1.6)
- **Phase 7**: Frontend Evolution & HNSC Architecture (V.1.7)
- **Phase 8**: Enterprise Governance (V.1.8)
- **Phase 9**: Repository Cleanup & Production Deployment (V.1.9)

### Recent Milestones

- **V.1.9.10**: Server deployment with 7 verified API endpoints
- **V.1.9.11**: PostgreSQL integration, Model Lifecycle Manager, Chat Router
- **V.1.9.12**: Chat reliability fixes (180s timeout, GPU optimization)
- **V.1.9.13**: Dashboard enhancements with dynamic model display
- **V2.0.0**: Dashboard V3 "Grand Unification" with tabbed interface

## Quick Reference Commands

### Health Checks

```bash
curl -s http://{{NAS_IP}}:9200/healthz
curl -s http://{{NAS_IP}}:9200/readyz
curl -s http://{{NAS_IP}}:9201/health
```

### Model Management

```bash
curl -s http://{{NAS_IP}}:9200/v1/models/status
curl -X POST http://{{NAS_IP}}:9200/v1/models/llama3.1:8b/load
```

### Debate System

```bash
curl -s http://{{NAS_IP}}:9200/v1/debate/topics
curl -s http://{{NAS_IP}}:9200/v1/debate/leaderboard
```

### Dashboard Access

- **URL**: <http://{{NAS_IP}}:9205>
- **Features**: Cockpit, Monitor, Intelligence, Governance tabs
- **Chat**: MCP Concierge with 47 tools available

### Home Assistant

- **URL**: `http://{{HOME_ASSISTANT_IP}}:8123` (macvlan IP)
- **Access**: ML Backend has direct access via macvlan network
- **Commands**: "turn on bathroom light", "home status", "what lights are on"

### Media Automation (Tracking Mode Active)

**Architecture:** ML Backend → Gateway (port 8000) → Radarr/Sonarr ({{NAS_IP}})

| Command | Action |
|---------|--------|
| "download Dune movie" | Logs to PostgreSQL, shows tracking message |
| "confirm download Dune" | Actually adds to Radarr/Sonarr |
| "tracking stats" | Shows logged requests and statistics |
| "what's downloading" | Shows SABnzbd/Radarr/Sonarr queues |

**Tracking Mode Settings:**
- `MEDIA_TRACKING_ONLY=true` (15-day learning period)
- All searches logged to `media_downloads` table
- Downloads require explicit "confirm download" command

**Gateway Proxy Routes:**
- `GET/POST /api/media/radarr/{path}` → Radarr API
- `GET/POST /api/media/sonarr/{path}` → Sonarr API
- `GET /api/media/sabnzbd` → SABnzbd API

## Next Steps & Maintenance

1. **Monitor** periodic debates (6-hour automated cycles)
2. **Ingest** documents via RAG endpoint for knowledge base
3. **Utilize** Dashboard for comprehensive system observability
4. **Address** identified dashboard issues for optimal UX
5. **Scale** system as needed using Kubernetes manifests
6. **Review** media tracking data after 15 days for recommendation patterns
7. **Disable** tracking mode when ready: set `MEDIA_TRACKING_ONLY=false`

---

This document serves as the canonical reference for all Aura IA MCP Server operations, deployment, and maintenance activities.
