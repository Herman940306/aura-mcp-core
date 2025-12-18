# Codex MCP Integration Guide

**Version:** 1.1.0  
**Last Updated:** December 7, 2025  
**PRD Reference:** Section 8.14  
**Status:** Production-Ready

---

## Overview

This guide documents how to configure OpenAI Codex to work alongside Aura IA MCP in a **Co-MCP architecture** where:

- **Aura IA MCP (LEAD)**: Handles HNSC safety, tool governance, role enforcement, and orchestration
- **Codex (CO-MCP)**: Handles code generation, file operations, and shell commands

The integration supports:

- Codex as an MCP **client** connecting to Aura IA servers
- Codex as an MCP **server** that Aura IA can invoke as a tool
- Both Streamable HTTP and STDIO transports

---

## Architecture: Lead + Co-MCP

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Multi-Agent MCP Architecture                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    AURA IA MCP (LEAD)                            │   │
│   │  ┌─────────────────────────────────────────────────────────┐    │   │
│   │  │              HNSC Architecture (6 Layers)                │    │   │
│   │  │  Safety → Tools → Reasoning → Workflow → Router → LLM   │    │   │
│   │  └─────────────────────────────────────────────────────────┘    │   │
│   │                           │                                      │   │
│   │    ┌──────────────────────┼──────────────────────┐              │   │
│   │    ▼                      ▼                      ▼              │   │
│   │ ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌────────────┐         │   │
│   │ │:9200 │  │:9201 │  │:9202 │  │:9206 │  │  :9207     │         │   │
│   │ │Gate- │  │ML    │  │RAG   │  │Role  │  │  Ollama    │         │   │
│   │ │way   │  │Back  │  │Qdrant│  │Engine│  │  Agents    │         │   │
│   │ └──────┘  └──────┘  └──────┘  └──────┘  └────────────┘         │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│                    ┌───────────────┴───────────────┐                    │
│                    ▼                               ▼                    │
│   ┌────────────────────────────┐  ┌────────────────────────────┐       │
│   │     CODEX (CO-MCP)         │  │     External Clients       │       │
│   │  ┌──────────────────────┐  │  │  ┌──────────────────────┐  │       │
│   │  │ codex mcp-server     │  │  │  │ IDE Extensions       │  │       │
│   │  │ • codex tool         │  │  │  │ CLI Tools            │  │       │
│   │  │ • codex-reply tool   │  │  │  │ Other MCP Clients    │  │       │
│   │  └──────────────────────┘  │  │  └──────────────────────┘  │       │
│   │                            │  │                            │       │
│   │  Responsibilities:         │  │                            │       │
│   │  • Code generation         │  │                            │       │
│   │  • File operations         │  │                            │       │
│   │  • Shell commands          │  │                            │       │
│   │  • Workspace management    │  │                            │       │
│   └────────────────────────────┘  └────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Copy Configuration File

```bash
# Copy the configuration to your Codex config directory
cp config/codex_mcp_servers.toml ~/.config/codex/mcp_servers.toml

# Or use the project-local configuration
# Codex will auto-detect config/codex_mcp_servers.toml in your project root
```

### 2. Verify Docker Stack is Running

```bash
# Start the Aura IA Docker stack
docker compose up -d

# Verify all services are healthy
docker compose ps
```

### 3. List Available Servers

```bash
codex mcp list
```

Expected output:

```
┌─────────────────┬────────────────────────────────────┬─────────┐
│ Name            │ URL                                │ Status  │
├─────────────────┼────────────────────────────────────┼─────────┤
│ aura_gateway    │ http://localhost:9200/mcp/stream   │ enabled │
│ aura_ml         │ http://localhost:9201/mcp/stream   │ enabled │
│ aura_ollama     │ http://localhost:9207/mcp/stream   │ enabled │
│ aura_role_engine│ http://localhost:9206/mcp/stream   │ enabled │
│ codex_agent     │ codex mcp-server (STDIO)           │ enabled │
└─────────────────┴────────────────────────────────────┴─────────┘
```

---

## Server Configuration

### Aura Gateway (LEAD MCP - Primary Entry Point)

The main MCP server providing access to all 49+ tools. This is the **LEAD MCP** that governs all tool execution through HNSC architecture.

```toml
[mcp_servers.aura_gateway]
url = "http://localhost:9200/mcp/stream"
startup_timeout_sec = 30
tool_timeout_sec = 120
enabled = true

# Security: Block sensitive tools
disabled_tools = ["execute_command", "request_approval"]
```

**Available Tools:**

