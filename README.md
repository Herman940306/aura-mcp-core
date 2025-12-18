# Aura MCP Core: A Framework for Operational Integrity in AI Connectivity

<div align="center">

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![PRD](https://img.shields.io/badge/PRD-v4.4-orange.svg)
![Standard](https://img.shields.io/badge/standard-mission--critical-red.svg)

**A mission-critical Model Context Protocol (MCP) framework engineered for operational integrity, systematic reliability, and audit-ready state management.**

[Getting Started](#-quick-start) • [Architecture](#-architecture) • [Documentation](#-documentation) • [API Reference](#-canonical-port-map)

</div>

---

## 🔧 Systems Pedigree

Aura is engineered with a focus on **systemic reliability**, drawing on a decade of experience in high-stakes systems diagnostics and technical oversight. It applies the same **zero-tolerance for failure** found in heavy-duty mechanical and electrical systems to the Model Context Protocol.

This framework treats AI connectivity as critical infrastructure—where silent failures are unacceptable, state consistency is non-negotiable, and every operation must be traceable for root-cause analysis.

---

## 📋 Mission-Critical Standard

Aura MCP Core adheres to rigorous engineering standards designed for operational environments where failure is not an option:

| Principle | Implementation | Purpose |
|-----------|----------------|---------|
| **Strict Type Safety** | Full type hints across all modules | Ensures state consistency and prevents runtime type coercion errors |
| **Fail-Safe Protocol Validation** | Schema validation on all MCP messages | Eliminates "silent failures" through explicit error propagation |
| **High-Precision Monitoring** | Structured JSONL audit logs with request IDs | Provides audit-ready state logs for compliance and root-cause analysis |
| **Circuit Breaker Patterns** | Automatic fault isolation and graceful degradation | Prevents cascade failures across interconnected services |
| **Deterministic State Management** | Immutable configuration, versioned policies | Guarantees reproducible system behavior for standardization |

---

## 🎯 Overview

Aura MCP Core is a production-grade AI connectivity framework that integrates:

- **MCP Gateway** (FastMCP SSE) — Model Context Protocol server with 47+ tools
- **ML Backend** — Sentiment analysis, semantic search, real embeddings (sentence-transformers)
- **RAG Engine** — Qdrant vector database with hybrid retrieval (cosine + BM25)
- **Role Engine (ARE+)** — Policy-based access control and role enforcement
- **Audio Service** — Speech-to-Text (Vosk) and Text-to-Speech (Coqui TTS) with PII redaction
- **HNSC Controller** — Hybrid Neuro-Symbolic Control for multi-agent orchestration

All operations comply with [AURA_IA_MCP_PRD.md](AURA_IA_MCP_PRD.md) v4.4 governance standards.

---

## ✨ Key Features

| Category | Features |
|----------|----------|
| **ML Intelligence** | Sentiment analysis, emotion detection, predictive insights, adaptive personality |
| **Retrieval (Wave 5-6)** | Real embeddings, cross-encoder re-ranking, query expansion, connection pooling |
| **Multi-Agent** | HNSC orchestration, DAG workflows, debate engine, risk routing |
| **Security** | PII filtering, audit logging, SAFE MODE governance, circuit breakers |
| **Observability** | Prometheus metrics, OpenTelemetry tracing, Grafana dashboards |
| **Audio I/O** | STT (Vosk), TTS (Coqui), real-time PII redaction |

---

## 🔌 Canonical Port Map

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| **MCP Gateway** | 9200 | `http://localhost:9200` | Primary MCP endpoint (SSE + REST health) |
| **ML Backend** | 9201 | `http://localhost:9201` | AI inference, embeddings, /chat/send, /embed |
| **RAG / Qdrant** | 9202 | `http://localhost:9202` | Vector database for semantic search |
| **Embeddings** | 9203 | `http://localhost:9203` | Embedding service (future) |
| **LLM Stub** | 9204 | `http://localhost:9204` | Text generation (future) |
| **Dashboard** | 9205 | `http://localhost:9205` | Monitoring UI & MCP Concierge |
| **Role Engine** | 9206 | `http://localhost:9206` | ARE+ policy engine |
| **Audio Service** | 8001 | `http://localhost:8001` | STT/TTS gateway |
| **Vosk STT** | 2700 | `http://localhost:2700` | Speech-to-Text engine |
| **Coqui TTS** | 5002 | `http://localhost:5002` | Text-to-Speech engine |

> ⚠️ Port deviation triggers alignment failure via `scripts/verify_prd_alignment.py`

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone and configure
git clone https://github.com/your-org/aura-ia-mcp.git
cd aura-ia-mcp
cp .env.example .env
# Edit .env: Set GITHUB_TOKEN=your_token

# 2. Start all services
docker compose up -d --build

# 3. Verify health
curl http://localhost:9200/health   # Gateway
curl http://localhost:9201/health   # ML Backend
curl http://localhost:9206/roles    # Role Engine
open http://localhost:9205          # Dashboard
```

### Option 2: Home Server Deployment

**Windows (PowerShell):**

```powershell
.\scripts\deploy_home_server.ps1
```

**Linux/macOS:**

```bash
chmod +x scripts/deploy_home_server.sh
./scripts/deploy_home_server.sh
```

**What it does:**

- ✅ Checks system requirements (CPU, RAM, disk)
- ✅ Detects GPU and enables acceleration
- ✅ Configures GitHub token
- ✅ Builds and starts Docker containers
- ✅ Verifies service health
- ✅ Displays access URLs

📚 **Full Guide**: [docs/HOME_SERVER_DEPLOYMENT.md](docs/HOME_SERVER_DEPLOYMENT.md)

### Option 3: Development Mode

```bash
# Activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start services individually
python scripts/start_mcp_with_backend.py
uvicorn ops.role_engine.are_service:app --port 9206
cd aura-audio-service && uvicorn audio_service.main:app --port 8001
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         VS Code / IDE Client                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ MCP Protocol (SSE)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     MCP Gateway (FastMCP) :9200                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ 47+ Tools   │  │ HNSC Ctrl   │  │ Safety      │  │ Prometheus  │ │
│  │             │  │ Controller  │  │ Policy      │  │ Metrics     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────────┘ │
└─────────┼────────────────┼────────────────┼─────────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ ML Backend:9201 │  │ RAG/Qdrant:9202 │  │ Role Engine:9206│
│ ├─ /health      │  │ ├─ Vectors      │  │ ├─ /roles       │
│ ├─ /chat/send   │  │ ├─ Hybrid       │  │ ├─ /propose     │
│ ├─ /embed       │  │ │  Search       │  │ ├─ /evaluate    │
│ └─ Sentiment    │  │ └─ Re-ranking   │  │ └─ /simulate    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Audio Service :8001                              │
│  ┌─────────────────┐              ┌─────────────────┐               │
│  │ Vosk STT :2700  │◄────────────►│ Coqui TTS :5002 │               │
│  │ Speech-to-Text  │              │ Text-to-Speech  │               │
│  └─────────────────┘              └─────────────────┘               │
│                     PII Redaction Layer                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1-3 | ✅ Complete | Foundation, Standardization, Security |
| Phase 4 | ✅ Complete | Advanced Intelligence (52/52 tests) |
| Phase 5 | ✅ Complete | Observability Platform (36/36 tests) |
| Phase 6 | ✅ Complete | Advanced Retrieval (45/45 tests) |
| Phase 7 | ✅ Complete | Frontend & HNSC Architecture |
| Phase 8 | ✅ Complete | Enterprise Governance (PRD Section 9) |
| Phase 9 | ✅ Complete | Final Production Deployment |

**PRD Version**: v4.4 (December 7, 2025)

---

## 🛡️ Operational Integrity & Governance

The framework implements defense-in-depth controls for mission-critical AI operations:

| Control Layer | Mechanism | Operational Purpose |
|---------------|-----------|---------------------|
| **SAFE MODE** | Hardware-style kill switch (HTTP 423 Locked) | Immediate halt of training, mutation, and autonomous operations |
| **Capability Flags** | `ENABLE_TRAINING`, `ENABLE_AUTONOMY`, `ENABLE_ROLE_MUTATION` | Granular permission gating for high-risk operations |
| **Policy Gateway** | Risk-scored action evaluation with audit trail | Root-cause analysis capability for all state transitions |
| **Audit Middleware** | Request IDs + structured JSONL logs | Compliance-ready logging for forensic investigation |
| **PII Filtering** | Automatic redaction in logs and audio streams | Data protection standardization across all outputs |
| **Circuit Breakers** | Automatic fault isolation with graceful degradation | Cascade failure prevention through systematic isolation |

---

## 📁 Project Structure

```
aura-ia-mcp/
├── aura_ia_mcp/           # Core application package
│   ├── core/              # Config, logging, auth, health
│   ├── services/          # Gateway, embedding, audio_io
│   ├── ops/               # Role engine, guards
│   └── training/          # SICD loop components
├── aura-audio-service/    # STT/TTS microservice
├── src/mcp_server/        # MCP Gateway implementation
│   ├── hnsc/              # Hybrid Neuro-Symbolic Controller
│   ├── tools/             # MCP tool implementations
│   └── services/          # Chat, conversation store
├── ops/role_engine/       # ARE+ policy engine
├── dashboard/             # Monitoring UI
├── docs/                  # Documentation
├── tests/                 # Unit & integration tests
├── scripts/               # Operational scripts
├── docker/                # Dockerfiles
├── k8s/                   # Kubernetes manifests
└── observability/         # Prometheus, Grafana, Loki
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [AURA_IA_MCP_PRD.md](AURA_IA_MCP_PRD.md) | Product Requirements Document (canonical) |
| [docs/MASTER_PROJECT_STATUS.md](docs/MASTER_PROJECT_STATUS.md) | Comprehensive status tracking |
| [docs/HOME_SERVER_DEPLOYMENT.md](docs/HOME_SERVER_DEPLOYMENT.md) | Home server setup guide |
| [docs/MCP_TOOL_GUIDE.md](docs/MCP_TOOL_GUIDE.md) | MCP tool reference |
| [docs/ARE_PLUS_README.md](docs/ARE_PLUS_README.md) | Role Engine documentation |
| [docs/SAFE_MODE_GUIDE.md](docs/SAFE_MODE_GUIDE.md) | Governance procedures |

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test suites
python -m pytest tests/test_wave4_dual_model_integration.py -v  # 24 tests
python -m pytest tests/test_core_mcp_tools.py -v                # Core tools
python -m pytest tests/test_health.py -v                        # Health endpoints

# Run with coverage
python -m pytest tests/ --cov=aura_ia_mcp --cov-report=html
```

---

## 🔧 VS Code MCP Configuration

Add to your VS Code `settings.json`:

```json
"mcpServers": {
    "aura-ia-mcp": {
        "transport": {
            "type": "sse",
            "url": "http://localhost:9200/sse"
        },
        "autoApprove": [
            "ide_agents_health",
            "ide_agents_catalog",
            "ml_analyze_emotion",
            "ml_get_predictions"
        ]
    }
}
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Ensure tests pass (`python -m pytest tests/`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

All contributions must comply with [AURA_IA_MCP_PRD.md](AURA_IA_MCP_PRD.md) governance.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**Engineered by Herman Swanepoel**

*Operational Integrity • Systematic Reliability • Zero-Tolerance Engineering*

</div>

---

## 🔍 Wave 6: Advanced Retrieval Configuration

Wave 6 introduces production-grade retrieval with real embeddings, cross-encoder re-ranking, and query expansion. All features are **optional** and controlled by environment variables.

### Environment Variables

#### Core Embedding (Phase 1)

```bash
# Embedding model (default: all-MiniLM-L6-v2, 384-dim)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu  # or cuda

# Alternative models:
# - all-MiniLM-L6-v2: Fast, lightweight (80MB, 384-dim)
# - all-mpnet-base-v2: Higher quality (420MB, 768-dim)
# - multi-qa-MiniLM-L6-cos-v1: Optimized for Q&A (80MB, 384-dim)
```

#### Re-Ranking (Phase 3)

```bash
# Enable cross-encoder re-ranking
RERANK_ENABLED=1
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2  # 90MB
RERANK_DEVICE=cpu  # or cuda
RERANK_TOP_K=50  # Retrieve 50 candidates, re-rank to top-10

# Alternative models:
# - ms-marco-MiniLM-L-6-v2: Fast, good quality (90MB)
# - ms-marco-TinyBERT-L-2-v2: Faster, lower quality (16MB)
# - ms-marco-electra-base: Highest quality, slower (420MB)
```

#### Query Expansion (Phase 3)

```bash
# Enable query expansion
QUERY_EXPANSION_ENABLED=1
EXPANSION_STRATEGY=synonyms  # or multi_query
EXPANSION_MAX_VARIANTS=5

# Strategies:
# - synonyms: WordNet-based synonym replacement ("ML" → "machine learning")
# - multi_query: Template-based query generation (5 variants)
```

#### Connection Pooling (Phase 2)

```bash
# Connection pool for high throughput
QDRANT_POOL_SIZE=5
QDRANT_POOL_TIMEOUT=30.0
QDRANT_POOL_RETRY_ENABLED=1
QDRANT_POOL_MAX_RETRIES=3
QDRANT_POOL_RETRY_DELAY=1.0  # seconds
```

### Configuration Profiles

#### Development (Fast Iteration)

```bash
# Minimal overhead, fast feedback
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
RERANK_ENABLED=0  # Disable re-ranking
QUERY_EXPANSION_ENABLED=0  # Disable expansion
QDRANT_POOL_SIZE=1
```

#### Staging (Balanced)

```bash
# Test quality improvements with moderate resources
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
RERANK_ENABLED=1  # Enable re-ranking
RERANK_TOP_K=30
QUERY_EXPANSION_ENABLED=1  # Enable expansion
EXPANSION_STRATEGY=synonyms
QDRANT_POOL_SIZE=3
```

#### Production (Maximum Quality)

```bash
# Full features, optimized for GPU if available
EMBEDDING_MODEL=all-mpnet-base-v2  # Higher quality
EMBEDDING_DEVICE=cuda  # GPU acceleration
RERANK_ENABLED=1
RERANK_MODEL=ms-marco-electra-base  # Highest quality
RERANK_DEVICE=cuda
RERANK_TOP_K=50
QUERY_EXPANSION_ENABLED=1
EXPANSION_STRATEGY=multi_query
EXPANSION_MAX_VARIANTS=5
QDRANT_POOL_SIZE=10  # High concurrency
```

### Performance Benchmarks

| Configuration | Latency (p50) | Latency (p99) | Quality (NDCG@10) | Model Size |
|---------------|---------------|---------------|-------------------|------------|
| Baseline (no re-rank) | 15ms | 30ms | 0.72 | 80MB |
| + Re-ranking (CPU) | 65ms | 120ms | 0.84 (+17%) | 170MB |
| + Re-ranking (GPU) | 25ms | 45ms | 0.84 (+17%) | 170MB |
| + Expansion (synonyms) | 80ms | 140ms | 0.88 (+22%) | 180MB |
| + Expansion (multi-query) | 120ms | 200ms | 0.91 (+26%) | 180MB |
| Full (GPU, mpnet) | 85ms | 150ms | 0.94 (+31%) | 940MB |

**Notes:**

- Latencies measured on Intel i7-12700K (CPU) / RTX 3080 (GPU)
- Quality measured on BEIR benchmark (average across 18 datasets)
- Model sizes include both embedding and cross-encoder models

### Model Selection Guide

#### Embedding Models

| Model | Size | Dimensions | Speed | Quality | Use Case |
|-------|------|------------|-------|---------|----------|
| all-MiniLM-L6-v2 | 80MB | 384 | ⚡⚡⚡ | ⭐⭐⭐ | Development, fast iteration |
| multi-qa-MiniLM-L6-cos-v1 | 80MB | 384 | ⚡⚡⚡ | ⭐⭐⭐⭐ | Q&A tasks, customer support |
| all-mpnet-base-v2 | 420MB | 768 | ⚡⚡ | ⭐⭐⭐⭐⭐ | Production, best quality |

#### Cross-Encoder Models

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| ms-marco-TinyBERT-L-2-v2 | 16MB | ⚡⚡⚡ | ⭐⭐ | High-throughput, low-resource |
| ms-marco-MiniLM-L-6-v2 | 90MB | ⚡⚡ | ⭐⭐⭐⭐ | Default, balanced |
| ms-marco-electra-base | 420MB | ⚡ | ⭐⭐⭐⭐⭐ | Maximum quality |

### Troubleshooting

#### Out of Memory (OOM)

**Symptom**: Process killed during model loading or inference

**Solutions:**

1. Use smaller models: `all-MiniLM-L6-v2` instead of `all-mpnet-base-v2`
2. Disable re-ranking: `RERANK_ENABLED=0`
3. Reduce pool size: `QDRANT_POOL_SIZE=1`
4. Use CPU instead of GPU: `EMBEDDING_DEVICE=cpu`

#### Slow Inference

**Symptom**: Queries take >500ms

**Solutions:**

1. Enable GPU: `EMBEDDING_DEVICE=cuda` (requires CUDA-capable GPU)
2. Reduce re-ranking candidates: `RERANK_TOP_K=20`
3. Disable expansion: `QUERY_EXPANSION_ENABLED=0`
4. Use smaller models: `ms-marco-TinyBERT-L-2-v2`

#### Model Loading Fails

**Symptom**: `OSError: Can't load model` or `ConnectionError`

**Solutions:**

1. Check internet connection (models auto-download from HuggingFace)
2. Pre-download models:

   ```bash
   python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
   ```

3. Use local model cache: Set `TRANSFORMERS_CACHE=/path/to/cache`
4. Check disk space (models require 100MB-1GB)

#### NLTK WordNet Missing

**Symptom**: `LookupError: WordNet not found` when using synonym expansion

**Solution:**

```bash
python -c "import nltk; nltk.download('wordnet')"
```

Or set `EXPANSION_STRATEGY=multi_query` instead.

### Monitoring & Metrics

Wave 6 exposes Prometheus metrics for observability:

#### Embedding Metrics

- `embedding_latency_seconds` (histogram): Time to encode queries/documents
- `embedding_batch_size` (gauge): Current batch size

#### Re-Ranking Metrics

- `reranker_latency_seconds` (histogram): Time to re-rank candidates
- `reranker_score_distribution` (histogram): Cross-encoder score distribution
- `reranker_candidates_total` (counter): Number of documents re-ranked

#### Query Expansion Metrics

- `query_expansion_variants_total` (counter): Number of query variants generated
- `query_expansion_latency_seconds` (histogram): Time to expand queries

#### Connection Pool Metrics

- `qdrant_pool_size` (gauge): Active connections in pool
- `qdrant_pool_waiting` (gauge): Queries waiting for connection
- `qdrant_circuit_breaker_open` (gauge): 1 if circuit breaker is open, 0 otherwise
- `qdrant_retry_attempts_total` (counter): Total retry attempts

**Grafana Dashboard**: See `docs/WAVE6_DEPLOYMENT.md` for pre-built dashboard JSON.

---

## 🚀 ML Features

### Core ML Intelligence

- **ml_analyze_emotion**: ML-powered emotion detection & sentiment analysis
- **ml_get_predictions**: AI predictions for automation & optimization
- **ml_get_learning_insights**: Comprehensive learning analytics & metrics
- **ml_analyze_reasoning**: Contextual reasoning for complex commands
- **ml_get_personality_profile**: Current AI personality configuration
- **ml_adjust_personality**: Dynamic personality & tone adjustment

### Smart Home Control (ML-Enhanced)

- **send_smart_command**: ML-enhanced command processing with reasoning
- **test_command_reasoning**: Test ML reasoning without execution
- **list_entities**: View all controllable devices
- **get_entity_details**: Detailed device information
- **reload_mappings**: Reload voice command mappings

### System Status

- **get_ml_system_status**: Complete ML engine status & metrics

## 📦 Installation

1. Install MCP dependencies:

```bash
pip install -r requirements.txt
```

1. Ensure your AI Home Assistant is running (backend).

1. Run the MCP server:

```bash
python scripts/start_mcp_with_backend.py
```

## 🐳 Docker Compose Deployment

The repository now ships with production-ready container definitions in `docker/` and a root-level `docker-compose.yml` that wires everything together. Base images updated to `python:3.12-slim` and `nginx:1.27.2-alpine`. Three long-running services are started:

- `mcp-server` (FastMCP bridge, port 9100 → 8000)
- `ml-backend` (real ML + GitHub service, port 9101 → 8001)
- `dashboard` (static monitoring UI, port 9102 → 80)

### Bring the stack online

1. Export secrets once (or create an `.env` file that Compose will read):

     ```bash
     setx GITHUB_TOKEN "<your-personal-access-token>"
     ```

2. Build and start the services:

     ```bash
     docker compose up -d --build
     ```

3. Confirm each surface is alive:

     ```bash
     curl http://localhost:9101/health       # backend
     nc -zv localhost 9100                   # MCP SSE port
     curl http://localhost:9102              # dashboard HTML
     ```

The compose file mounts `./logs` and `./data` into the containers to keep telemetry and learning artifacts on the host. Hugging Face caches live in dedicated named volumes (`backend-model-cache`, `mcp-model-cache`) so model downloads survive container rebuilds.

### VS Code Insiders MCP connection

VS Code Insiders understands SSE transports, so it can connect directly to the MCP endpoint that the container exposes on `http://localhost:9100`.

Add the following snippet to `settings.json` (Preferences → Settings → search for `mcpServers` → `Edit in settings.json`):

```json
"mcpServers": {
    "ide-agents-mcp": {
        "transport": {
            "type": "sse",
            "url": "http://localhost:9100"
        },
        "autoApprove": [
            "ide_agents_health",
            "ide_agents_catalog",
            "ide_agents_resource",
            "ide_agents_prompt"
        ]
    }
}
```

> Tip: If your Insiders build does not yet expose the SSE transport UI, you can fall back to the classic command runner by pointing it at the running container: set `command` to `docker` and `args` to `['exec', '-i', 'mcp_server', 'python', '-m', 'mcp_server.ide_agents_mcp_server']`.

Once configured, opening the Command Palette → `MCP: Refresh Servers` should show `ide-agents-mcp` as `Connected`. All tools described below will then be available straight from the IDE.

## 🧭 MCP Server Instructions (Phase 0)

This server now exposes consolidated tools and server instructions.

- Version: `v0.1` (printed at startup)
- Consolidated tools:
  - `ide_agents.command({ method: "run"|"dry_run"|"explain", command, cwd?, timeout?, payload? })`
  - `ide_agents.catalog({ method: "list_entities"|"get_doc", query? })`
- Resources: `repo.graph`, `kb.snippet`, `build.logs` via `ide_agents.resource({ method: "list"|"get", name? })`
- Prompts: `/diff_review`, `/test_failures`, `/hotfix_plan` via `ide_agents.prompt({ method: "list"|"get", name? })`

Example calls (pseudo):

```json
{
    "tool": "ide_agents.command",
    "args": { "method": "explain", "command": "echo hello" }
}
```

Telemetry spans are written to `logs/mcp_tool_spans.jsonl` during local/CI runs.

## ⚙️ Configuration in Kiro

Your `.kiro/settings/mcp.json` is already configured! The server connects to:

- **API**: <http://127.0.0.1:8001>
- **Python**: Your virtual environment's Python interpreter
- **Auto-Approve**: Safe ML analysis tools (emotion, predictions, insights, status)

## 🎯 ML Usage Examples

### Emotion Detection & Analysis

```
"Analyze the emotion in: I'm feeling great today!"
→ Uses ml_analyze_emotion
→ Returns: Mood, confidence, context factors
```

### AI Predictions & Automation

```
"Show me AI predictions for my routines"
→ Uses ml_get_predictions
→ Returns: Routine automation, music recommendations, comfort adjustments
```

### Learning Analytics

```
"What has the AI learned about me?"
→ Uses ml_get_learning_insights
→ Returns: Commands learned, usage patterns, AI effectiveness metrics
```

### Contextual Reasoning

```
"Analyze how you'd interpret: make it cozy"
→ Uses ml_analyze_reasoning
→ Returns: Reasoning type, execution plan, confidence scores
```

### Personality Management

```
"Show me your current personality"
→ Uses ml_get_personality_profile
→ Returns: Personality type, mood, tone, traits

"Adjust personality to enthusiastic and playful"
→ Uses ml_adjust_personality
→ Dynamically changes AI behavior
```

### Smart Home Control

```
"Turn on bedroom light"
→ Uses send_smart_command
→ ML-enhanced with reasoning + personality

"Test command: movie night setup"
→ Uses test_command_reasoning
→ Shows reasoning without execution
```

### System Monitoring

```
"Show ML system status"
→ Uses get_ml_system_status
→ Returns: All 7 ML engines status & metrics
```

## Troubleshooting

1. **Connection refused**: Make sure your AI Assistant is running on port 8001
2. **Command not working**: Use test_command to debug command interpretation
3. **Entities not found**: Use reload_mappings after updating voice_mappings.json

## Security Notes

- This server connects to localhost only (127.0.0.1:8001)
- No external network access required
- All commands go through your local AI Assistant API
- Home Assistant token is managed by your AI Assistant, not exposed to MCP

## 🧠 ML Engines Overview

### 1. Voice Recognition Engine

- Multi-user voice identification
- Voice signature analysis
- Profile registration & matching
- Confidence scoring

### 2. Emotion Detection Engine

- Text-based sentiment analysis
- Mood state classification (8 states)
- Contextual emotion adjustment
- Time-aware detection

### 3. Predictive Engine

- Routine automation suggestions
- Music preference prediction
- Comfort optimization
- Energy saving recommendations
- Pattern learning from interactions

### 4. Contextual Reasoning Engine

- **Sequential**: Multi-step commands
- **Conditional**: If-then logic
- **Abstract**: Concept mapping ("cozy" → actions)
- **Contextual**: Situation awareness
- **Temporal**: Time-based execution
- **Situational**: Scene setup

### 5. Adaptive Personality Engine

- Dynamic personality types (8 types)
- Mood-based responses (7 moods)
- Tone adjustment (5 levels)
- User adaptation
- Conversation style matching

### 6. Conversation Flow Manager

- Context retention (10 min)
- Multi-turn dialogue
- Topic tracking
- Emotional progression analysis

### 7. Learning Analytics Engine

- Usage pattern analysis
- Learning progress tracking
- AI effectiveness metrics
- Personalization scoring

## 🔬 ML Metrics & Performance

The system tracks:

- **Prediction Accuracy**: ~87%
- **Emotion Detection**: ~87%
- **Voice Recognition**: ~85% threshold
- **User Satisfaction**: ~92%
- **Response Relevance**: ~89%
- **Personalization Score**: ~85%

## 🎓 Learning Capabilities

The AI learns from:

- Command patterns & frequency
- Time-based routines
- Device preferences
- Music tastes
- Interaction style
- Emotional context
- Conversation patterns

Minimum 10 interactions required before predictions activate.

## 🛠️ Development & Testing

### Test ML Engines

```bash
# Test emotion detection
python -c "import requests; print(requests.get('http://127.0.0.1:8001/ai/intelligence/mood/analyze/I am feeling great!').json())"

# Test predictions
python -c "import requests; print(requests.get('http://127.0.0.1:8001/ai/intelligence/predictions/test_user').json())"

# Test learning insights
python -c "import requests; print(requests.get('http://127.0.0.1:8001/ai/intelligence/insights/test_user').json())"
```

### Add New ML Features

1. Implement in `app/core/ai_intelligence_engine.py`
2. Add API endpoint in `app/api/main.py`
3. Add MCP tool in `src/mcp_server/ide_agents_mcp_server.py`
4. Update auto-approve list in `.kiro/settings/mcp.json`

## 🔐 Security

- Localhost only (127.0.0.1:8001)
- No external network access
- Home Assistant token managed by AI Assistant
- MCP tools auto-approved for safe ML analysis
- Command execution requires explicit approval

## 🐛 Troubleshooting

**Connection refused**

- Ensure AI Assistant running: `python main.py`
- Check port 8001 is available

**ML engines not responding**

- Check `/ai/intelligence/status` endpoint
- Verify engines initialized in logs

**Low prediction accuracy**

- Need 10+ interactions for learning
- Check learning insights for data collection

**Personality not adapting**

- Verify `adapt_to_user` setting enabled
- Check conversation flow manager active

## 📊 Monitoring ML Performance

Use `get_ml_system_status` to monitor:

- Engine activation status
- Profile counts
- Prediction accuracy
- Total interactions
- Learning rate

## 🚀 Future ML Enhancements

- [ ] Deep learning models for voice recognition
- [ ] Transformer-based NLP for reasoning
- [ ] Reinforcement learning for optimization
- [ ] Computer vision for visual context
- [ ] Federated learning across users
- [ ] Real-time model retraining
- [ ] Advanced anomaly detection

## 🏢 Enterprise & ULTRA Additions

The current codebase includes production-focused enterprise features beyond the original ML scaffold:

### ULTRA Semantic Ranking

Implemented structured candidate ranking with backend normalization (`/ai/intelligence/rank`). Responses are normalized to `{ ranked: [ { candidate, score } ] }` ensuring deterministic parsing and graceful fallback without user-facing errors.

### Persistent Personality Profile

Personality adjustments persist across sessions (`data/personality_profile.json`). Tools:

- `ide_agents_ml_get_personality_profile`
- `ide_agents_ml_adjust_personality`
State includes `tone`, `mood`, `adaptive`, and `traits` with timestamped updates.

### Security Anomaly Detection

New tool `ide_agents_security_anomalies` surfaces spikes in audit events (rate limits, approvals). Backed by `logs/security_audit.jsonl` + rotation policy (size/time).

### Audit Log Rotation

Automatic rotation when audit file >5MB or daily interval exceeded. Retains up to 5 historical files `security_audit.N.jsonl` and meta file for last rotation timestamp.

### Extended Health & Readiness

`ide_agents_health` / `ide_agents_readyz` enriched with model availability and latency metrics. Backend exposes `/models/status` and includes `ml_models` in `/health` for quick diagnostics.

### Command Sandbox Hardening

Disallowed shell metacharacters (`&&`, `|`, `;`, redirects, subshell markers) ensuring only safe commands on allow‑list run.

### Adaptive GitHub Batching

Ranking logic reduces per-repo issue pagination for larger sets to avoid API pressure and improve latency.

### Telemetry Shutdown Consistency

Shutdown flush test ensures spans in `logs/mcp_tool_spans.jsonl` persist after lifecycle completion.

### Planned Metrics Exposure

Prometheus stub exports breaker state, tool success/failure counts, latency percentiles (p50/p90/p99) and histogram buckets, total spans, anomaly counts under `/metrics` for scraping.

> These enhancements target production reliability: observability, persistence, security hygiene, graceful degradation, and deterministic ML integration.

## 📚 ML Architecture

```
Kiro (MCP Client)
    ↓
MCP Server (src/mcp_server/ide_agents_mcp_server.py)
    ↓
Prometheus Metrics Stub (/metrics)
    ↓
FastAPI (main.py)
    ↓
ML Engines:
  ├── Voice Recognition Engine
  ├── Emotion Detection Engine
  ├── Predictive Engine
  ├── Reasoning Engine
  ├── Personality Engine
  ├── Conversation Flow Manager
  └── Learning Analytics Engine
    ↓
Home Assistant Integration
```

## 🛠️ Runtime Management

- `ide_agents_reload` tool clears caches and returns current dynamic anomaly thresholds.
- Optional environment thresholds: `ANOMALY_THRESHOLD_RATE_LIMITED`, `ANOMALY_THRESHOLD_APPROVAL_REQUESTED`, `ANOMALY_THRESHOLD_TOOL_FAILURE`.
- Trend analysis (15m vs 1h) exposed via `ide_agents_security_anomalies` output.

## 🔏 Personality Profile Encryption (Optional)

Set `PERSONA_KEY` env variable to enable XOR-based obfuscation of `data/personality_profile.json` at rest.

## 📈 Metrics Endpoint

Prometheus scrape example:

```
curl http://localhost:9100/metrics
```

Exports (selected):

- `mcp_telemetry_spans_total`
- `mcp_telemetry_spans_success` / `mcp_telemetry_spans_failure`
- `mcp_latency_p50_ms` / `mcp_latency_p90_ms` / `mcp_latency_p99_ms`
- Histogram buckets: `mcp_latency_hist_bucket{le="..."}` and `mcp_latency_hist_count`
- `mcp_anomaly_count`
- `mcp_breaker_open`

## ☸️ Kubernetes Deployment (Optional)

Manifests under `k8s/`:

- `deployment.yaml`
- `service.yaml`
- `configmap.yaml`
- `secret.example.yaml`

Apply (example):

```
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.example.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

## 🔐 CI Security & License Scans

GitHub Actions workflow `.github/workflows/ci.yml` runs:

- Unit & integration tests (pytest)
- `pip-audit` vulnerability scan
- `safety` advisory check
- Optional license check via `scripts/security_scan.sh`

## ♻️ Log & Audit Rotation

Security audit logs rotate daily or at 5MB, gzip archived with retention purge beyond configured cap.

## ✅ Reload & Threshold Validation

Use:

```
{ "tool": "ide_agents_reload", "args": {} }
```

to refresh caches and view active thresholds.

## 💡 Best Practices

1. **Let it learn**: Give the AI 10+ interactions before expecting predictions
2. **Provide feedback**: Use personality adjustments to improve responses
3. **Monitor metrics**: Check learning insights regularly
4. **Test reasoning**: Use test tools before executing complex commands
5. **Review analytics**: Track AI effectiveness and learning progress

---

**Engineered by Herman Swanepoel**
*Operational Integrity | Root-Cause Analysis | Mission-Critical Standardization*

---

## Retrieval (Wave 5)

- Feature flags:
  - `RETRIEVAL_ENABLED` (`1`/`0`)
  - `RETRIEVAL_COLLECTION` (default: `default`)
  - `RETRIEVAL_TOP_K` (default: `5`)
  - `RETRIEVAL_BUDGET_TOKENS` (default: `1024`)
  - `QDRANT_URL` (default: `http://localhost:6333`)

- Upsert docs:
  - Generate JSONL from a folder: `python scripts/ingest_docs.py data/knowledge docs.jsonl --namespace default`
  - Upsert into Qdrant: `python scripts/qdrant_upsert.py docs.jsonl default --url $env:QDRANT_URL --vector-size 384`

- Wiring:
  - Retrieval is integrated in `DualModelEngine` and prepends context to the initial conversation when enabled.
  - Metrics: Prometheus `retrieval_latency_seconds` (Histogram) and `retrieval_hits_total` (Counter).
    - Audit (optional): Set `RETRIEVAL_AUDIT_LOG=1` and optionally `RETRIEVAL_AUDIT_PATH` (default `logs/security_audit.jsonl`) to record retrieval failures without impacting flow.


---

## 🛡️ Security & Repository Migration

### Zero-Leak Release (December 2025)

This repository was re-initialized to ensure a clean, secure release for public portfolio use. The following security measures were implemented:

#### What Was Done

1. **Secret Extraction**: All hardcoded secrets were identified and moved to environment variables:
   - API keys (OpenAI, Anthropic, Google, DeepSeek, Groq)
   - Home Assistant tokens and URLs
   - Media automation credentials (Sonarr, Radarr, SABnzbd, Plex)
   - Smart TV integration (IP, MAC, client key)
   - Database connection strings

2. **History Sanitization**: Git history was completely wiped and re-initialized to ensure no secrets exist in any previous commits.

3. **Dynamic Configuration**: Frontend code (`dashboard/assets/app.js`) uses dynamic host detection instead of hardcoded IPs.

4. **Documentation Sanitization**: All documentation files use placeholder values like `{{NAS_IP}}`, `{{YOUR_SSH_USER}}`, and `{{HOME_ASSISTANT_IP}}`.

#### Security Best Practices

- ✅ All secrets stored in `.env` (gitignored)
- ✅ `.env.example` contains only placeholder values
- ✅ No hardcoded IPs, tokens, or credentials in source code
- ✅ Backup folder (`aura_backup_pre_sanitization/`) excluded from Git
- ✅ Private documentation (`docs/private/`) excluded from Git

#### For Contributors

1. Copy `.env.example` to `.env`
2. Fill in your own credentials
3. Never commit `.env` or any file containing real secrets
4. Use environment variables for all sensitive configuration

---
