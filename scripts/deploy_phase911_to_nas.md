# NAS Deployment Script for Phase 9.11

**Date:** December 12, 2025  
**Target:** Ubuntu NAS at {{NAS_IP}}

---

## Quick Reference

```
SSH: {{YOUR_SSH_USER}}@{{NAS_IP}}
Path: /volume2/docker/Herman/MCP_Server
Docker: /usr/local/bin/docker
```

---

## Step 1: Sync Files (From Windows PowerShell)

```powershell
# Run these from F:\Kiro_Projects\LATEST_MCP
scp -O -r src {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
scp -O -r aura_ia_mcp {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
scp -O -r ops {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
scp -O -r config {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
scp -O docker-compose.yml {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
scp -O requirements*.txt {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
scp -O AURA_IA_MCP_PRD.md {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
scp -O -r docs {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
```

---

## Step 2: Rebuild Containers (SSH to NAS)

```bash
# SSH first
ssh {{YOUR_SSH_USER}}@{{NAS_IP}}

# Navigate to project
cd /volume2/docker/Herman/MCP_Server

# Rebuild with no cache (requires sudo)
sudo /usr/local/bin/docker compose build --no-cache aura-ia-role-engine
sudo /usr/local/bin/docker compose build --no-cache aura-ia-gateway
sudo /usr/local/bin/docker compose build --no-cache aura-ia-ml

# Restart all services
sudo /usr/local/bin/docker compose up -d
```

---

## Step 3: Verify Endpoints

```bash
# Run these from NAS shell

# Health checks
curl -s http://localhost:9206/health        # Role Engine
curl -s http://localhost:9200/healthz       # Gateway
curl -s http://localhost:9200/readyz        # Gateway ready

# New Phase 9.11 endpoints
curl -s http://localhost:9200/v1/dashboard/summary
curl -s http://localhost:9200/v1/debate/topics
curl -s http://localhost:9200/v1/debate/leaderboard

# Ollama (MCP Concierge model)
curl -s http://localhost:9207/api/tags | grep phi3.5
```

---

## Expected Results

| Endpoint | Expected Response |
|----------|-------------------|
| `/health` (9206) | `{"status": "ok"}` |
| `/healthz` (9200) | `{"status": "live", ...}` |
| `/readyz` (9200) | `{"status": "ok", "backend_ok": true}` |
| `/v1/dashboard/summary` | JSON with router_stats, debates, rag |
| `/v1/debate/topics` | 60 topics across 6 categories |
| `/v1/debate/leaderboard` | 4 models with ELO ratings |
| Ollama phi3.5 | Model in tags list |

---

## Troubleshooting

**If containers fail to start:**
```bash
sudo /usr/local/bin/docker compose logs aura-ia-gateway
sudo /usr/local/bin/docker compose logs aura-ia-role-engine
```

**If Ollama healthcheck fails:**
```bash
sudo /usr/local/bin/docker exec -it aura_ia_ollama bash -c "apt-get update && apt-get install -y curl"
sudo /usr/local/bin/docker compose restart aura-ia-ollama
```

**Check container status:**
```bash
sudo /usr/local/bin/docker compose ps
```