- Health & Status: `check_health`, `get_system_status`, `get_model_status`
- AI/ML: `analyze_emotion`, `semantic_rank`
- Debate Engine: `start_debate`, `get_debate_status`
- DAG Orchestration: `create_workflow`, `execute_workflow`, `visualize_dag`
- Risk Assessment: `evaluate_risk`
- Role Engine: `list_roles`, `get_role_capabilities`, `suggest_role`, `check_permission`
- Ollama: `ollama_consult`, `ollama_list_models`, `ollama_model_info`, `ollama_health`
- And many more...

### Aura ML Backend (Direct ML Access)

Direct access to ML inference capabilities.

```toml
[mcp_servers.aura_ml]
url = "http://localhost:9201/mcp/stream"
startup_timeout_sec = 20
tool_timeout_sec = 60
enabled = true

enabled_tools = ["analyze_emotion", "semantic_rank", "get_model_status"]
```

### Aura Ollama (External LLM Consultation)

Access to Ollama models for specialist knowledge queries.

```toml
[mcp_servers.aura_ollama]
url = "http://localhost:9207/mcp/stream"
startup_timeout_sec = 30
tool_timeout_sec = 180  # Longer timeout for LLM generation
enabled = true

enabled_tools = ["ollama_consult", "ollama_list_models", "ollama_model_info", "ollama_health"]
disabled_tools = ["ollama_pull_model"]  # Security: Block model pulling
```

**Usage Example:**

```
User: Consult the Ollama code expert about Python async patterns

Codex: [Calls ollama_consult with task_type="code"]
```

### Aura Role Engine (Permissions & Trust)

Query role capabilities and permissions.

```toml
[mcp_servers.aura_role_engine]
url = "http://localhost:9206/mcp/stream"
startup_timeout_sec = 15
tool_timeout_sec = 30
enabled = true

enabled_tools = ["list_roles", "get_role_capabilities", "suggest_role", "check_permission"]
```

---

## Codex as MCP Server (CO-MCP)

Codex can run as an MCP server via `codex mcp-server`, enabling Aura IA to invoke Codex as a tool inside its multi-agent framework.

### Configuration

```toml
[mcp_servers.codex_agent]
command = "codex"
args = ["mcp-server"]
startup_timeout_sec = 60
tool_timeout_sec = 600000  # 10 minutes - Codex sessions can take time
enabled = true

[mcp_servers.codex_agent.env]
CODEX_APPROVAL_POLICY = "on-failure"
CODEX_SANDBOX = "workspace-write"
CODEX_MODEL = "o4-mini"
```

### Available Tools (when Codex is server)

| Tool | Description |
|------|-------------|
| `codex` | Run a Codex session with full configuration |
| `codex-reply` | Continue an existing Codex conversation |

### The `codex` Tool Properties

| Property | Type | Description |
|----------|------|-------------|
| `prompt` (required) | string | Initial user prompt for Codex conversation |
| `approval-policy` | string | `untrusted`, `on-failure`, `on-request`, `never` |
| `base-instructions` | string | Override default instructions |
| `config` | object | Override config.toml settings |
| `cwd` | string | Working directory for session |
| `model` | string | Model override (`o3`, `o4-mini`, etc.) |
| `profile` | string | Configuration profile from config.toml |
| `sandbox` | string | `read-only`, `workspace-write`, `danger-full-access` |

### The `codex-reply` Tool Properties

| Property | Type | Description |
|----------|------|-------------|
| `prompt` (required) | string | Next user prompt to continue conversation |
| `conversationId` (required) | string | ID of conversation to continue |

### Launch Codex MCP Server

```bash
# Direct launch
codex mcp-server

# With MCP Inspector (for debugging)
npx @modelcontextprotocol/inspector codex mcp-server
```

### Example: Building a Tic-Tac-Toe Game

Using the MCP Inspector with `codex mcp-server`:

1. Set timeouts to 600000ms (10 minutes) in ⛭ Configuration
2. Send `tools/list` to see available tools
3. Call `codex` tool with:

   ```json
   {
     "prompt": "Implement a simple tic-tac-toe game with HTML, JavaScript, and CSS. Write the game in a single file called index.html.",
     "approval-policy": "never",
     "sandbox": "workspace-write"
   }
   ```

4. Watch events as Codex builds the game

---

## Tracing & Verbose Logging

Codex uses `RUST_LOG` environment variable for logging configuration.

### TUI Mode (Interactive)

```bash
# Default: RUST_LOG=codex_core=info,codex_tui=info,codex_rmcp_client=info
# Logs written to: ~/.codex/log/codex-tui.log

# Monitor logs in real-time
tail -F ~/.codex/log/codex-tui.log
```

### Non-Interactive Mode (codex exec)

```bash
# Default: RUST_LOG=error
# Messages printed inline (no separate file)

# Enable verbose logging
RUST_LOG=codex_core=debug codex exec "your prompt"
```

### Common Log Levels

