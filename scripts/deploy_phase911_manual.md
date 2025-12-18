# Aura IA Deployment Script (Phase 9.11)

This script deploys the latest Debate Engine features (Scheduler + Status Endpoint) to the NAS.

## 1. Copy Files to NAS
Run these commands in your local terminal (Git Bash or PowerShell):

```powershell
# Copy Scheduler
scp F:\Kiro_Projects\LATEST_MCP\aura_ia_mcp\services\debate_engine\scheduler.py {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/aura_ia_mcp/services/debate_engine/

# Copy Updated Engine (with Get Debate)
scp F:\Kiro_Projects\LATEST_MCP\aura_ia_mcp\services\debate_engine\engine.py {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/aura_ia_mcp/services/debate_engine/

# Copy Updated Server (with Status Endpoint & Lazy Scheduler Start)
scp F:\Kiro_Projects\LATEST_MCP\src\mcp_server\ide_agents_mcp_server.py {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/src/mcp_server/
```

## 2. Rebuild Authenticated Gateway Service
SSH into the NAS and rebuild the gateway container:

```bash
ssh {{YOUR_SSH_USER}}@{{NAS_IP}}
sudo -i
cd /volume2/docker/Herman/MCP_Server

# Rebuild Gateway
docker compose build --no-cache aura-ia-gateway
docker compose up -d --force-recreate --no-deps aura-ia-gateway
```

## 3. Verify Deployment
Check the new endpoint:

```bash
curl -s http://localhost:9200/v1/debate/leaderboard
# Expect valid JSON response
```
