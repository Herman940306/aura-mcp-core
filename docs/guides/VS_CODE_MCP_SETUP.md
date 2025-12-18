# VS Code Insiders MCP Setup (Docker SSE)

Use this guide to connect VS Code Insiders’ Copilot Chat to your Dockerized MCP server.

## 1) Start the stack

```powershell
# Optional: set GitHub token once (reopen shell after setx)
setx GITHUB_TOKEN "<your-token>"

# Bring services up
./scripts/dev_up.ps1 -Rebuild

# Verify
./scripts/verify_stack.ps1
```

Expected:
- Backend: OK on http://localhost:9101/health
- MCP SSE: listening on http://localhost:9100
- Dashboard: http://localhost:9102

## 2) Configure VS Code Insiders

Open `.vscode/settings.json` and ensure:

```json
{
  "mcpServers": {
    "dev-assistant-mcp": {
      "transport": { "type": "sse", "url": "http://localhost:9100" },
      "autoApprove": [
        "ide_agents_health",
        "ide_agents_catalog",
        "ide_agents_resource",
        "ide_agents_prompt",
        "ide_agents_github_repos",
        "ide_agents_github_rank_repos",
        "ide_agents_github_rank_all"
      ]
    }
  }
}
```

Reload window, run `MCP: Refresh Servers`, verify status shows Connected.

## 3) Quick validation

- "Check MCP server health" ? ok, version
- "Show me repo.graph" ? resource content
- "Find my GitHub repositories related to Python" ? requires GITHUB_TOKEN

## 4) Dev loop

```powershell
# Rebuild images after code changes
./scripts/dev_up.ps1 -Rebuild

# Tail logs
./scripts/dev_logs.ps1
```

Telemetry is written to `./logs/mcp_tool_spans.jsonl` on host.

## 5) Troubleshooting

- Ports 9100/9101/9102 must be reachable
- GitHub token must be present for GitHub tools
- If SSE transport UI not visible, fallback to command transport via Docker exec

```json
{
  "mcpServers": {
    "dev-assistant-mcp": {
      "command": "docker",
      "args": ["exec","-i","mcp_server","python","-m","mcp_server.ide_agents_mcp_server"],
      "env": {
        "IDE_AGENTS_BACKEND_URL": "http://ml-backend:8001",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```