- `error` - Only errors
- `warn` - Warnings and errors
- `info` - General information (default for TUI)
- `debug` - Detailed debugging
- `trace` - Very verbose tracing

---

## Alternative: STDIO Configuration

For local development without Docker:

```toml
[mcp_servers.aura_local]
command = "python"
args = ["-m", "aura_ia_mcp.main", "--mode", "stdio"]
cwd = "/path/to/LATEST_MCP"
startup_timeout_sec = 30
tool_timeout_sec = 120
enabled = true

[mcp_servers.aura_local.env]
AURA_LOG_LEVEL = "INFO"
AURA_BACKEND_URL = "http://localhost:9201"
```

---

## CLI Commands Reference

### List Servers

```bash
# Pretty table output
codex mcp list

# JSON output for scripting
codex mcp list --json
```

### Show Server Details

```bash
codex mcp get aura_gateway
codex mcp get aura_gateway --json
```

### Add Server Dynamically

```bash
# Add with environment variables
codex mcp add my_server --env API_KEY=secret -- python -m my_server

# Add with specific working directory
codex mcp add docs_server -- docs-server --port 4000
```

### Remove Server

```bash
codex mcp remove my_server
```

### OAuth Authentication

```bash
# Login to server supporting OAuth
codex mcp login aura_gateway

# Logout
codex mcp logout aura_gateway
```

---

## Feature Flags

Enable experimental features in your configuration:

```toml
[features]
# Enable Rust MCP client for OAuth support and better performance
rmcp_client = true
```

---

## Security Best Practices

### 1. Tool Filtering

Always use `disabled_tools` to block sensitive operations:

```toml
disabled_tools = [
    "execute_command",      # Shell access
    "request_approval",     # Internal workflow
    "ollama_pull_model",    # Resource-intensive
]
```

### 2. Timeout Configuration

Set appropriate timeouts based on operation complexity:

| Operation Type | Recommended Timeout |
|----------------|---------------------|
| Health checks  | 10-15s |
| Simple queries | 30-60s |
| ML inference   | 60-120s |
| LLM generation | 120-180s |

### 3. Rate Limiting

The Aura IA backend enforces per-user rate limits via TokenBucket:

- Default: 100 requests per minute
- Configurable via `AURA_RATE_LIMIT` environment variable

### 4. Audit Logging

All Codex tool invocations are logged to:

- `logs/codex_tool_spans.jsonl` - Tool call traces
- `logs/security_audit.jsonl` - Security events

---

## Troubleshooting

### Server Not Responding

1. Check Docker services are running:

   ```bash
   docker compose ps
   ```

2. Verify port accessibility:

   ```bash
   curl http://localhost:9200/health
   ```

3. Check server logs:

   ```bash
   docker compose logs aura-ia-mcp
   ```

### Tool Timeout

1. Increase timeout in configuration:

   ```toml
   tool_timeout_sec = 180
   ```

2. Check backend load:

   ```bash
   curl http://localhost:9201/metrics
   ```

### Authentication Issues

1. Enable OAuth feature flag:

   ```toml
   [features]
   rmcp_client = true
   ```

2. Run OAuth login:

   ```bash
   codex mcp login aura_gateway
   ```

---

## Architecture Integration

```
┌──────────────────────────────────────────────────────────────────┐
│                       Codex Client                                │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │               MCP Protocol (Streamable HTTP)                 │ │
│  └────────────────────────────┬────────────────────────────────┘ │
└───────────────────────────────┼──────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                    Aura IA Gateway :9200                          │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   HNSC Architecture                          │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │  │
│  │  │Layer 6  │  │Layer 5  │  │Layer 4  │  │Layer 3  │        │  │
│  │  │Safety   │→│Tools    │→│Reasoning│→│Workflow │        │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │  │
│  │       ↓            ↓                                        │  │
│  │  ┌─────────┐  ┌─────────┐                                  │  │
│  │  │Layer 2  │  │Layer 1  │                                  │  │
│  │  │Router   │→│LLM      │                                  │  │
│  │  └─────────┘  └─────────┘                                  │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
    ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
    │ML :9201 │   │RAG :9202│   │Role:9206│   │Ollama   │
    │Backend  │   │Qdrant   │   │Engine   │   │:9207    │
    └─────────┘   └─────────┘   └─────────┘   └─────────┘
```

---

## Related Documentation

- [AURA_IA_MCP_PRD.md](../AURA_IA_MCP_PRD.md) - Canonical PRD (Section 8.14)
- [MASTER_PROJECT_STATUS.md](MASTER_PROJECT_STATUS.md) - Project status
- [MCP_TOOL_GUIDE.md](MCP_TOOL_GUIDE.md) - Full tool reference
- [SAFE_MODE_GUIDE.md](SAFE_MODE_GUIDE.md) - Safety features

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-07 | Initial Codex MCP integration |
